"""Tests for BitboardManager — bit operations, occupancy tracking, and sync validation."""
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame
pygame.init()

import pytest
from DuckChess_Game.Logic.bitboard_manager import BitboardManager
from DuckChess_Game.Logic.board_manager import BoardManager
from DuckChess_Game.Logic.constants import PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING


# ------------------------------------------------------------------ #
# Bit operations                                                       #
# ------------------------------------------------------------------ #

class TestBitOperations:
    def test_set_bit_roundtrip(self, fresh_bb):
        for sq in (0, 27, 63):
            bb = fresh_bb.set_bit(0, sq)
            assert fresh_bb.get_bit(bb, sq)

    def test_clear_bit_roundtrip(self, fresh_bb):
        for sq in (0, 27, 63):
            bb = fresh_bb.set_bit(0, sq)
            bb = fresh_bb.clear_bit(bb, sq)
            assert not fresh_bb.get_bit(bb, sq)

    def test_set_bit_does_not_affect_others(self, fresh_bb):
        bb = fresh_bb.set_bit(0, 5)
        for sq in range(64):
            if sq != 5:
                assert not fresh_bb.get_bit(bb, sq)

    def test_coords_to_square_corners(self, fresh_bb):
        assert fresh_bb.coords_to_square(0, 0) == 0
        assert fresh_bb.coords_to_square(0, 7) == 7
        assert fresh_bb.coords_to_square(7, 0) == 56
        assert fresh_bb.coords_to_square(7, 7) == 63

    def test_coords_to_square_midboard(self, fresh_bb):
        assert fresh_bb.coords_to_square(3, 4) == 28
        assert fresh_bb.coords_to_square(4, 3) == 35


# ------------------------------------------------------------------ #
# Occupancy updates                                                    #
# ------------------------------------------------------------------ #

class TestOccupancy:
    def test_add_piece_sets_white_occupancy(self, fresh_bb):
        fresh_bb.add_piece('w', PAWN, 6, 0)
        sq = fresh_bb.coords_to_square(6, 0)
        assert fresh_bb.get_bit(fresh_bb.white_occupancy, sq)
        assert fresh_bb.get_bit(fresh_bb.all_occupancy, sq)
        assert not fresh_bb.get_bit(fresh_bb.black_occupancy, sq)

    def test_add_piece_sets_black_occupancy(self, fresh_bb):
        fresh_bb.add_piece('b', KNIGHT, 2, 3)
        sq = fresh_bb.coords_to_square(2, 3)
        assert fresh_bb.get_bit(fresh_bb.black_occupancy, sq)
        assert not fresh_bb.get_bit(fresh_bb.white_occupancy, sq)

    def test_remove_piece_clears_occupancy(self, fresh_bb):
        fresh_bb.add_piece('w', ROOK, 7, 0)
        fresh_bb.remove_piece('w', ROOK, 7, 0)
        sq = fresh_bb.coords_to_square(7, 0)
        assert not fresh_bb.get_bit(fresh_bb.white_occupancy, sq)
        assert not fresh_bb.get_bit(fresh_bb.all_occupancy, sq)

    def test_two_pieces_same_color(self, fresh_bb):
        fresh_bb.add_piece('w', PAWN, 6, 0)
        fresh_bb.add_piece('w', PAWN, 6, 1)
        sq0 = fresh_bb.coords_to_square(6, 0)
        sq1 = fresh_bb.coords_to_square(6, 1)
        assert fresh_bb.get_bit(fresh_bb.white_occupancy, sq0)
        assert fresh_bb.get_bit(fresh_bb.white_occupancy, sq1)


# ------------------------------------------------------------------ #
# Duck board                                                           #
# ------------------------------------------------------------------ #

class TestDuckBoard:
    def test_move_duck_sets_duck_board(self, fresh_bb):
        fresh_bb.move_duck(3, 3)
        sq = fresh_bb.coords_to_square(3, 3)
        assert fresh_bb.get_bit(fresh_bb.duck_board, sq)

    def test_move_duck_clears_previous_square(self, fresh_bb):
        fresh_bb.move_duck(3, 3)
        fresh_bb.move_duck(4, 4)
        old_sq = fresh_bb.coords_to_square(3, 3)
        new_sq = fresh_bb.coords_to_square(4, 4)
        assert not fresh_bb.get_bit(fresh_bb.duck_board, old_sq)
        assert fresh_bb.get_bit(fresh_bb.duck_board, new_sq)

    def test_duck_not_in_piece_occupancy(self, fresh_bb):
        fresh_bb.move_duck(3, 3)
        sq = fresh_bb.coords_to_square(3, 3)
        assert not fresh_bb.get_bit(fresh_bb.white_occupancy, sq)
        assert not fresh_bb.get_bit(fresh_bb.black_occupancy, sq)


# ------------------------------------------------------------------ #
# Sync validation                                                      #
# ------------------------------------------------------------------ #

class TestVerifySync:
    def test_passes_on_starting_position(self, starting_bb, starting_board):
        assert starting_bb.verify_sync(starting_board, (-1, -1)) is True

    def test_fails_when_bb_has_extra_piece(self, starting_bb, starting_board):
        # Add a ghost piece to the bitboard without updating the 2D board
        starting_bb.add_piece('w', PAWN, 3, 3)
        assert starting_bb.verify_sync(starting_board, (-1, -1)) is False

    def test_fails_when_duck_pos_mismatches(self, starting_bb, starting_board):
        # Move duck in bb but pass wrong duck_pos
        starting_bb.move_duck(4, 4)
        assert starting_bb.verify_sync(starting_board, (-1, -1)) is False

    def test_passes_with_duck_synced(self, starting_bb, starting_board):
        starting_bb.move_duck(4, 4)
        assert starting_bb.verify_sync(starting_board, (4, 4)) is True
