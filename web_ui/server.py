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
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

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
    # Return halfmoves as-is; frontend does the pairing
    return halfmoves


def valid_duck_squares(engine):
    """Authoritative list of legal duck squares for the current move_duck phase."""
    masks = engine.action_masks()
    out = []
    for a in np.where(masks)[0]:
        _, d = engine._decode_move(int(a))
        out.append([d[0], d[1]])
    return out


def _enhance_history_with_notation(engine, halfmoves):
    """Add human-readable notation to move history."""
    piece_symbols = {
        'P': '♟', 'N': '♞', 'B': '♝', 'R': '♜', 'Q': '♛', 'K': '♚',
    }

    enhanced = []
    for hm in halfmoves:
        notation = hm["text"]  # default: use raw text

        # Try to add piece symbols for piece moves
        if len(notation) >= 4:
            from_file = notation[0]
            to_file = notation[2]
            # Check if it's a capture (indicated by 'x' or followed by emoji)
            is_capture = 'x' in notation or len(notation) > 4

            # Try to get the piece at the from square (from board state)
            try:
                from_idx = ord(from_file) - ord('a')
                from_rank = 8 - int(notation[1])
                # We don't have board state here, so just format nicely
                notation = f"{from_file}{notation[1]} → {to_file}{notation[3]}"
                if is_capture:
                    notation = notation.replace(" → ", " × ")
            except:
                pass

        enhanced.append({
            **hm,
            "notation": notation,
        })
    return enhanced


def _generate_board_snapshots(sess):
    """
    Replay the session's game from the start and capture board state after each move.
    Returns list of board grids: [initial_state, after_move_1, after_move_2, ...]
    """
    # Create a fresh engine at the starting position
    test_engine = _HeadlessEngine()
    snapshots = [board_to_grid(test_engine)]  # snapshot 0: initial empty board

    # Replay each move pair (piece + duck) from the halfmoves history
    move_index = 0
    while move_index < len(sess.halfmoves):
        hm = sess.halfmoves[move_index]

        # Extract piece move coordinates (format: "a1b2 ...")
        move_str = hm["text"]
        if len(move_str) < 4:
            move_index += 1
            continue

        try:
            # Parse algebraic notation: "e2e4" style or with duck emoji
            frm_file = ord(move_str[0]) - ord('a')
            frm_rank = 8 - int(move_str[1])
            to_file = ord(move_str[2]) - ord('a')
            to_rank = 8 - int(move_str[3])

            # Execute piece move
            test_engine.execute_move((frm_rank, frm_file), (to_rank, to_file), animated=False)
            snapshots.append(board_to_grid(test_engine))  # board after piece move

            # Find duck position in the move text (marked by duck emoji 🦆 or @)
            if "🦆" in move_str or "@" in move_str:
                # Duck move is present; extract coordinates
                duck_coords = None
                for i, c in enumerate(move_str):
                    if c in "abcdefgh" and i + 1 < len(move_str) and move_str[i + 1] in "12345678":
                        duck_file = ord(c) - ord('a')
                        duck_rank = 8 - int(move_str[i + 1])
                        duck_coords = (duck_rank, duck_file)
                        break

                if duck_coords:
                    test_engine.place_duck(duck_coords, animated=False)
                    snapshots.append(board_to_grid(test_engine))  # board after duck move
        except (ValueError, IndexError):
            pass  # Skip malformed moves

        move_index += 1

    return snapshots


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
    # For 2-player games, there's no model
    if sess.model_id is None:
        return None
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
    model: Optional[str] = "stage12"  # None for 2-player local games
    color: str = "white"              # 'white' | 'black'


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


class SaveGameReq(BaseModel):
    game_id: str
    username: str
    label: str                     # user-provided name for the game


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
    print(f"DEBUG: new_game called with model={req.model!r} (type: {type(req.model).__name__})")
    player_color = "w" if req.color == "white" else "b"

    # Handle 2-player local game (no model)
    if req.model is None:
        engine = _HeadlessEngine()
        sess = Session(engine, player_color, None, "2 Players")
        gid = uuid.uuid4().hex[:12]
        SESSIONS[gid] = sess
        state = serialize(sess)
        state["gameId"] = gid
        return state

    # vs-model game
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
        is_2player = sess.model_id is None
        print(f"DEBUG legal_moves: is_2player={is_2player}, model_id={sess.model_id!r}, e.turn={e.turn}, req r={req.r} c={req.c}")
        if e.game_over or e.phase != "move_piece":
            print(f"  -> game_over or wrong phase, returning empty")
            return {"moves": []}
        # In 2-player, allow any pieces; in vs-model, only player's pieces
        if not is_2player and e.turn != sess.player_color:
            print(f"  -> vs-model and not your turn, returning empty")
            return {"moves": []}
        p = e.board[req.r][req.c]
        required_color = e.turn if is_2player else sess.player_color
        print(f"  -> piece={p}, required_color={required_color}, piece.color={p.color if p else None}")
        if p is None or p.color != required_color:
            print(f"  -> no piece or wrong color, returning empty")
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
        # For 2-player games, allow moves from both colors
        is_2player = sess.model_id is None
        if not is_2player and e.turn != sess.player_color:
            raise HTTPException(400, "Not your turn.")
        if e.phase != "move_piece":
            raise HTTPException(400, "Not your move-piece phase.")
        frm = (int(req.frm[0]), int(req.frm[1]))
        to = (int(req.to[0]), int(req.to[1]))
        p = e.board[frm[0]][frm[1]]
        # In 2-player, allow piece of whose turn it is; in vs-model, only player's color
        required_color = e.turn if is_2player else sess.player_color
        if p is None or p.color != required_color:
            raise HTTPException(400, "No piece of yours on the start square.")
        legal = e.get_piece_legal_moves(frm[0], frm[1])
        if to not in legal:
            raise HTTPException(400, "Illegal move for that piece.")

        moving_player = e.turn  # Save whose turn it is before we execute
        e.execute_move(frm, to, animated=False)
        sess.pending = (frm, to)

        if getattr(e, "game_over", False):     # king captured -> instant win
            sess.halfmoves.append({"color": moving_player, "text": f"{sq(frm)}{sq(to)}#"})
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
        # For 2-player games, allow moves from both colors
        is_2player = sess.model_id is None
        if not is_2player and e.turn != sess.player_color:
            raise HTTPException(400, "Not your turn.")
        if e.phase != "move_duck":
            raise HTTPException(400, "Not your move-duck phase.")
        duck = (int(req.duck[0]), int(req.duck[1]))
        valid = {tuple(x) for x in valid_duck_squares(e)}
        if duck not in valid:
            raise HTTPException(400, "Illegal duck square.")

        moving_player = e.turn  # Save whose turn it is before we execute
        e.place_duck(duck, animated=False)

        frm, to = sess.pending if sess.pending else ((0, 0), (0, 0))
        sess.pending = None
        sess.halfmoves.append(
            {"color": moving_player, "text": f"{sq(frm)}{sq(to)} {DUCK}{sq(duck)}"}
        )
        player_move = {"from": list(frm), "to": list(to), "duck": list(duck)}

        ai_move = None
        if not getattr(e, "game_over", False) and sess.model_id is not None:
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


# ---------------------------------------------------------------------------
# Save & Load Games
# ---------------------------------------------------------------------------

@app.post("/api/save-game")
def save_game(req: SaveGameReq):
    """Save a game to disk as JSON. Returns filename."""
    sess = _get_session(req.game_id)

    # Create save directory if needed
    save_dir = ROOT / "saved_replays"
    save_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().isoformat().replace(":", "-").split(".")[0]
    filename = f"{req.username}_{timestamp}.json"
    filepath = save_dir / filename

    # Serialize full game state
    e = sess.engine
    with sess.lock:
        # Generate board snapshots: one for each move in history
        snapshots = _generate_board_snapshots(sess)
        # Enhance history with notation
        history_with_notation = _enhance_history_with_notation(e, sess.halfmoves)

        game_data = {
            "label": req.label,
            "username": req.username,
            "timestamp": timestamp,
            "model_label": sess.model_label,
            "player_color": sess.player_color,
            "model_color": sess.model_color,
            "board": board_to_grid(e),
            "duck": list(e.duck_pos) if tuple(e.duck_pos) != (-1, -1) else None,
            "history": history_with_notation,
            "board_snapshots": snapshots,
            "game_over": getattr(e, "game_over", False),
            "winner": getattr(e, "winner", None),
        }

    with open(filepath, "w") as f:
        json.dump(game_data, f, indent=2)

    return {"filename": filename, "message": "Game saved successfully"}


@app.get("/api/saved-games")
def list_saved_games(username: str):
    """List saved games for a user."""
    save_dir = ROOT / "saved_replays"
    if not save_dir.exists():
        return {"games": []}

    games = []
    for f in sorted(save_dir.glob(f"{username}_*.json"), reverse=True):
        try:
            with open(f) as fp:
                data = json.load(fp)
            games.append({
                "filename": f.name,
                "label": data.get("label", "Unnamed"),
                "timestamp": data.get("timestamp", ""),
                "model_label": data.get("model_label", ""),
                "result": "Won" if (data.get("winner") == data.get("player_color")) else
                          "Lost" if data.get("game_over") else "In Progress",
            })
        except (json.JSONDecodeError, KeyError):
            pass  # Skip corrupt files

    return {"games": games}


@app.get("/api/load-game/{filename}")
def load_game(filename: str):
    """Load a saved game. Reconstructs board snapshots if missing."""
    save_dir = ROOT / "saved_replays"
    filepath = save_dir / filename

    if not filepath.exists():
        raise HTTPException(404, "Game file not found")

    try:
        with open(filepath) as f:
            game_data = json.load(f)

        # Reconstruct snapshots if missing (for games saved before this feature)
        if "board_snapshots" not in game_data or not game_data["board_snapshots"]:
            test_engine = _HeadlessEngine()
            snapshots = [board_to_grid(test_engine)]

            # Replay moves from history
            for hm in game_data.get("history", []):
                move_str = hm.get("text", "")
                if len(move_str) < 4:
                    continue

                try:
                    frm_file = ord(move_str[0]) - ord('a')
                    frm_rank = 8 - int(move_str[1])
                    to_file = ord(move_str[2]) - ord('a')
                    to_rank = 8 - int(move_str[3])

                    test_engine.execute_move((frm_rank, frm_file), (to_rank, to_file), animated=False)
                    snapshots.append(board_to_grid(test_engine))

                    if "🦆" in move_str or "@" in move_str:
                        for i, c in enumerate(move_str):
                            if c in "abcdefgh" and i + 1 < len(move_str) and move_str[i + 1] in "12345678":
                                duck_file = ord(c) - ord('a')
                                duck_rank = 8 - int(move_str[i + 1])
                                test_engine.place_duck((duck_rank, duck_file), animated=False)
                                snapshots.append(board_to_grid(test_engine))
                                break
                except (ValueError, IndexError):
                    pass

            game_data["board_snapshots"] = snapshots

        return game_data
    except json.JSONDecodeError:
        raise HTTPException(400, "Corrupt game file")


# Static files LAST so /api/* routes win.  html=True -> "/" serves index.html.
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    print(f"[Duck Chess] models available: {[m['id'] for m in MODEL_CHOICES]}")
    uvicorn.run(app, host="127.0.0.1", port=7890)
