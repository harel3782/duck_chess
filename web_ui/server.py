"""
Duck Chess — Web backend (FastAPI).

Wraps the real game engine (DuckChess_Game.Logic via the pygame-free
_HeadlessEngine) and the trained MaskablePPO models so the web UI in this
folder can actually play Duck Chess against a model.

Run from the PROJECT ROOT:
    python -m uvicorn web_ui.server:app --port 7890
or simply:
    python web_ui/server.py

Notes
-----
* Login is intentionally OPEN (no real auth / no database yet). The frontend
  lets any name in; the backend keeps games in memory keyed by a game id.
* A "turn" in Duck Chess has two phases: move a piece, then move the duck.
  The API mirrors that:  /api/move-piece  then  /api/place-duck.
  After the human's duck placement the selected model plays its full turn.
"""
from __future__ import annotations

import json
import re
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# --- make the project importable when run from anywhere -------------------
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from DuckChess_Game.SBThree.base.env_base import _HeadlessEngine  # noqa: E402
from sb3_contrib import MaskablePPO  # noqa: E402

WEB_DIR = Path(__file__).resolve().parent
MODELS_DIR = ROOT / "models" / "duck_ppo"
# Web game saves live in their own subfolder of saved_replays/ so they never
# collide with the training-replay pickles (saved under numbered stage dirs).
SAVED_GAMES_DIR = ROOT / "saved_replays" / "web"
# Shared art (piece sprites, duck, sounds), a sibling of web_ui/. Served at /assets.
ASSETS_DIR = ROOT / "assets"

DUCK = "\U0001F986"  # 🦆
FILES = "abcdefgh"
PIECE_VALUES = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9, "K": 0}
START_COUNT = {"P": 8, "N": 2, "B": 2, "R": 2, "Q": 1, "K": 1}


def sq(rc) -> str:
    """(row, col) -> algebraic, e.g. (6,4) -> 'e2'. row 0 = rank 8."""
    r, c = rc
    return f"{FILES[c]}{8 - r}"


# ---------------------------------------------------------------------------
# Model discovery (auto-scan models/duck_ppo for all .zip files)
# ---------------------------------------------------------------------------
GROUP_ORDER = [
    "v2",
    "stage 14", "stage 13", "stage 12", "stage 11", "stage 10",
    "stage 9",  "stage 8",  "stage 7",  "stage 6",  "stage 5",
    "stage 4",  "stage 3",  "stage 2",  "stage 1",
    "strong", "real", "peter_local", "antiexploit",
]


def _file_sort_key(stem: str):
    """'final'/'latest' first, then descending version number, then alpha."""
    if stem.endswith("_final") or stem.endswith("_latest") or stem in ("final", "latest"):
        return (0, 0, "")
    m = re.search(r"v(\d+)$", stem)
    if m:
        return (1, -int(m.group(1)), "")
    return (2, 0, stem)


def discover_models() -> list[dict]:
    """Recursively scan models/duck_ppo/ for all .zip files."""
    entries = []
    for zip_path in sorted(MODELS_DIR.rglob("*.zip")):
        if not zip_path.is_file():
            continue
        group = zip_path.parent.name if zip_path.parent != MODELS_DIR else ""
        stem = zip_path.stem
        slug = ((group + "_" + stem) if group else stem).replace(" ", "_")
        label = ((group + " — " + stem) if group else stem)
        entries.append({"id": slug, "label": label, "path": zip_path, "group": group or "(root)"})

    def sort_key(e):
        g = e["group"]
        try:
            gi = GROUP_ORDER.index(g)
        except ValueError:
            gi = len(GROUP_ORDER)
        return (gi, _file_sort_key(Path(e["path"]).stem))

    entries.sort(key=sort_key)
    return entries


_discovered: list[dict] | None = None


def get_model_choices(refresh: bool = False) -> list[dict]:
    """Get cached model list, optionally refresh it."""
    global _discovered
    if _discovered is None or refresh:
        _discovered = discover_models()
    return _discovered


# Default opponent: the strongest *stable* league checkpoint, NOT the experimental
# v2 group (which sorts first). The first preference that actually exists on disk
# wins; if none are present we fall back to the first discovered model. This drives
# both the dropdown's pre-selected option and get_model()'s fallback for unknown ids.
DEFAULT_MODEL_PREFERENCES = (
    "stage_13_stage13_final",
    "strong_strong_final",
    "stage_12_stage12_final_master",
)


def get_default_choice() -> dict | None:
    """The default opponent choice dict (preferred stable model, else first discovered)."""
    choices = get_model_choices()
    if not choices:
        return None
    by_id = {m["id"]: m for m in choices}
    for pref in DEFAULT_MODEL_PREFERENCES:
        if pref in by_id:
            return by_id[pref]
    return choices[0]


_model_cache: dict[str, MaskablePPO] = {}
_model_lock = threading.Lock()


def get_model(model_id: str):
    """Return (model, choice_dict), loading + caching lazily. Unknown ids fall back
    to the configured default model (get_default_choice)."""
    choices = get_model_choices()
    choice = next((m for m in choices if m["id"] == model_id), None)
    if choice is None:
        choice = get_default_choice()
        if choice is None:
            raise HTTPException(500, "No PPO model files found under models/duck_ppo/.")
    with _model_lock:
        if choice["id"] not in _model_cache:
            _model_cache[choice["id"]] = MaskablePPO.load(str(choice["path"]), device="cpu")
    return _model_cache[choice["id"]], choice


# ---------------------------------------------------------------------------
# In-memory game sessions
# ---------------------------------------------------------------------------
class Session:
    def __init__(self, engine, player_color, model_id, model_label):
        self.engine = engine
        self.player_color = player_color          # 'w' or 'b'
        self.model_color = "b" if player_color == "w" else "w"
        self.model_id = model_id
        self.model_label = model_label
        self.halfmoves: list[dict] = []           # {'color','text'}
        self.pending = None                       # (frm, to) between the two phases
        self.lock = threading.Lock()


SESSIONS: dict[str, Session] = {}
MAX_SESSIONS = 100        # cap memory: oldest sessions are evicted past this (local dev server)


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------
def board_to_grid(engine):
    grid = []
    for r in range(8):
        row = []
        for c in range(8):
            p = engine.board[r][c]
            row.append(None if p is None else p.color + p.type)
        row_ = row
        grid.append(row_)
    return grid


def captured_lists(engine):
    """Return (captured_by_white, captured_by_black) as lists of piece codes."""
    cur = {"w": {}, "b": {}}
    for r in range(8):
        for c in range(8):
            p = engine.board[r][c]
            if p:
                cur[p.color][p.type] = cur[p.color].get(p.type, 0) + 1
    cap_w, cap_b = [], []   # white captured black pieces / black captured white pieces
    order = ["Q", "R", "B", "N", "P"]
    for t in order:
        n = START_COUNT[t]
        for _ in range(n - cur["b"].get(t, 0)):
            cap_w.append("b" + t)
        for _ in range(n - cur["w"].get(t, 0)):
            cap_b.append("w" + t)
    return cap_w, cap_b


def material_diff(engine):
    s = 0
    for r in range(8):
        for c in range(8):
            p = engine.board[r][c]
            if p:
                s += PIECE_VALUES[p.type] * (1 if p.color == "w" else -1)
    return s


def history_rows(halfmoves):
    return halfmoves


def valid_duck_squares(engine):
    """Authoritative list of legal duck squares for the current move_duck phase."""
    masks = engine.action_masks()
    out = []
    for a in np.where(masks)[0]:
        _, d = engine._decode_move(int(a))
        out.append([d[0], d[1]])
    return out


def serialize(sess, *, highlight=None, ai_move=None, player_move=None, message=None, reason=None):
    e = sess.engine
    cap_w, cap_b = captured_lists(e)
    diff = material_diff(e)
    duck = list(e.duck_pos) if tuple(e.duck_pos) != (-1, -1) else None
    return {
        "board": board_to_grid(e),
        "duck": duck,
        "turn": e.turn,
        "phase": e.phase,
        "gameOver": bool(getattr(e, "game_over", False)),
        "winner": getattr(e, "winner", None),
        "playerColor": sess.player_color,
        "modelColor": sess.model_color,
        "modelLabel": sess.model_label,
        "history": history_rows(sess.halfmoves),
        "capturedByWhite": cap_w,
        "capturedByBlack": cap_b,
        "evalDiff": diff,
        "highlight": highlight or [],
        "aiMove": ai_move,
        "playerMove": player_move,
        "message": message,
        "reason": game_over_reason(e, reason),
    }


def _result_text(engine) -> str:
    """Short human-readable result for a saved game card."""
    if not getattr(engine, "game_over", False):
        return "Unfinished"
    w = getattr(engine, "winner", None)
    return {"draw": "Draw", "w": "White won", "b": "Black won"}.get(w, "Finished")


def game_over_reason(engine, override=None):
    """Why the game ended: 'king_capture' | 'fowling' | 'resign' | 'draw_50move' | None.

    Derived purely from engine state (no engine changes needed):
      * resign is the only reason the server sets explicitly -> passed as `override`.
      * the engine's only draw is the 50-move rule (endgame_checker) -> winner == 'draw'.
      * a king capture removes that king from the board, so a missing king == capture.
      * otherwise a finished game must be fowling (a side had no legal move and wins).
    """
    if override:
        return override
    if not getattr(engine, "game_over", False):
        return None
    if getattr(engine, "winner", None) == "draw":
        return "draw_50move"
    kings = {"w": 0, "b": 0}
    for r in range(8):
        for c in range(8):
            p = engine.board[r][c]
            if p is not None and p.type == "K":
                kings[p.color] = kings.get(p.color, 0) + 1
    if kings["w"] == 0 or kings["b"] == 0:
        return "king_capture"
    return "fowling"


def _snapshots_from_halfmoves(halfmoves) -> list:
    """Replay halfmove notation into a fresh engine and return, after each completed
    halfmove (plus the initial position), a snapshot dict:

        {"board": <8x8 piece grid>, "duck": [row, col] | None}

    The duck is captured PER STEP (from eng.duck_pos) so the replay viewer can move
    the duck, not just the pieces. On a king-capture halfmove (no duck placed) the
    duck simply stays where it was — eng.duck_pos reflects that correctly.

    Notation is deterministic: the first 4 chars are the piece move (e.g. 'e2e4');
    an optional ' <duck-emoji><sq>' suffix is the duck placement (e.g. 'e2e4 🦆d4');
    a trailing '#' marks a king capture. This is the source of `board_snapshots`.
    """
    def _duck(eng):
        return list(eng.duck_pos) if tuple(eng.duck_pos) != (-1, -1) else None

    eng = _HeadlessEngine()
    snaps = [{"board": board_to_grid(eng), "duck": _duck(eng)}]
    for hm in halfmoves:
        text = hm.get("text", "") if isinstance(hm, dict) else ""
        if len(text) >= 4:
            try:
                frm = (8 - int(text[1]), ord(text[0]) - ord("a"))
                to = (8 - int(text[3]), ord(text[2]) - ord("a"))
                eng.execute_move(frm, to, animated=False)
                if DUCK in text and not getattr(eng, "game_over", False):
                    i = text.index(DUCK)
                    dsq = text[i + 1:i + 3]
                    if len(dsq) == 2:
                        duck = (8 - int(dsq[1]), ord(dsq[0]) - ord("a"))
                        eng.place_duck(duck, animated=False)
            except (ValueError, IndexError):
                pass
        snaps.append({"board": board_to_grid(eng), "duck": _duck(eng)})
    return snaps


# ---------------------------------------------------------------------------
# Core game logic
# ---------------------------------------------------------------------------
def play_model_turn(sess):
    """Let the model play its full turn (piece + duck). Returns last aiMove dict."""
    e = sess.engine
    model, _ = get_model(sess.model_id)
    last = None
    # one full turn = one piece phase + one duck phase; loop guards against
    # any unexpected state where it is still the model's move.
    while e.turn == sess.model_color and not getattr(e, "game_over", False):
        masks = e.action_masks()
        if not masks.any():
            # Fowled: the side to move has no legal move -> that side wins (Duck rule).
            e.game_over = True
            e.winner = sess.model_color
            break

        # ---- piece phase ----
        obs = e._get_obs()
        action, _ = model.predict(obs, action_masks=masks, deterministic=True)
        p_from, p_to = e._decode_move(int(action))
        e.execute_move(p_from, p_to, animated=False)

        if getattr(e, "game_over", False):
            sess.halfmoves.append({"color": sess.model_color, "text": f"{sq(p_from)}{sq(p_to)}#"})
            return {"from": list(p_from), "to": list(p_to), "duck": None}

        # ---- duck phase ----
        masks = e.action_masks()
        if not masks.any():
            e.game_over = True
            e.winner = sess.model_color
            sess.halfmoves.append({"color": sess.model_color, "text": f"{sq(p_from)}{sq(p_to)}"})
            return {"from": list(p_from), "to": list(p_to), "duck": None}
        obs = e._get_obs()
        action, _ = model.predict(obs, action_masks=masks, deterministic=True)
        _, d_to = e._decode_move(int(action))
        e.place_duck(d_to, animated=False)

        sess.halfmoves.append(
            {"color": sess.model_color, "text": f"{sq(p_from)}{sq(p_to)} {DUCK}{sq(d_to)}"}
        )
        last = {"from": list(p_from), "to": list(p_to), "duck": list(d_to)}
    return last


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
app = FastAPI(title="Duck Chess Web")


class NewGameReq(BaseModel):
    model: str | None = None      # None -> local 2-player (human vs human)
    color: str = "white"          # 'white' | 'black'


class SelectReq(BaseModel):
    game_id: str
    r: int
    c: int


class MovePieceReq(BaseModel):
    game_id: str
    frm: list                     # [row, col]
    to: list                      # [row, col]


class PlaceDuckReq(BaseModel):
    game_id: str
    duck: list                    # [row, col]


class UndoMoveReq(BaseModel):
    game_id: str


class SaveGameReq(BaseModel):
    game_id: str
    username: str = "Player"
    label: str = ""


class DeleteGameReq(BaseModel):
    filename: str


def _get_session(game_id: str) -> Session:
    sess = SESSIONS.get(game_id)
    if sess is None:
        raise HTTPException(404, "Game not found. Start a new game.")
    return sess


def _human_to_move(sess: Session) -> bool:
    """True if the side to move is human-controlled.

    In local 2-player (model_id is None) BOTH colors are human. In vs-model only
    the player's own color is human-controlled.
    """
    if sess.model_id is None:
        return True
    return sess.engine.turn == sess.player_color


@app.get("/api/models")
def list_models(refresh: bool = False):
    choices = get_model_choices(refresh=refresh)
    default = get_default_choice()
    return {
        "models": [{"id": m["id"], "label": m["label"], "group": m["group"]} for m in choices],
        "default": default["id"] if default else None,
    }


@app.post("/api/new-game")
def new_game(req: NewGameReq):
    if req.color not in ("white", "black"):
        raise HTTPException(400, "color must be 'white' or 'black'.")
    player_color = "w" if req.color == "white" else "b"
    engine = _HeadlessEngine()

    if req.model is None:                     # local 2-player (human vs human)
        sess = Session(engine, player_color, None, "2 Players")
    else:
        _, choice = get_model(req.model)      # validates / preloads the model
        sess = Session(engine, player_color, choice["id"], choice["label"])

    gid = uuid.uuid4().hex[:12]
    SESSIONS[gid] = sess
    while len(SESSIONS) > MAX_SESSIONS:           # evict oldest (insertion order)
        SESSIONS.pop(next(iter(SESSIONS)))

    ai_move = None
    with sess.lock:
        # model plays White first only when there IS a model and the human is Black
        if sess.model_id is not None and player_color == "b":
            ai_move = play_model_turn(sess)
        state = serialize(sess, ai_move=ai_move,
                          highlight=([ai_move["from"], ai_move["to"]] if ai_move else []))
    state["gameId"] = gid
    return state


@app.post("/api/legal-moves")
def legal_moves(req: SelectReq):
    if not (0 <= req.r <= 7 and 0 <= req.c <= 7):
        raise HTTPException(400, "Square out of bounds.")
    sess = _get_session(req.game_id)
    e = sess.engine
    with sess.lock:
        if e.game_over or not _human_to_move(sess) or e.phase != "move_piece":
            return {"moves": []}
        p = e.board[req.r][req.c]
        if p is None or p.color != e.turn:     # may only move the side whose turn it is
            return {"moves": []}
        moves = [[r, c] for (r, c) in e.get_piece_legal_moves(req.r, req.c)]
    return {"moves": moves}


@app.post("/api/move-piece")
def move_piece(req: MovePieceReq):
    sess = _get_session(req.game_id)
    e = sess.engine
    with sess.lock:
        if e.game_over:
            raise HTTPException(400, "Game is over.")
        if not _human_to_move(sess) or e.phase != "move_piece":
            raise HTTPException(400, "Not your move-piece phase.")
        mover = e.turn                         # actual side to move (== player_color in vs-model)
        frm = (int(req.frm[0]), int(req.frm[1]))
        to = (int(req.to[0]), int(req.to[1]))
        if not (0 <= frm[0] <= 7 and 0 <= frm[1] <= 7 and 0 <= to[0] <= 7 and 0 <= to[1] <= 7):
            raise HTTPException(400, "Square out of bounds.")
        p = e.board[frm[0]][frm[1]]
        if p is None or p.color != mover:
            raise HTTPException(400, "No piece of yours on the start square.")
        legal = e.get_piece_legal_moves(frm[0], frm[1])
        if to not in legal:
            raise HTTPException(400, "Illegal move for that piece.")

        e.execute_move(frm, to, animated=False)
        sess.pending = (frm, to)

        if getattr(e, "game_over", False):     # king captured -> instant win
            sess.halfmoves.append({"color": mover, "text": f"{sq(frm)}{sq(to)}#"})
            sess.pending = None
            state = serialize(sess, player_move={"from": list(frm), "to": list(to), "duck": None},
                              highlight=[list(frm), list(to)])
            return state

        # now in move_duck phase
        state = serialize(sess, player_move={"from": list(frm), "to": list(to), "duck": None},
                          highlight=[list(frm), list(to)])
        state["validDuck"] = valid_duck_squares(e)
    return state


@app.post("/api/place-duck")
def place_duck(req: PlaceDuckReq):
    sess = _get_session(req.game_id)
    e = sess.engine
    with sess.lock:
        if e.game_over:
            raise HTTPException(400, "Game is over.")
        if not _human_to_move(sess) or e.phase != "move_duck":
            raise HTTPException(400, "Not your move-duck phase.")
        mover = e.turn                         # capture before place_duck flips the turn
        duck = (int(req.duck[0]), int(req.duck[1]))
        valid = {tuple(x) for x in valid_duck_squares(e)}
        if duck not in valid:
            raise HTTPException(400, "Illegal duck square.")

        e.place_duck(duck, animated=False)

        frm, to = sess.pending if sess.pending else ((0, 0), (0, 0))
        sess.pending = None
        sess.halfmoves.append(
            {"color": mover, "text": f"{sq(frm)}{sq(to)} {DUCK}{sq(duck)}"}
        )
        player_move = {"from": list(frm), "to": list(to), "duck": list(duck)}

        # In local 2-player there is no model: the turn simply flips to the other human.
        ai_move = None
        if sess.model_id is not None and not getattr(e, "game_over", False):
            ai_move = play_model_turn(sess)

        hi = []
        if ai_move:
            hi = [ai_move["from"], ai_move["to"]]
        else:
            hi = [list(frm), list(to)]
        state = serialize(sess, player_move=player_move, ai_move=ai_move, highlight=hi)
    return state


@app.post("/api/resign")
def resign(req: SelectReq):
    sess = _get_session(req.game_id)
    e = sess.engine
    with sess.lock:
        if e.game_over:
            raise HTTPException(400, "Game is already over.")
        resigning_color = e.turn                  # the side to move is the one resigning
        e.game_over = True
        e.winner = "b" if resigning_color == "w" else "w"
        state = serialize(sess, message="resign", reason="resign")
    return state


@app.post("/api/undo-move")
def undo_move(req: UndoMoveReq):
    """Undo the last turn. In 2-player that's one player-turn (piece + duck); in
    vs-model it's the full human+model round. Only when it's a human's move-piece phase."""
    sess = _get_session(req.game_id)
    e = sess.engine
    with sess.lock:
        if e.game_over:
            raise HTTPException(400, "Cannot undo: game is over.")
        if sess.model_id is not None and e.turn != sess.player_color:
            raise HTTPException(400, "Cannot undo on opponent's turn.")
        # How many halfmoves make up "one undo":
        #   2-player local -> one player-turn is a single halfmove, so undo ONE.
        #   vs-model       -> a full round is human + model = two halfmoves, so
        #                     undo BOTH to hand the human back THEIR own turn.
        n_undo = 1 if sess.model_id is None else 2
        if len(sess.halfmoves) < n_undo:
            raise HTTPException(400, "No moves to undo.")
        if e.phase != "move_piece":
            raise HTTPException(400, "Can only undo at the start of a turn (piece phase).")

        sess.halfmoves = sess.halfmoves[:-n_undo]
        new_engine = _HeadlessEngine()
        for hm in sess.halfmoves:
            move_str = hm["text"]
            if len(move_str) < 4:
                continue
            try:
                frm_file = ord(move_str[0]) - ord('a')
                frm_rank = 8 - int(move_str[1])
                to_file = ord(move_str[2]) - ord('a')
                to_rank = 8 - int(move_str[3])
                new_engine.execute_move((frm_rank, frm_file), (to_rank, to_file), animated=False)
                if "🦆" in move_str or "@" in move_str or move_str.count(" ") > 0:
                    for i in range(len(move_str)):
                        if i < len(move_str) - 1 and move_str[i] in "abcdefgh" and move_str[i + 1] in "12345678":
                            if i < 5:
                                continue
                            duck_file = ord(move_str[i]) - ord('a')
                            duck_rank = 8 - int(move_str[i + 1])
                            new_engine.place_duck((duck_rank, duck_file), animated=False)
                            break
            except (ValueError, IndexError):
                pass
        sess.engine = new_engine
        state = serialize(sess)
    return state


@app.post("/api/save-game")
def save_game(req: SaveGameReq):
    """Persist the current game (incl. board_snapshots) as a JSON file."""
    sess = _get_session(req.game_id)
    e = sess.engine
    with sess.lock:
        SAVED_GAMES_DIR.mkdir(parents=True, exist_ok=True)
        safe_user = re.sub(r"[^A-Za-z0-9_-]", "_", (req.username or "Player"))[:40] or "Player"
        filename = f"{safe_user}_{uuid.uuid4().hex[:8]}.json"
        duck = list(e.duck_pos) if tuple(e.duck_pos) != (-1, -1) else None
        payload = {
            "filename": filename,
            "username": req.username or "Player",
            "label": req.label or "(Unnamed)",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "saved_at": int(time.time()),
            "result": _result_text(e),
            "model_label": sess.model_label if sess.model_id is not None else None,
            "player_color": sess.player_color,
            "model_color": sess.model_color,
            "winner": getattr(e, "winner", None),
            "game_over": bool(getattr(e, "game_over", False)),
            "duck": duck,
            "board": board_to_grid(e),
            "history": sess.halfmoves,
            "board_snapshots": _snapshots_from_halfmoves(sess.halfmoves),
        }
        try:
            with open(SAVED_GAMES_DIR / filename, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except OSError as ex:
            raise HTTPException(500, f"Could not save game: {ex}")
    return {"ok": True, "filename": filename}


@app.get("/api/saved-games")
def saved_games(username: str = ""):
    """List saved games for a username, newest first."""
    SAVED_GAMES_DIR.mkdir(parents=True, exist_ok=True)
    games = []
    for p in SAVED_GAMES_DIR.glob("*.json"):
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if username and data.get("username") != username:
            continue
        games.append({
            "filename": data.get("filename", p.name),
            "label": data.get("label", "(Unnamed)"),
            "timestamp": data.get("timestamp", ""),
            "result": data.get("result", ""),
            "model_label": data.get("model_label"),
            "saved_at": data.get("saved_at", 0),
        })
    games.sort(key=lambda g: g.get("saved_at", 0), reverse=True)
    return {"games": games}


def _resolve_saved_game(filename: str) -> Path:
    """Resolve a saved-game filename to a path inside SAVED_GAMES_DIR, or raise.

    Shared path-traversal guard for load-game and delete-game: the name must be a
    plain '.json' basename that resolves inside the saved-games dir. 400 for a bad
    filename, 404 if the file does not exist.
    """
    safe = Path(filename).name             # strip any path components
    if not safe.endswith(".json"):
        raise HTTPException(400, "Invalid file.")
    path = SAVED_GAMES_DIR / safe
    try:
        resolved = path.resolve()
        resolved.relative_to(SAVED_GAMES_DIR.resolve())   # must stay inside the dir
    except (ValueError, OSError):
        raise HTTPException(400, "Invalid file path.")
    if not resolved.is_file():
        raise HTTPException(404, "Saved game not found.")
    return resolved


@app.get("/api/load-game/{filename}")
def load_game(filename: str):
    """Return the full saved payload (incl. board_snapshots) for replay."""
    resolved = _resolve_saved_game(filename)
    try:
        with open(resolved, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        raise HTTPException(500, "Could not read saved game.")
    # Rebuild snapshots on the fly (without touching the file on disk) when they
    # are missing OR in the legacy duck-less format (a bare grid per entry, or a
    # dict lacking a 'duck' key). The rebuild parses the duck from the history so
    # old saves replay with a moving duck too.
    bs = data.get("board_snapshots")
    if not bs or not isinstance(bs[0], dict) or "duck" not in bs[0]:
        data["board_snapshots"] = _snapshots_from_halfmoves(data.get("history", []))
    return data


@app.post("/api/delete-game")
def delete_game(req: DeleteGameReq):
    """Delete a saved game file (same dir + path-traversal guard as load-game)."""
    resolved = _resolve_saved_game(req.filename)
    try:
        resolved.unlink()
    except OSError as ex:
        raise HTTPException(500, f"Could not delete game: {ex}")
    return {"ok": True, "filename": Path(req.filename).name}


# Serve the shared assets/ dir (piece sprites, duck, sounds) at /assets. Must be
# mounted BEFORE the catch-all "/" mount below, or "/" would swallow these paths.
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

# Static files LAST so /api/* routes win.  html=True -> "/" serves index.html.
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="static")


def ensure_models_downloaded() -> None:
    """Fetch model checkpoints at boot when the models dir is empty.

    The ~1.3 GB MaskablePPO checkpoints are not stored in git, so a fresh
    container starts with an empty models/duck_ppo/. If MODEL_ZIP_URL is set
    (a direct link to a zip of the checkpoints), download and extract it into
    models/duck_ppo/ so vs-model play works; the zip is expected to contain the
    checkpoint files/folders directly. With no URL set we warn and continue —
    local 2-player play still works without any model. A failed download never
    crashes boot.
    """
    import os
    import zipfile

    import requests

    if MODELS_DIR.exists() and any(MODELS_DIR.rglob("*.zip")):
        return  # models already present — nothing to do

    url = os.environ.get("MODEL_ZIP_URL")
    if not url:
        print("[Duck Chess] WARNING: No models found and MODEL_ZIP_URL not set — "
              "vs-model play will be unavailable.")
        return

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = MODELS_DIR.parent / "_models_download.zip"
    print("[Duck Chess] No models found — downloading from MODEL_ZIP_URL …")
    try:
        with requests.get(url, stream=True, timeout=300) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            got = mark = 0
            with open(zip_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1 << 20):   # 1 MB
                    fh.write(chunk)
                    got += len(chunk)
                    if total and got >= mark:                         # log ~every 10%
                        print(f"[Duck Chess]   {got/1e6:.0f}/{total/1e6:.0f} MB "
                              f"({100 * got // total}%)", flush=True)
                        mark += max(total // 10, 1)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(MODELS_DIR)
        n = len(list(MODELS_DIR.rglob("*.zip")))
        print(f"[Duck Chess] Models ready — extracted {n} checkpoint(s) into {MODELS_DIR}.")
    except Exception as exc:                                          # never crash boot over a fetch
        print(f"[Duck Chess] WARNING: model download failed ({exc}) — "
              "vs-model play will be unavailable.")
    finally:
        try:
            zip_path.unlink(missing_ok=True)
        except OSError:
            pass


if __name__ == "__main__":
    import os

    # The model checkpoints were saved with this project's .venv (Python 3.12 /
    # torch 2.11). Loading them under a different interpreter — notably the system
    # Python 3.13 + torch 2.12 — hard-crashes (segfaults, exit 139) the moment a
    # game loads a model, with no Python traceback. Refuse to start under the wrong
    # interpreter with a clear message instead of crashing later. Set DUCK_NO_REEXEC=1
    # to override the check (e.g. you know your interpreter is ABI-compatible).
    _venv_py = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if (
        os.environ.get("DUCK_NO_REEXEC") != "1"
        and _venv_py.exists()
        and Path(sys.executable).resolve() != _venv_py.resolve()
    ):
        print(f"[Duck Chess] Wrong Python interpreter: {sys.executable}")
        print(f"[Duck Chess] Models were saved with the project's .venv and crash "
              f"(segfault) when loaded under a different Python/torch.")
        print(f"[Duck Chess] Run with .venv python: .venv/Scripts/python web_ui/server.py")
        print(f"[Duck Chess] (set DUCK_NO_REEXEC=1 to skip this check)")
        sys.exit(1)

    import uvicorn
    print(f"[Duck Chess] python: {sys.executable}")
    ensure_models_downloaded()
    print(f"[Duck Chess] models available: {[m['id'] for m in get_model_choices()]}")
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "7890"))
    uvicorn.run(app, host=host, port=port)
