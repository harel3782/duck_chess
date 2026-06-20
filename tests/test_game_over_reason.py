"""
Game-over REASON logic in web_ui/server.py: game_over_reason() and the `reason`
field on serialized state. Reasons: king_capture / fowling / resign / draw_50move.

The backend reason is symmetric (same string regardless of who won); the human
WIN vs LOSS wording is decided in the frontend (reasonText/reason2Player in
index.html) and is only reachable via the browser/E2E tests.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from web_ui.server import app, SESSIONS, Session, serialize, game_over_reason
from DuckChess_Game.SBThree.base.env_base import _HeadlessEngine

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_sessions():
    SESSIONS.clear()
    yield
    SESSIONS.clear()


def _remove_king(engine, color):
    for r in range(8):
        for c in range(8):
            p = engine.board[r][c]
            if p is not None and p.type == "K" and p.color == color:
                engine.board[r][c] = None


# ── game_over_reason() helper, direct ──────────────────────────────────────

def test_reason_none_when_not_over():
    assert game_over_reason(_HeadlessEngine()) is None


def test_reason_override_resign_takes_precedence():
    e = _HeadlessEngine()
    assert game_over_reason(e, "resign") == "resign"
    e.game_over, e.winner = True, "w"          # even over a finished board
    assert game_over_reason(e, "resign") == "resign"


def test_reason_draw_50move():
    e = _HeadlessEngine()
    e.game_over, e.winner = True, "draw"
    assert game_over_reason(e) == "draw_50move"


def test_reason_king_capture_white_wins():
    e = _HeadlessEngine()
    e.game_over, e.winner = True, "w"
    _remove_king(e, "b")                        # black king captured -> white won
    assert game_over_reason(e) == "king_capture"


def test_reason_king_capture_black_wins():
    e = _HeadlessEngine()
    e.game_over, e.winner = True, "b"
    _remove_king(e, "w")                        # white king captured -> black won
    assert game_over_reason(e) == "king_capture"


def test_reason_fowling_white_wins():
    e = _HeadlessEngine()
    e.game_over, e.winner = True, "w"           # both kings still present -> fowling
    assert game_over_reason(e) == "fowling"


def test_reason_fowling_black_wins():
    e = _HeadlessEngine()
    e.game_over, e.winner = True, "b"
    assert game_over_reason(e) == "fowling"


# ── reason flows through serialize / endpoints ─────────────────────────────

def test_draw_50move_propagates_through_serialize():
    e = _HeadlessEngine()
    e.half_move_clock = 100
    e.check_game_end_conditions()              # engine auto-detects the 50-move draw
    assert e.game_over and e.winner == "draw"
    state = serialize(Session(e, "w", None, "2 Players"))
    assert state["winner"] == "draw"
    assert state["reason"] == "draw_50move"


def test_resign_endpoint_sets_reason_and_winner():
    gid = client.post("/api/new-game", json={"color": "white", "model": None}).json()["gameId"]
    state = client.post("/api/resign", json={"game_id": gid, "r": 0, "c": 0}).json()
    assert state["gameOver"] is True
    assert state["reason"] == "resign"
    assert state["message"] == "resign"
    assert state["winner"] == "b"              # white resigned -> black wins


def test_fresh_game_reason_is_none():
    ng = client.post("/api/new-game", json={"color": "white", "model": None}).json()
    assert ng["gameOver"] is False
    assert ng["reason"] is None
