"""Tests for MovePipeline — two-phase turn orchestration, validation, and atomic safety."""
import pytest
from DuckChess_Game.Logic.move_pipeline import MovePipeline, TurnResult
from DuckChess_Game.Logic.constants import PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING
from DuckChess_Game.Logic.pieces import Piece


@pytest.fixture
def pipeline(engine):
    return MovePipeline(engine)


# ------------------------------------------------------------------ #
# TurnResult dataclass                                                 #
# ------------------------------------------------------------------ #

class TestTurnResult:
    def test_is_dataclass(self):
        r = TurnResult(ok=True)
        assert isinstance(r, TurnResult)
        assert r.ok is True
        assert r.captured_piece is None
        assert r.error is None

    def test_failure_result(self):
        r = TurnResult(ok=False, error="oops")
        assert not r.ok
        assert r.error == "oops"


# ------------------------------------------------------------------ #
# execute_full_turn — success                                          #
# ------------------------------------------------------------------ #

class TestExecuteFullTurnSuccess:
    def test_basic_pawn_move_with_duck(self, pipeline, engine):
        result = pipeline.execute_full_turn((6, 4), (4, 4), (3, 3))
        assert result.ok, f"Unexpected error: {result.error}"
        assert result.error is None

    def test_state_advances_to_black_turn(self, pipeline, engine):
        pipeline.execute_full_turn((6, 4), (4, 4), (3, 3))
        assert engine.turn == 'b'
        assert engine.phase == 'move_piece'

    def test_duck_placed_at_correct_position(self, pipeline, engine):
        pipeline.execute_full_turn((6, 4), (4, 4), (3, 3))
        assert engine.duck_pos == (3, 3)

    def test_capture_returned_in_result(self, pipeline, engine):
        # Set up: white pawn at (5,3), black pawn at (4,4) about to be captured via
        # white pawn (6,3)->(5,3)->(4,4) — easier: just place black pawn at (5,5)
        # and have white pawn at (6,4) capture it is not possible in 1 turn.
        # Instead: manually place black pawn at (5,4) and white pawn at (6,3).
        engine.board[5][4] = Piece('b', PAWN)
        engine.bb_mgr.add_piece('b', PAWN, 5, 4)
        result = pipeline.execute_full_turn((6, 3), (5, 4), (3, 3))
        assert result.ok
        assert result.captured_piece is not None
        assert result.captured_piece.color == 'b'
        assert result.captured_piece.type == PAWN


# ------------------------------------------------------------------ #
# execute_full_turn — rejections (no state mutation)                   #
# ------------------------------------------------------------------ #

class TestExecuteFullTurnRejections:
    def test_wrong_phase_rejected(self, pipeline, engine):
        engine.phase = 'move_duck'
        result = pipeline.execute_full_turn((6, 4), (4, 4), (3, 3))
        assert not result.ok
        assert "phase" in result.error.lower()

    def test_illegal_piece_move_rejected(self, pipeline, engine):
        result = pipeline.execute_full_turn((6, 4), (3, 4), (3, 3))  # 3-square pawn
        assert not result.ok
        assert "illegal" in result.error.lower()

    def test_no_state_mutation_on_illegal_move(self, pipeline, engine):
        original_board_snapshot = [row[:] for row in engine.board]
        pipeline.execute_full_turn((6, 4), (3, 4), (3, 3))
        for r in range(8):
            for c in range(8):
                assert engine.board[r][c] == original_board_snapshot[r][c]

    def test_wrong_color_piece_rejected(self, pipeline, engine):
        result = pipeline.execute_full_turn((1, 4), (3, 4), (3, 3))  # black pawn, white's turn
        assert not result.ok

    def test_invalid_duck_dest_occupied(self, pipeline, engine):
        # Try to place duck on white pawn at (6,0)
        result = pipeline.execute_full_turn((6, 4), (4, 4), (6, 0))
        assert not result.ok
        assert not result.ok

    def test_empty_start_square_rejected(self, pipeline, engine):
        result = pipeline.execute_full_turn((3, 3), (4, 3), (5, 5))
        assert not result.ok


# ------------------------------------------------------------------ #
# is_valid_piece_move                                                  #
# ------------------------------------------------------------------ #

class TestIsValidPieceMove:
    def test_valid_pawn_single_push(self, pipeline):
        assert pipeline.is_valid_piece_move((6, 4), (5, 4))

    def test_valid_pawn_double_push(self, pipeline):
        assert pipeline.is_valid_piece_move((6, 4), (4, 4))

    def test_invalid_pawn_triple_push(self, pipeline):
        assert not pipeline.is_valid_piece_move((6, 4), (3, 4))

    def test_wrong_color_returns_false(self, pipeline):
        assert not pipeline.is_valid_piece_move((1, 4), (3, 4))

    def test_empty_square_returns_false(self, pipeline):
        assert not pipeline.is_valid_piece_move((4, 4), (5, 4))


# ------------------------------------------------------------------ #
# is_valid_duck_placement                                              #
# ------------------------------------------------------------------ #

class TestIsValidDuckPlacement:
    def test_empty_center_square_valid(self, pipeline):
        assert pipeline.is_valid_duck_placement((4, 4))

    def test_occupied_square_invalid(self, pipeline, engine):
        assert not pipeline.is_valid_duck_placement((6, 0))   # white pawn

    def test_prev_duck_pos_invalid(self, pipeline, engine):
        engine.prev_duck_pos = (4, 4)
        assert not pipeline.is_valid_duck_placement((4, 4))

    def test_out_of_bounds_invalid(self, pipeline):
        assert not pipeline.is_valid_duck_placement((8, 0))
        assert not pipeline.is_valid_duck_placement((-1, 3))

    def test_sentinel_minus1_is_valid_destination(self, pipeline, engine):
        """(-1,-1) is not a real square — should be invalid."""
        assert not pipeline.is_valid_duck_placement((-1, -1))


# ------------------------------------------------------------------ #
# get_all_valid_turns                                                  #
# ------------------------------------------------------------------ #

class TestGetAllValidTurns:
    def test_returns_list_of_triples(self, pipeline):
        turns = pipeline.get_all_valid_turns()
        assert isinstance(turns, list)
        assert all(len(t) == 3 for t in turns)

    def test_count_at_start(self, pipeline):
        turns = pipeline.get_all_valid_turns()
        # 20 piece moves × 32 empty squares (rows 2-5 at start) = 640
        assert len(turns) >= 600

    def test_no_state_mutation(self, pipeline, engine):
        turn_before = engine.turn
        phase_before = engine.phase
        pipeline.get_all_valid_turns()
        assert engine.turn == turn_before
        assert engine.phase == phase_before

    def test_all_piece_moves_valid(self, pipeline, engine):
        turns = pipeline.get_all_valid_turns()
        for piece_start, piece_end, _ in turns:
            assert pipeline.is_valid_piece_move(piece_start, piece_end), (
                f"get_all_valid_turns returned invalid piece move {piece_start}->{piece_end}"
            )
