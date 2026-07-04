"""
CHARACTERIZATION tests for Logic/ termination & encoding behaviour that the
existing 'comprehensive' suite left as empty stubs (test_king_capture_ends_game,
test_fowling_rule_no_legal_moves_wins were comment-only and asserted nothing).

These LOCK current behaviour — they do not change it. Positions are built with
clear_board() (which resets the 2D board AND the bitboards together) plus a small
synced _place() helper, so the dual board representation stays consistent.

Action-mask invariants and observation shape/dtype are already strongly covered
by test_action_masker.py and test_observation_encoder.py and are not duplicated;
the 50-move draw is locked in test_game_over_reason.py.
"""
import numpy as np
import pytest

from DuckChess_Game.SBThree.base.env_base import _HeadlessEngine
from DuckChess_Game.Logic.pieces import Piece
from DuckChess_Game.Logic.constants import KING, ROOK


@pytest.fixture
def eng():
    return _HeadlessEngine()


def _place(engine, color, ptype, r, c):
    """Place a piece on BOTH the 2D board and the bitboards (keep them in sync)."""
    engine.board[r][c] = Piece(color, ptype)
    if getattr(engine, "bb_mgr", None) is not None:
        engine.bb_mgr.add_piece(color, ptype, r, c)


def _empty_position(engine, turn="w"):
    engine.clear_board()
    engine.phase = "move_piece"
    engine.game_over = False
    engine.winner = None
    engine.turn = turn


# ── King capture ends the game; winner is the capturing side ───────────────

def test_king_capture_ends_game_white_wins(eng):
    _empty_position(eng, turn="w")
    _place(eng, "w", KING, 7, 4)      # white king e1
    _place(eng, "b", KING, 0, 0)      # black king a8 (about to be captured)
    _place(eng, "w", ROOK, 7, 0)      # white rook a1, clear file to a8
    eng.execute_move((7, 0), (0, 0), animated=False)   # Rxa8 captures the black king
    assert eng.game_over is True
    assert eng.winner == "w"
    assert eng.board[0][0] is not None and eng.board[0][0].type == ROOK   # rook took the square
    # the captured king is gone from the board
    kings = [eng.board[r][c] for r in range(8) for c in range(8)
             if eng.board[r][c] and eng.board[r][c].type == KING]
    assert all(k.color == "w" for k in kings)


def test_king_capture_winner_is_capturing_side_black(eng):
    _empty_position(eng, turn="b")
    _place(eng, "b", KING, 0, 4)      # black king e8
    _place(eng, "w", KING, 7, 7)      # white king h1 (about to be captured)
    _place(eng, "b", ROOK, 0, 7)      # black rook h8, clear file to h1
    eng.execute_move((0, 7), (7, 7), animated=False)   # Rxh1 captures the white king
    assert eng.game_over is True
    assert eng.winner == "b"


# ── Fowling: the side to move with NO legal moves WINS (inverse stalemate) ──

def test_fowling_side_to_move_with_no_moves_wins_white(eng):
    # No pieces for the side to move -> zero legal moves -> that side wins.
    _empty_position(eng, turn="w")
    eng.check_game_end_conditions()
    assert eng.game_over is True
    assert eng.winner == "w"


def test_fowling_side_to_move_with_no_moves_wins_black(eng):
    _empty_position(eng, turn="b")
    eng.check_game_end_conditions()
    assert eng.game_over is True
    assert eng.winner == "b"


def test_no_termination_when_side_to_move_has_moves(eng):
    # Sanity counter-case: a normal start position is NOT game over.
    eng.check_game_end_conditions()
    assert eng.game_over is False
    assert eng.winner is None


# ── Duck placement legality at the engine level ────────────────────────────

def test_place_duck_noop_on_occupied_square(eng):
    eng.execute_move((6, 4), (4, 4), animated=False)   # e2->e4, now in move_duck phase
    assert eng.phase == "move_duck"
    before = tuple(eng.duck_pos)
    eng.place_duck((6, 0), animated=False)             # a2 is still occupied by a pawn
    # rejected: phase and duck unchanged
    assert eng.phase == "move_duck"
    assert tuple(eng.duck_pos) == before
    # a legal empty square is accepted and completes the turn
    eng.place_duck((5, 0), animated=False)             # a3 is empty
    assert eng.phase == "move_piece"
    assert tuple(eng.duck_pos) == (5, 0)


# ── Observation tensor value range (shape/dtype covered elsewhere) ─────────

def test_observation_values_in_unit_range(eng):
    obs = eng._get_obs()
    assert obs.shape == (19, 8, 8)
    assert obs.dtype == np.float32
    assert float(obs.min()) >= 0.0
    assert float(obs.max()) <= 1.0
