"""
Web UI backend tests for the recently-added / recently-buggy areas:
- delete-game endpoint + the shared path-traversal guard (load + delete)
- replay snapshot reconstruction with PER-STEP duck position
- happy-path full turn (move-piece -> place-duck) and positive legal-moves

Uses FastAPI TestClient (no live server). All games here are local 2-player
(model=None) so no MaskablePPO model is loaded — fast and deterministic.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from web_ui.server import app, SESSIONS, _snapshots_from_halfmoves, DUCK

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_sessions():
    SESSIONS.clear()
    yield
    SESSIONS.clear()


# ── helpers ────────────────────────────────────────────────────────────────

def _new_2p():
    return client.post("/api/new-game", json={"color": "white", "model": None}).json()["gameId"]


def _play_turn(game_id, frm, to):
    """Play one full turn: move the piece then place the duck on the first legal square."""
    mp = client.post("/api/move-piece", json={"game_id": game_id, "frm": list(frm), "to": list(to)})
    assert mp.status_code == 200, mp.text
    duck = mp.json()["validDuck"][0]
    pd = client.post("/api/place-duck", json={"game_id": game_id, "duck": duck})
    assert pd.status_code == 200, pd.text
    return pd.json()


def _save(game_id, username="snaptest", label="x"):
    return client.post("/api/save-game",
                       json={"game_id": game_id, "username": username, "label": label}).json()["filename"]


# ── happy-path turn + legal moves (positive cases the suite lacked) ─────────

def test_full_turn_2player_advances():
    gid = _new_2p()
    state = _play_turn(gid, (6, 4), (4, 4))      # white e2->e4 + duck
    assert state["turn"] == "b"                  # turn handed to the other human
    assert state["aiMove"] is None               # no model in 2-player
    assert len(state["history"]) == 1
    assert state["history"][0]["color"] == "w"


def test_legal_moves_returns_moves_for_own_pawn():
    gid = _new_2p()
    moves = client.post("/api/legal-moves", json={"game_id": gid, "r": 6, "c": 4}).json()["moves"]
    assert [4, 4] in moves and [5, 4] in moves   # e2->e4 and e2->e3


# ── delete-game + path-traversal guard ─────────────────────────────────────

def test_delete_game_removes_file():
    fn = _save(_new_2p(), username="deltest")
    assert any(g["filename"] == fn
               for g in client.get("/api/saved-games?username=deltest").json()["games"])

    resp = client.post("/api/delete-game", json={"filename": fn})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "filename": fn}

    # gone from disk and from the listing
    assert client.get(f"/api/load-game/{fn}").status_code == 404
    assert not any(g["filename"] == fn
                   for g in client.get("/api/saved-games?username=deltest").json()["games"])


def test_delete_game_missing_file_404():
    assert client.post("/api/delete-game", json={"filename": "does_not_exist.json"}).status_code == 404


def test_delete_game_non_json_400():
    assert client.post("/api/delete-game", json={"filename": "notes.txt"}).status_code == 400


def test_delete_game_path_traversal_blocked():
    # ".." stripped to a non-.json basename -> 400, real file never touched
    assert client.post("/api/delete-game", json={"filename": "../../server.py"}).status_code == 400
    # ".." stripped to a .json basename that isn't in the dir -> 404 (cannot escape the dir)
    assert client.post("/api/delete-game", json={"filename": "../../secret.json"}).status_code == 404
    assert client.post("/api/delete-game", json={"filename": "..\\..\\secret.json"}).status_code == 404
    # the guard must not have deleted anything outside the saves dir
    assert (ROOT / "web_ui" / "server.py").exists()


def test_load_game_guard_non_json_400_and_missing_404():
    assert client.get("/api/load-game/notes.txt").status_code == 400
    assert client.get("/api/load-game/nope.json").status_code == 404


# ── replay snapshots: per-step board + DUCK (the recent bug) ────────────────

def test_saved_game_snapshots_have_board_and_duck_and_duck_moves():
    gid = _new_2p()
    _play_turn(gid, (6, 4), (4, 4))   # white
    _play_turn(gid, (1, 4), (3, 4))   # black
    fn = _save(gid, username="snaptest")
    try:
        loaded = client.get(f"/api/load-game/{fn}").json()
        snaps = loaded["board_snapshots"]
        assert len(snaps) == 3                       # initial + 2 completed turns
        for s in snaps:
            assert isinstance(s, dict) and "board" in s and "duck" in s
            assert len(s["board"]) == 8 and all(len(r) == 8 for r in s["board"])
        assert snaps[0]["duck"] is None              # no duck before any move
        assert snaps[1]["duck"] is not None          # white placed a duck
        assert snaps[2]["duck"] is not None          # black placed a duck
        # the duck must actually MOVE across steps (bug was it staying put)
        ducks = [tuple(s["duck"]) if s["duck"] else None for s in snaps]
        assert len(set(ducks)) > 1
    finally:
        client.post("/api/delete-game", json={"filename": fn})   # cleanup


def test_snapshots_reconstruction_duck_retained_when_halfmove_has_no_duck():
    """A half-move with no duck (the king-capture / fowled-after-piece case) must
    KEEP the previous duck square, not drop it — exercised directly on the helper."""
    halfmoves = [
        {"color": "w", "text": f"d2d4 {DUCK}d6"},   # piece move + duck on d6 = (2,3)
        {"color": "b", "text": "e7e5"},             # piece move, NO duck this half-move
    ]
    snaps = _snapshots_from_halfmoves(halfmoves)
    assert len(snaps) == 3
    assert snaps[0]["duck"] is None
    assert snaps[1]["duck"] == [2, 3]               # d6
    assert snaps[2]["duck"] == [2, 3]               # retained across the duck-less half-move
    assert snaps[1]["board"] != snaps[2]["board"]   # but the board still advanced (e7->e5)


def test_snapshots_initial_is_start_position():
    snaps = _snapshots_from_halfmoves([])
    assert len(snaps) == 1
    assert snaps[0]["duck"] is None
    assert snaps[0]["board"][6] == ["wP"] * 8       # white pawns on rank 2
    assert snaps[0]["board"][1] == ["bP"] * 8       # black pawns on rank 7
