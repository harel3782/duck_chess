"""Tests for MoveGenerationMixin — legal moves, double pushes, duck blocking, castling, en passant."""
import pytest
from DuckChess_Game.Logic.constants import PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING
from DuckChess_Game.UI.pieces import Piece


# ------------------------------------------------------------------ #
# Starting position move counts                                        #
# ------------------------------------------------------------------ #

class TestStartingMoveCount:
    def test_white_has_20_legal_moves(self, engine):
        total = sum(
            len(engine.get_piece_legal_moves(r, c))
            for r in range(8) for c in range(8)
            if engine.board[r][c] and engine.board[r][c].color == 'w'
        )
        assert total == 20

    def test_black_has_20_legal_moves(self, engine):
        total = sum(
            len(engine.get_piece_legal_moves(r, c))
            for r in range(8) for c in range(8)
            if engine.board[r][c] and engine.board[r][c].color == 'b'
        )
        assert total == 20


# ------------------------------------------------------------------ #
# Pawn double-push from starting rank                                  #
# ------------------------------------------------------------------ #

class TestPawnDoublePush:
    def test_white_a_pawn_can_double_push(self, engine):
        moves = engine.get_piece_legal_moves(6, 0)
        assert (4, 0) in moves   # two squares forward
        assert (5, 0) in moves   # one square forward

    def test_white_pawn_double_push_blocked_by_piece(self, engine):
        """Place a piece one square in front of white pawn — no double push."""
        engine.board[5][0] = Piece('b', PAWN)
        engine.bb_mgr.add_piece('b', PAWN, 5, 0)
        moves = engine.get_piece_legal_moves(6, 0)
        assert (4, 0) not in moves
        assert (5, 0) not in moves

    def test_black_a_pawn_can_double_push(self, engine):
        """Regression for bitboard black pawn starting-row mask."""
        moves = engine.get_piece_legal_moves(1, 0)
        assert (3, 0) in moves
        assert (2, 0) in moves

    def test_black_pawn_double_push_all_files(self, engine):
        for col in range(8):
            moves = engine.get_piece_legal_moves(1, col)
            assert (3, col) in moves, f"Black pawn at (1,{col}) cannot double-push"


# ------------------------------------------------------------------ #
# Duck blocking                                                        #
# ------------------------------------------------------------------ #

class TestDuckBlocking:
    def test_duck_blocks_rook_on_open_file(self, engine):
        # Clear column a for white rook and place duck in between
        engine.board[6][0] = None
        engine.bb_mgr.remove_piece('w', PAWN, 6, 0)
        engine.duck_pos = (4, 0)
        engine.bb_mgr.move_duck(4, 0)
        moves = engine.get_piece_legal_moves(7, 0)   # white rook at a1
        # Rook can move to (5,0) and (6,0) but NOT past the duck
        col_a_moves = [m for m in moves if m[1] == 0]
        rows = [m[0] for m in col_a_moves]
        assert 4 not in rows   # duck square is blocked
        assert 3 not in rows   # beyond duck is blocked

    def test_duck_blocks_queen_diagonal(self, engine):
        # Clear d2 pawn and e3 square; put white queen on d1 and duck on f3
        engine.board[6][3] = None
        engine.bb_mgr.remove_piece('w', PAWN, 6, 3)
        engine.duck_pos = (5, 5)
        engine.bb_mgr.move_duck(5, 5)
        queen_moves = engine.get_piece_legal_moves(7, 3)   # white queen d1
        diagonal_past_duck = [(4, 6), (3, 7)]
        for sq in diagonal_past_duck:
            assert sq not in queen_moves


# ------------------------------------------------------------------ #
# En passant                                                           #
# ------------------------------------------------------------------ #

class TestEnPassant:
    def test_ep_capture_appears_after_double_push(self, engine):
        # White pawn e2->e4
        engine.execute_move((6, 4), (4, 4), animated=False)
        # Place black pawn on d4 manually (adjacent)
        engine.board[4][3] = Piece('b', PAWN)
        engine.bb_mgr.add_piece('b', PAWN, 4, 3)
        # Set ep target as if white just double-pushed
        engine.en_passant_target = (5, 4)
        moves = engine.get_piece_legal_moves(4, 3)
        assert (5, 4) in moves

    def test_ep_blocked_by_duck(self, engine):
        engine.execute_move((6, 4), (4, 4), animated=False)
        engine.board[4][3] = Piece('b', PAWN)
        engine.bb_mgr.add_piece('b', PAWN, 4, 3)
        engine.en_passant_target = (5, 4)
        engine.duck_pos = (5, 4)
        engine.bb_mgr.move_duck(5, 4)
        moves = engine.get_piece_legal_moves(4, 3)
        assert (5, 4) not in moves


# ------------------------------------------------------------------ #
# Castling                                                             #
# ------------------------------------------------------------------ #

class TestCastling:
    def _clear_kingside_white(self, engine):
        """Remove f1 and g1 pieces to open kingside for white."""
        engine.board[7][5] = None
        engine.board[7][6] = None
        engine.bb_mgr.remove_piece('w', BISHOP, 7, 5)
        engine.bb_mgr.remove_piece('w', KNIGHT, 7, 6)

    def test_castling_not_available_at_start(self, engine):
        """Pieces block the castling path at game start."""
        moves = engine.get_piece_legal_moves(7, 4)  # white king
        assert (7, 6) not in moves
        assert (7, 2) not in moves

    def test_kingside_castling_available_with_clear_path(self, engine):
        self._clear_kingside_white(engine)
        moves = engine.get_piece_legal_moves(7, 4)
        assert (7, 6) in moves

    def test_castling_blocked_by_duck(self, engine):
        self._clear_kingside_white(engine)
        engine.duck_pos = (7, 5)
        engine.bb_mgr.move_duck(7, 5)
        moves = engine.get_piece_legal_moves(7, 4)
        assert (7, 6) not in moves

    def test_castling_blocked_after_king_moves(self, engine):
        self._clear_kingside_white(engine)
        engine.board[7][4].has_moved = True
        moves = engine.get_piece_legal_moves(7, 4)
        assert (7, 6) not in moves
