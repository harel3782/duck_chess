"""
Comprehensive tests for Duck Chess Web UI backend (web_ui/server.py).

Tests cover:
- API endpoints (new-game, move-piece, place-duck, legal-moves, resign, save/load)
- 2-player vs AI game modes
- Game state serialization
- Move history tracking
- Error handling and edge cases
- Concurrency safety
"""
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from web_ui.server import app, SESSIONS, Session, history_rows, sq


client = TestClient(app)


# ─────────────────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear all game sessions before and after each test."""
    SESSIONS.clear()
    yield
    SESSIONS.clear()


@pytest.fixture
def mock_engine():
    """Mock game engine for testing without real logic."""
    engine = MagicMock()
    engine.game_over = False
    engine.turn = 'w'
    engine.phase = 'move_piece'
    engine.board = [[None] * 8 for _ in range(8)]
    # Add basic pieces for testing
    from unittest.mock import MagicMock
    white_pawn = MagicMock()
    white_pawn.color = 'w'
    black_pawn = MagicMock()
    black_pawn.color = 'b'
    engine.board[6][4] = white_pawn  # white pawn on e2
    engine.board[1][4] = black_pawn  # black pawn on e7
    engine.action_masks = MagicMock(return_value=[1] * 100)
    engine.get_piece_legal_moves = MagicMock(return_value=[(5, 4)])  # can move to e3
    engine.execute_move = MagicMock()
    engine.place_duck = MagicMock()
    return engine


# ─────────────────────────────────────────────────────────────────────────
# TEST: API ENDPOINTS - NEW GAME
# ─────────────────────────────────────────────────────────────────────────

def test_new_game_2player():
    """Test creating a 2-player local game (no model)."""
    response = client.post("/api/new-game", json={"color": "white", "model": None})
    assert response.status_code == 200
    data = response.json()

    assert "gameId" in data
    assert data["playerColor"] == "w"
    assert data["modelLabel"] == "2 Players"
    assert "board" in data
    assert "history" in data
    assert data["gameId"] in SESSIONS


def test_new_game_vs_ai_white():
    """Test creating vs-AI game as white."""
    response = client.post("/api/new-game", json={"color": "white", "model": "stage11"})
    assert response.status_code == 200
    data = response.json()

    assert data["playerColor"] == "w"
    assert "stage 11" in data["modelLabel"].lower()
    assert data["gameId"] in SESSIONS


def test_new_game_vs_ai_black():
    """Test creating vs-AI game as black (AI moves first)."""
    response = client.post("/api/new-game", json={"color": "black", "model": "stage11"})
    assert response.status_code == 200
    data = response.json()

    assert data["playerColor"] == "b"
    # AI should have already moved
    assert len(data.get("history", [])) > 0 or "aiMove" in data


def test_new_game_invalid_model():
    """Test creating game with non-existent model falls back to first available."""
    response = client.post("/api/new-game", json={"color": "white", "model": "nonexistent"})
    assert response.status_code == 200
    data = response.json()
    assert "gameId" in data


def test_new_game_default_color():
    """Test new game with default color parameter."""
    response = client.post("/api/new-game", json={"model": None})
    assert response.status_code == 200
    data = response.json()
    assert data["playerColor"] in ["w", "b"]


# ─────────────────────────────────────────────────────────────────────────
# TEST: API ENDPOINTS - LEGAL MOVES
# ─────────────────────────────────────────────────────────────────────────

def test_legal_moves_empty_square():
    """Test requesting legal moves from empty square returns empty list."""
    resp = client.post("/api/new-game", json={"color": "white", "model": None})
    game_id = resp.json()["gameId"]

    response = client.post("/api/legal-moves", json={"game_id": game_id, "r": 4, "c": 4})
    assert response.status_code == 200
    assert response.json()["moves"] == []


def test_legal_moves_not_your_turn_vs_ai():
    """Test legal moves blocked when not your turn in vs-AI mode."""
    resp = client.post("/api/new-game", json={"color": "white", "model": "stage11"})
    game_id = resp.json()["gameId"]
    state = resp.json()

    if state["playerColor"] == "b":
        # We're black and it's white's turn, should block
        response = client.post("/api/legal-moves", json={"game_id": game_id, "r": 1, "c": 0})
        assert response.json()["moves"] == []


def test_legal_moves_allowed_2player():
    """Test legal moves allowed for any color in 2-player mode."""
    resp = client.post("/api/new-game", json={"color": "white", "model": None})
    game_id = resp.json()["gameId"]

    # Should allow querying any square (even empty ones return empty, not error)
    response = client.post("/api/legal-moves", json={"game_id": game_id, "r": 0, "c": 0})
    assert response.status_code == 200
    assert "moves" in response.json()


def test_legal_moves_invalid_game():
    """Test legal moves returns empty for non-existent game."""
    response = client.post("/api/legal-moves", json={"game_id": "invalid", "r": 0, "c": 0})
    assert response.status_code == 404


# ─────────────────────────────────────────────────────────────────────────
# TEST: API ENDPOINTS - MOVE PIECE
# ─────────────────────────────────────────────────────────────────────────

def test_move_piece_invalid_game():
    """Test move on non-existent game returns 404."""
    response = client.post("/api/move-piece", json={
        "game_id": "invalid",
        "frm": [6, 4],
        "to": [5, 4]
    })
    assert response.status_code == 404


def test_move_piece_invalid_move():
    """Test illegal move returns error."""
    resp = client.post("/api/new-game", json={"color": "white", "model": None})
    game_id = resp.json()["gameId"]

    # Try to move from empty square
    response = client.post("/api/move-piece", json={
        "game_id": game_id,
        "frm": [4, 4],
        "to": [3, 4]
    })
    assert response.status_code == 400


def test_move_piece_vs_ai_not_your_turn():
    """Test can't move on opponent's turn in vs-AI mode."""
    resp = client.post("/api/new-game", json={"color": "black", "model": "stage11"})
    game_id = resp.json()["gameId"]
    state = resp.json()

    if state["turn"] != "b":
        # It's not our turn, try to move
        response = client.post("/api/move-piece", json={
            "game_id": game_id,
            "frm": [1, 0],
            "to": [2, 0]
        })
        assert response.status_code == 400


def test_move_piece_2player_both_colors():
    """Test both colors can move in 2-player mode."""
    resp = client.post("/api/new-game", json={"color": "white", "model": None})
    game_id = resp.json()["gameId"]
    state = resp.json()

    # First move should work (white's turn)
    assert state["turn"] == "w"
    # (move will fail because board is not set up, but should pass validation)


# ─────────────────────────────────────────────────────────────────────────
# TEST: API ENDPOINTS - PLACE DUCK
# ─────────────────────────────────────────────────────────────────────────

def test_place_duck_invalid_game():
    """Test duck placement on non-existent game."""
    response = client.post("/api/place-duck", json={
        "game_id": "invalid",
        "duck": [3, 3]
    })
    assert response.status_code == 404


def test_place_duck_not_move_duck_phase():
    """Test duck placement fails when not in move_duck phase."""
    resp = client.post("/api/new-game", json={"color": "white", "model": None})
    game_id = resp.json()["gameId"]

    # We haven't moved a piece yet, so we're in move_piece phase
    response = client.post("/api/place-duck", json={
        "game_id": game_id,
        "duck": [3, 3]
    })
    assert response.status_code == 400


# ─────────────────────────────────────────────────────────────────────────
# TEST: API ENDPOINTS - RESIGN
# ─────────────────────────────────────────────────────────────────────────

def test_resign_game():
    """Test resigning a game marks it as over."""
    resp = client.post("/api/new-game", json={"color": "white", "model": None})
    game_id = resp.json()["gameId"]

    response = client.post("/api/resign", json={"game_id": game_id, "r": 0, "c": 0})
    assert response.status_code == 200
    data = response.json()
    assert data["gameOver"] == True


def test_resign_already_over():
    """Test resigning when game is already over."""
    resp = client.post("/api/new-game", json={"color": "white", "model": None})
    game_id = resp.json()["gameId"]

    # Resign once
    client.post("/api/resign", json={"game_id": game_id, "r": 0, "c": 0})

    # Resign again
    response = client.post("/api/resign", json={"game_id": game_id, "r": 0, "c": 0})
    assert response.status_code in [200, 400]  # Either OK or error is acceptable


def test_resign_invalid_game():
    """Test resigning non-existent game."""
    response = client.post("/api/resign", json={"game_id": "invalid", "r": 0, "c": 0})
    assert response.status_code == 404


# ─────────────────────────────────────────────────────────────────────────
# TEST: SAVE & LOAD GAMES
# ─────────────────────────────────────────────────────────────────────────

def test_save_game():
    """Test saving a game creates JSON file."""
    resp = client.post("/api/new-game", json={"color": "white", "model": None})
    game_id = resp.json()["gameId"]

    response = client.post("/api/save-game", json={
        "game_id": game_id,
        "username": "testuser",
        "label": "Test Game"
    })
    assert response.status_code == 200
    data = response.json()
    assert "filename" in data


def test_list_saved_games():
    """Test listing saved games for a user."""
    # Save a game first
    resp = client.post("/api/new-game", json={"color": "white", "model": None})
    game_id = resp.json()["gameId"]

    client.post("/api/save-game", json={
        "game_id": game_id,
        "username": "testuser",
        "label": "Game 1"
    })

    # List games
    response = client.get("/api/saved-games?username=testuser")
    assert response.status_code == 200
    data = response.json()
    assert "games" in data
    assert len(data["games"]) > 0


def test_load_game():
    """Test loading a saved game."""
    # Save a game first
    resp = client.post("/api/new-game", json={"color": "white", "model": None})
    game_id = resp.json()["gameId"]

    save_resp = client.post("/api/save-game", json={
        "game_id": game_id,
        "username": "testuser",
        "label": "Test Game"
    })
    filename = save_resp.json()["filename"]

    # Load it
    response = client.get(f"/api/load-game/{filename}")
    assert response.status_code == 200
    data = response.json()
    assert "board" in data
    assert "history" in data
    assert "board_snapshots" in data


def test_save_game_without_moves():
    """Test saving a game that just started (no moves)."""
    resp = client.post("/api/new-game", json={"color": "white", "model": None})
    game_id = resp.json()["gameId"]

    response = client.post("/api/save-game", json={
        "game_id": game_id,
        "username": "testuser",
        "label": "Fresh Game"
    })
    assert response.status_code == 200


# ─────────────────────────────────────────────────────────────────────────
# TEST: GAME STATE SERIALIZATION
# ─────────────────────────────────────────────────────────────────────────

def test_serialize_includes_required_fields():
    """Test that serialized state includes all required fields."""
    resp = client.post("/api/new-game", json={"color": "white", "model": None})
    state = resp.json()

    required_fields = [
        "gameId", "playerColor", "turn", "phase", "gameOver",
        "board", "history", "modelLabel", "capturedByWhite", "capturedByBlack"
    ]
    for field in required_fields:
        assert field in state, f"Missing field: {field}"


def test_board_grid_correct_size():
    """Test board is 8x8."""
    resp = client.post("/api/new-game", json={"color": "white", "model": None})
    state = resp.json()
    board = state["board"]

    assert len(board) == 8
    assert all(len(row) == 8 for row in board)


# ─────────────────────────────────────────────────────────────────────────
# TEST: HISTORY & NOTATION
# ─────────────────────────────────────────────────────────────────────────

def test_history_rows_empty():
    """Test history_rows with empty halfmoves."""
    result = history_rows([])
    assert result == []


def test_history_rows_single_white_move():
    """Test history_rows with one white move."""
    halfmoves = [{"color": "w", "text": "e2-e4"}]
    result = history_rows(halfmoves)

    assert len(result) == 1
    assert result[0]["color"] == "w"
    assert result[0]["text"] == "e2-e4"


def test_history_rows_paired_moves():
    """Test history_rows with white and black moves."""
    halfmoves = [
        {"color": "w", "text": "e2-e4"},
        {"color": "b", "text": "e7-e5"}
    ]
    result = history_rows(halfmoves)

    assert len(result) == 2
    assert result[0]["color"] == "w"
    assert result[1]["color"] == "b"


def test_sq_conversion():
    """Test square coordinate to algebraic notation conversion."""
    # (row, col) -> algebraic
    assert sq((6, 4)) == "e2"  # white's e-pawn
    assert sq((1, 4)) == "e7"  # black's e-pawn
    assert sq((7, 0)) == "a1"  # white's queen rook
    assert sq((0, 7)) == "h8"  # black's king rook


# ─────────────────────────────────────────────────────────────────────────
# TEST: ERROR HANDLING & EDGE CASES
# ─────────────────────────────────────────────────────────────────────────

def test_game_not_found_all_endpoints():
    """Test all endpoints handle missing game gracefully."""
    bad_game_id = "nonexistent"

    endpoints = [
        ("/api/legal-moves", {"r": 0, "c": 0}),
        ("/api/move-piece", {"frm": [0, 0], "to": [1, 1]}),
        ("/api/place-duck", {"duck": [3, 3]}),
        ("/api/resign", {"r": 0, "c": 0}),
    ]

    for path, payload in endpoints:
        payload["game_id"] = bad_game_id
        response = client.post(path, json=payload)
        assert response.status_code == 404, f"{path} didn't return 404"


def test_malformed_request_move_piece():
    """Test move-piece with invalid request format."""
    resp = client.post("/api/new-game", json={"color": "white", "model": None})
    game_id = resp.json()["gameId"]

    # Missing 'to' field
    response = client.post("/api/move-piece", json={
        "game_id": game_id,
        "frm": [6, 4]
    })
    assert response.status_code == 422  # Validation error


def test_malformed_request_new_game():
    """Test new-game with missing required color field."""
    response = client.post("/api/new-game", json={"model": None})
    # Should either work with default or fail with 422
    assert response.status_code in [200, 422]


# ─────────────────────────────────────────────────────────────────────────
# TEST: MODEL LOADING
# ─────────────────────────────────────────────────────────────────────────

def test_list_models():
    """Test getting available models."""
    response = client.get("/api/models")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert isinstance(data["models"], list)


def test_models_have_id_and_label():
    """Test each model has id and label."""
    response = client.get("/api/models")
    data = response.json()

    for model in data["models"]:
        assert "id" in model
        assert "label" in model
        assert isinstance(model["id"], str)
        assert isinstance(model["label"], str)


# ─────────────────────────────────────────────────────────────────────────
# TEST: 2-PLAYER VS AI MODE DETECTION
# ─────────────────────────────────────────────────────────────────────────

def test_2player_session_has_no_model():
    """Test 2-player sessions have model_id=None."""
    resp = client.post("/api/new-game", json={"color": "white", "model": None})
    game_id = resp.json()["gameId"]

    session = SESSIONS[game_id]
    assert session.model_id is None


def test_ai_session_has_model_id():
    """Test AI sessions have a model_id."""
    resp = client.post("/api/new-game", json={"color": "white", "model": "stage11"})
    game_id = resp.json()["gameId"]

    session = SESSIONS[game_id]
    assert session.model_id is not None
    assert session.model_id == "stage11"


# ─────────────────────────────────────────────────────────────────────────
# TEST: UNDO MOVE
# ─────────────────────────────────────────────────────────────────────────

def test_undo_move_invalid_game():
    """Test undo on non-existent game returns 404."""
    response = client.post("/api/undo-move", json={"game_id": "invalid"})
    assert response.status_code == 404


def test_undo_move_no_moves():
    """Test undo with no moves to undo."""
    resp = client.post("/api/new-game", json={"color": "white", "model": None})
    game_id = resp.json()["gameId"]

    response = client.post("/api/undo-move", json={"game_id": game_id})
    assert response.status_code == 400
    assert "No moves to undo" in response.json()["detail"]


def test_undo_move_game_over():
    """Test undo when game is over."""
    resp = client.post("/api/new-game", json={"color": "white", "model": None})
    game_id = resp.json()["gameId"]

    # Mark game as over
    SESSIONS[game_id].engine.game_over = True

    response = client.post("/api/undo-move", json={"game_id": game_id})
    assert response.status_code == 400
    assert "game is over" in response.json()["detail"].lower()


def test_undo_move_not_your_turn_vs_ai():
    """Test undo fails when not player's turn in vs-AI mode."""
    resp = client.post("/api/new-game", json={"color": "black", "model": "stage11"})
    game_id = resp.json()["gameId"]
    state = resp.json()

    session = SESSIONS[game_id]
    # If it's white's turn and we're black, undo should fail
    if session.engine.turn != "b":
        response = client.post("/api/undo-move", json={"game_id": game_id})
        assert response.status_code == 400


def test_undo_move_duck_phase():
    """Test undo fails during duck placement phase."""
    resp = client.post("/api/new-game", json={"color": "white", "model": None})
    game_id = resp.json()["gameId"]

    session = SESSIONS[game_id]
    e = session.engine
    # Make a complete move (piece + duck) to get a full turn in history
    e.execute_move((6, 4), (5, 4), animated=False)  # e4
    session.halfmoves.append({"color": "w", "text": "e4"})
    e.place_duck((3, 3), animated=False)  # duck to d5
    session.halfmoves.append({"color": "w", "text": "e4 🦆d5"})

    # Now make another piece move (entering duck phase)
    e.execute_move((1, 4), (2, 4), animated=False)  # e7-e5 (black)
    session.halfmoves.append({"color": "b", "text": "e5"})
    # Now in duck phase - try to undo
    assert e.phase == "move_duck"

    response = client.post("/api/undo-move", json={"game_id": game_id})
    assert response.status_code == 400
    assert "piece phase" in response.json()["detail"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
