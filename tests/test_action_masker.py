"""Tests for ActionMasker — encoding, decoding, phase masks, and collision regression."""
import pytest
import numpy as np
from DuckChess_Game.Logic.action_masker import ActionMasker
from DuckChess_Game.Logic.constants import PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING
from DuckChess_Game.UI.pieces import Piece


@pytest.fixture
def masker():
    return ActionMasker()


# ------------------------------------------------------------------ #
# Encode / decode                                                      #
# ------------------------------------------------------------------ #

class TestEncoding:
    def test_encode_decode_roundtrip_corners(self, masker):
        for start in [(0, 0), (0, 7), (7, 0), (7, 7)]:
            for end in [(0, 0), (3, 4), (7, 7)]:
                if start == end:
                    continue
                idx = masker.encode_move(start, end)
                s2, e2 = masker.decode_move(idx)
                assert s2 == start
                assert e2 == end

    def test_encode_decode_roundtrip_all_squares(self, masker):
        for sr in range(8):
            for sc in range(8):
                for er in range(8):
                    for ec in range(8):
                        if (sr, sc) == (er, ec):
                            continue
                        idx = masker.encode_move((sr, sc), (er, ec))
                        assert 0 <= idx < 4096
                        s2, e2 = masker.decode_move(idx)
                        assert s2 == (sr, sc)
                        assert e2 == (er, ec)

    def test_encode_range(self, masker):
        for sr in range(8):
            for sc in range(8):
                idx = masker.encode_move((sr, sc), (0, 0))
                assert 0 <= idx < 4096


# ------------------------------------------------------------------ #
# move_piece phase mask                                                #
# ------------------------------------------------------------------ #

class TestMovePieceMask:
    def test_starting_position_mask_count_is_20(self, engine):
        masks = engine.action_masks()
        assert masks.sum() == 20

    def test_mask_length_is_4096(self, engine):
        assert len(engine.action_masks()) == 4096

    def test_mask_dtype_bool(self, engine):
        assert engine.action_masks().dtype == bool

    def test_mask_reflects_legal_moves(self, engine):
        """Every True index in the mask decodes to a legal move for the current player."""
        masker = ActionMasker()
        masks = engine.action_masks()
        for idx in np.where(masks)[0]:
            start, end = masker.decode_move(int(idx))
            legal = engine.get_piece_legal_moves(start[0], start[1])
            assert end in legal, f"Mask set for illegal move {start}->{end}"


# ------------------------------------------------------------------ #
# move_duck phase mask — collision regression                          #
# ------------------------------------------------------------------ #

class TestMoveDuckMask:
    def _enter_duck_phase(self, engine):
        """Execute a piece move so phase becomes 'move_duck'."""
        engine.execute_move((6, 4), (4, 4), animated=False)   # e2 -> e4

    def test_duck_phase_no_collision_with_piece_from_a8(self, engine):
        """
        Regression for fix #1: at game start duck_pos is (-1,-1), which mapped
        to (0,0) before the fix — colliding with piece-from-a8 indices.
        After the fix, duck phase always uses (0,0) as from-coordinate, which is
        still consistent because piece and duck phases never overlap.
        """
        self._enter_duck_phase(engine)
        assert engine.phase == 'move_duck'
        masks = engine.action_masks()
        # All set bits in duck phase should decode to destinations only
        # (from-coord is always (0,0), destination varies)
        masker = ActionMasker()
        for idx in np.where(masks)[0]:
            start, end = masker.decode_move(int(idx))
            assert start == (0, 0), (
                f"Duck-phase mask index {idx} has unexpected from-square {start}"
            )

    def test_prev_duck_pos_excluded_from_duck_mask(self, engine):
        """After placing duck at (4,4), the next duck phase must exclude (4,4)."""
        # Play a full first turn
        engine.execute_move((6, 4), (4, 4), animated=False)
        engine.place_duck((3, 3), animated=False)
        # Play another piece move to enter next duck phase
        engine.execute_move((1, 4), (3, 4), animated=False)   # black e7->e5
        assert engine.phase == 'move_duck'
        prev = engine.prev_duck_pos   # should be (3,3)
        masker = ActionMasker()
        masks = engine.action_masks()
        for idx in np.where(masks)[0]:
            _, end = masker.decode_move(int(idx))
            assert end != prev, f"Duck mask includes prev_duck_pos {prev}"

    def test_duck_mask_excludes_occupied_squares(self, engine):
        """No duck destination in the mask should be an occupied square."""
        self._enter_duck_phase(engine)
        masker = ActionMasker()
        masks = engine.action_masks()
        for idx in np.where(masks)[0]:
            _, end = masker.decode_move(int(idx))
            assert engine.board[end[0]][end[1]] is None, (
                f"Duck mask includes occupied square {end}"
            )
