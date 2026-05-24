"""Tests for GameStateValidator — stateless diagnostics on game state integrity."""
import pytest
from DuckChess_Game.Logic.game_state_validator import GameStateValidator, ValidationReport
from DuckChess_Game.Logic.bitboard_manager import BitboardManager
from DuckChess_Game.Logic.board_manager import BoardManager
from DuckChess_Game.UI.pieces import Piece
from DuckChess_Game.Logic.constants import PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING


@pytest.fixture
def validator():
    return GameStateValidator()


# ------------------------------------------------------------------ #
# ValidationReport dataclass                                           #
# ------------------------------------------------------------------ #

class TestValidationReport:
    def test_is_dataclass(self):
        r = ValidationReport(ok=True)
        assert isinstance(r, ValidationReport)
        assert r.ok is True
        assert r.issues == []
        assert r.warnings == []

    def test_with_issues(self):
        r = ValidationReport(ok=False, issues=["problem A"])
        assert not r.ok
        assert "problem A" in r.issues


# ------------------------------------------------------------------ #
# full_check on live engine                                            #
# ------------------------------------------------------------------ #

class TestFullCheck:
    def test_clean_start_passes(self, validator, engine):
        report = validator.full_check(engine)
        assert report.ok, f"Issues: {report.issues}"

    def test_no_exception_on_garbage_bb_mgr(self, validator, engine):
        """Validator must not raise even if bb_mgr is None."""
        engine.bb_mgr = None
        report = validator.full_check(engine)
        assert not report.ok
        assert len(report.issues) > 0


# ------------------------------------------------------------------ #
# validate_board_sync                                                  #
# ------------------------------------------------------------------ #

class TestBoardSync:
    def test_passes_on_starting_position(self, validator, starting_board, starting_bb):
        report = validator.validate_board_sync(starting_board, starting_bb, (-1, -1))
        assert report.ok, f"Issues: {report.issues}"

    def test_detects_extra_piece_in_bb(self, validator, starting_board, starting_bb):
        starting_bb.add_piece('w', PAWN, 3, 3)   # not on 2D board
        report = validator.validate_board_sync(starting_board, starting_bb, (-1, -1))
        assert not report.ok
        assert any("(3,3)" in i for i in report.issues)

    def test_detects_duck_pos_mismatch(self, validator, starting_board, starting_bb):
        starting_bb.move_duck(4, 4)
        # Pass duck_pos as (-1,-1) while bb has duck at (4,4)
        report = validator.validate_board_sync(starting_board, starting_bb, (-1, -1))
        assert not report.ok

    def test_passes_with_duck_synced(self, validator, starting_board, starting_bb):
        starting_bb.move_duck(4, 4)
        report = validator.validate_board_sync(starting_board, starting_bb, (4, 4))
        assert report.ok


# ------------------------------------------------------------------ #
# validate_phase_consistency                                           #
# ------------------------------------------------------------------ #

class TestPhaseConsistency:
    def test_valid_initial_state(self, validator):
        r = validator.validate_phase_consistency('move_piece', 'w', (-1, -1), (-1, -1))
        assert r.ok

    def test_invalid_phase(self, validator):
        r = validator.validate_phase_consistency('fly_duck', 'w', (-1, -1), (-1, -1))
        assert not r.ok
        assert any("phase" in i.lower() for i in r.issues)

    def test_invalid_turn(self, validator):
        r = validator.validate_phase_consistency('move_piece', 'x', (-1, -1), (-1, -1))
        assert not r.ok
        assert any("turn" in i.lower() for i in r.issues)

    def test_duck_pos_out_of_bounds(self, validator):
        r = validator.validate_phase_consistency('move_piece', 'w', (9, 9), (-1, -1))
        assert not r.ok
        assert any("out of bounds" in i for i in r.issues)

    def test_duck_pos_negative(self, validator):
        r = validator.validate_phase_consistency('move_piece', 'w', (-2, 0), (-1, -1))
        assert not r.ok

    def test_duck_eq_prev_produces_warning(self, validator):
        r = validator.validate_phase_consistency('move_piece', 'w', (3, 3), (3, 3))
        assert r.ok          # not an error, just a warning
        assert len(r.warnings) > 0


# ------------------------------------------------------------------ #
# validate_en_passant                                                  #
# ------------------------------------------------------------------ #

class TestEnPassantValidation:
    def _board_with_pawn(self, r, c, color):
        board = [[None] * 8 for _ in range(8)]
        board[r][c] = Piece(color, PAWN)
        return board

    def test_none_ep_target_passes(self, validator):
        board = [[None] * 8 for _ in range(8)]
        r = validator.validate_en_passant(None, board)
        assert r.ok

    def test_valid_ep_at_row_5(self, validator):
        board = self._board_with_pawn(5, 5, 'w')   # white pawn adjacent
        r = validator.validate_en_passant((5, 4), board)
        assert r.ok

    def test_valid_ep_at_row_2(self, validator):
        board = self._board_with_pawn(2, 3, 'b')   # black pawn adjacent
        r = validator.validate_en_passant((2, 4), board)
        assert r.ok

    def test_ep_out_of_bounds_row(self, validator):
        board = [[None] * 8 for _ in range(8)]
        r = validator.validate_en_passant((8, 3), board)
        assert not r.ok

    def test_ep_out_of_bounds_negative(self, validator):
        board = [[None] * 8 for _ in range(8)]
        r = validator.validate_en_passant((-1, 3), board)
        assert not r.ok

    def test_ep_wrong_row_produces_issue(self, validator):
        board = [[None] * 8 for _ in range(8)]
        r = validator.validate_en_passant((3, 4), board)
        assert not r.ok

    def test_ep_no_adjacent_pawn_produces_warning(self, validator):
        board = [[None] * 8 for _ in range(8)]   # no pawns at all
        r = validator.validate_en_passant((5, 4), board)
        assert r.ok   # row is valid, just a warning
        assert len(r.warnings) > 0
