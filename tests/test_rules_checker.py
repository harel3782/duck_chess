"""Tests for RulesChecker — check detection with and without duck blocking."""
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame
pygame.init()

import pytest
from DuckChess_Game.Logic.rules_checker import RulesChecker
from DuckChess_Game.Logic.board_manager import BoardManager
from DuckChess_Game.UI.pieces import Piece
from DuckChess_Game.Logic.constants import PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING


@pytest.fixture
def checker():
    return RulesChecker()


@pytest.fixture
def empty_board():
    return [[None] * 8 for _ in range(8)]


def place(board, color, piece_type, r, c):
    board[r][c] = Piece(color, piece_type)


# ------------------------------------------------------------------ #
# Baseline                                                             #
# ------------------------------------------------------------------ #

class TestNoCheckAtStart:
    def test_white_not_in_check(self, checker, starting_board):
        assert not checker.is_in_check('w', starting_board, (-1, -1))

    def test_black_not_in_check(self, checker, starting_board):
        assert not checker.is_in_check('b', starting_board, (-1, -1))


# ------------------------------------------------------------------ #
# Attack vectors                                                       #
# ------------------------------------------------------------------ #

class TestKnightCheck:
    def test_knight_gives_check(self, checker, empty_board):
        place(empty_board, 'w', KING, 7, 4)
        place(empty_board, 'b', KNIGHT, 5, 3)   # attacks (7,4) via +2/-1
        assert checker.is_in_check('w', empty_board, (-1, -1))

    def test_knight_not_blocked_by_pieces(self, checker, empty_board):
        """Knights jump over pieces — no blocker can prevent the check."""
        place(empty_board, 'w', KING, 7, 4)
        place(empty_board, 'b', KNIGHT, 5, 3)
        place(empty_board, 'w', PAWN, 6, 3)    # pawn between them — irrelevant
        assert checker.is_in_check('w', empty_board, (-1, -1))

    def test_knight_not_blocking_non_attack(self, checker, empty_board):
        place(empty_board, 'w', KING, 7, 4)
        place(empty_board, 'b', KNIGHT, 4, 4)   # not an L-shape to (7,4)
        assert not checker.is_in_check('w', empty_board, (-1, -1))


class TestSlidingCheck:
    def test_rook_gives_check_on_rank(self, checker, empty_board):
        place(empty_board, 'w', KING, 7, 4)
        place(empty_board, 'b', ROOK, 7, 0)
        assert checker.is_in_check('w', empty_board, (-1, -1))

    def test_queen_gives_check_on_diagonal(self, checker, empty_board):
        place(empty_board, 'w', KING, 4, 4)
        place(empty_board, 'b', QUEEN, 1, 1)
        assert checker.is_in_check('w', empty_board, (-1, -1))

    def test_bishop_gives_check(self, checker, empty_board):
        place(empty_board, 'w', KING, 4, 4)
        place(empty_board, 'b', BISHOP, 2, 2)
        assert checker.is_in_check('w', empty_board, (-1, -1))

    def test_sliding_blocked_by_own_piece(self, checker, empty_board):
        place(empty_board, 'w', KING, 7, 4)
        place(empty_board, 'b', ROOK, 7, 0)
        place(empty_board, 'w', PAWN, 7, 2)     # blocks the rook's ray
        assert not checker.is_in_check('w', empty_board, (-1, -1))


class TestDuckBlocksCheck:
    def test_duck_blocks_rook_ray(self, checker, empty_board):
        place(empty_board, 'w', KING, 7, 4)
        place(empty_board, 'b', ROOK, 7, 0)
        duck_pos = (7, 2)
        assert not checker.is_in_check('w', empty_board, duck_pos)

    def test_duck_blocks_queen_diagonal(self, checker, empty_board):
        place(empty_board, 'w', KING, 4, 4)
        place(empty_board, 'b', QUEEN, 1, 1)
        duck_pos = (3, 3)
        assert not checker.is_in_check('w', empty_board, duck_pos)

    def test_duck_does_not_block_knight(self, checker, empty_board):
        """Duck on path between knight and king still allows the check (knights jump)."""
        place(empty_board, 'w', KING, 7, 4)
        place(empty_board, 'b', KNIGHT, 5, 3)
        duck_pos = (6, 4)
        assert checker.is_in_check('w', empty_board, duck_pos)


class TestPawnCheck:
    def test_black_pawn_gives_check_to_white_king(self, checker, empty_board):
        place(empty_board, 'w', KING, 3, 3)
        place(empty_board, 'b', PAWN, 2, 4)   # black pawn attacks diagonally downward
        assert checker.is_in_check('w', empty_board, (-1, -1))

    def test_white_pawn_gives_check_to_black_king(self, checker, empty_board):
        place(empty_board, 'b', KING, 3, 3)
        place(empty_board, 'w', PAWN, 4, 4)   # white pawn attacks diagonally upward
        assert checker.is_in_check('b', empty_board, (-1, -1))


class TestKingProximityCheck:
    def test_kings_adjacent_gives_check(self, checker, empty_board):
        place(empty_board, 'w', KING, 4, 4)
        place(empty_board, 'b', KING, 4, 5)
        assert checker.is_in_check('w', empty_board, (-1, -1))
