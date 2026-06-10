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

import sys
import threading
import uuid
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

DUCK = "\U0001F986"  # 🦆
FILES = "abcdefgh"
PIECE_VALUES = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9, "K": 0}
START_COUNT = {"P": 8, "N": 2, "B": 2, "R": 2, "Q": 1, "K": 1}


def sq(rc) -> str:
    """(row, col) -> algebraic, e.g. (6,4) -> 'e2'. row 0 = rank 8."""
    r, c = rc
    return f"{FILES[c]}{8 - r}"


# ---------------------------------------------------------------------------
# Model registry  (display label -> .zip path).  Only existing files are kept.
# ---------------------------------------------------------------------------
_CANDIDATE_MODELS = [
    ("stage12",     "Duck PPO — Stage 12 (final)",   MODELS_DIR / "stage 12" / "stage12_final_v52.zip"),
    ("stage11",     "Duck PPO — Stage 11",           MODELS_DIR / "stage 11" / "stage11_sparse_v8.zip"),
    ("stage10",     "Duck PPO — Stage 10 (league)",  MODELS_DIR / "stage 10" / "stage10_league_latest.zip"),
    ("stage10v416", "Duck PPO — Stage 10 v416",      MODELS_DIR / "stage 10" / "stage10_league_v416.zip"),
    ("stage9",      "Duck PPO — Stage 9",            MODELS_DIR / "stage 9"  / "stage9_selfplay_latest.zip"),
]
MODEL_CHOICES = [
    {"id": mid, "label": label, "path": path}
    for mid, label, path in _CANDIDATE_MODELS
    if path.exists()
]

_model_cache: dict[str, MaskablePPO] = {}
_model_lock = threading.Lock()


def get_model(model_id: str):
    """Return (model, choice_dict), loading + caching lazily. Falls back to first."""
    choice = next((m for m in MODEL_CHOICES if m["id"] == model_id), None)
    if choice is None:
        if not MODEL_CHOICES:
            raise HTTPException(500, "No PPO model files found under models/duck_ppo/.")
        choice = MODEL_CHOICES[0]
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
    rows, cur = [], None
    for hm in halfmoves:
        if hm["color"] == "w":
            cur = {"n": len(rows) + 1, "w": hm["text"], "b": ""}
            rows.append(cur)
        else:
            if cur is None:
                rows.append({"n": len(rows) + 1, "w": "…", "b": hm["text"]})
            else:
                cur["b"] = hm["text"]
                cur = None
    return rows


def valid_duck_squares(engine):
    """Authoritative list of legal duck squares for the current move_duck phase."""
    masks = engine.action_masks()
    out = []
    for a in np.where(masks)[0]:
        _, d = engine._decode_move(int(a))
        out.append([d[0], d[1]])
    return out


def serialize(sess, *, highlight=None, ai_move=None, player_move=None, message=None):
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
    }


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
    model: str = "stage12"
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


def _get_session(game_id: str) -> Session:
    sess = SESSIONS.get(game_id)
    if sess is None:
        raise HTTPException(404, "Game not found. Start a new game.")
    return sess


@app.get("/api/models")
def list_models():
    return {"models": [{"id": m["id"], "label": m["label"]} for m in MODEL_CHOICES]}


@app.post("/api/new-game")
def new_game(req: NewGameReq):
    player_color = "w" if req.color == "white" else "b"
    _, choice = get_model(req.model)          # validates / preloads the model
    engine = _HeadlessEngine()
    sess = Session(engine, player_color, choice["id"], choice["label"])
    gid = uuid.uuid4().hex[:12]
    SESSIONS[gid] = sess

    ai_move = None
    with sess.lock:
        if player_color == "b":               # model is White -> it moves first
            ai_move = play_model_turn(sess)
        state = serialize(sess, ai_move=ai_move,
                          highlight=([ai_move["from"], ai_move["to"]] if ai_move else []))
    state["gameId"] = gid
    return state


@app.post("/api/legal-moves")
def legal_moves(req: SelectReq):
    sess = _get_session(req.game_id)
    e = sess.engine
    with sess.lock:
        if e.game_over or e.turn != sess.player_color or e.phase != "move_piece":
            return {"moves": []}
        p = e.board[req.r][req.c]
        if p is None or p.color != sess.player_color:
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
        if e.turn != sess.player_color or e.phase != "move_piece":
            raise HTTPException(400, "Not your move-piece phase.")
        frm = (int(req.frm[0]), int(req.frm[1]))
        to = (int(req.to[0]), int(req.to[1]))
        p = e.board[frm[0]][frm[1]]
        if p is None or p.color != sess.player_color:
            raise HTTPException(400, "No piece of yours on the start square.")
        legal = e.get_piece_legal_moves(frm[0], frm[1])
        if to not in legal:
            raise HTTPException(400, "Illegal move for that piece.")

        e.execute_move(frm, to, animated=False)
        sess.pending = (frm, to)

        if getattr(e, "game_over", False):     # king captured -> instant win
            sess.halfmoves.append({"color": sess.player_color, "text": f"{sq(frm)}{sq(to)}#"})
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
        if e.turn != sess.player_color or e.phase != "move_duck":
            raise HTTPException(400, "Not your move-duck phase.")
        duck = (int(req.duck[0]), int(req.duck[1]))
        valid = {tuple(x) for x in valid_duck_squares(e)}
        if duck not in valid:
            raise HTTPException(400, "Illegal duck square.")

        e.place_duck(duck, animated=False)

        frm, to = sess.pending if sess.pending else ((0, 0), (0, 0))
        sess.pending = None
        sess.halfmoves.append(
            {"color": sess.player_color, "text": f"{sq(frm)}{sq(to)} {DUCK}{sq(duck)}"}
        )
        player_move = {"from": list(frm), "to": list(to), "duck": list(duck)}

        ai_move = None
        if not getattr(e, "game_over", False):
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
        e.game_over = True
        e.winner = sess.model_color
        state = serialize(sess, message="resign")
    return state


# Static files LAST so /api/* routes win.  html=True -> "/" serves index.html.
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    print(f"[Duck Chess] models available: {[m['id'] for m in MODEL_CHOICES]}")
    uvicorn.run(app, host="127.0.0.1", port=7890)
