"""Tests for ObservationEncoder — shape, channel layout, bounds safety."""
import pytest
import numpy as np
from DuckChess_Game.Logic.observation_encoder import ObservationEncoder
from DuckChess_Game.Logic.bitboard_manager import BitboardManager
from DuckChess_Game.Logic.board_manager import BoardManager
from DuckChess_Game.Logic.constants import PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING


@pytest.fixture
def encoder():
    return ObservationEncoder()


@pytest.fixture
def populated_bb():
    bb = BitboardManager()
    for piece, r, c in BoardManager().get_initial_setup():
        bb.add_piece(piece.color, piece.type, r, c)
    return bb


def no_castle(r, c, is_ks):
    return False


def all_castle(r, c, is_ks):
    return True


# ------------------------------------------------------------------ #
# Shape                                                                #
# ------------------------------------------------------------------ #

class TestShape:
    def test_output_shape(self, encoder, populated_bb):
        obs = encoder.encode_state(populated_bb, 'w', None, no_castle)
        assert obs.shape == (19, 8, 8)

    def test_output_dtype(self, encoder, populated_bb):
        obs = encoder.encode_state(populated_bb, 'w', None, no_castle)
        assert obs.dtype == np.float32


# ------------------------------------------------------------------ #
# Piece channels 0-11                                                  #
# ------------------------------------------------------------------ #

class TestPieceChannels:
    def test_white_pawns_channel_0_has_8_ones(self, encoder, populated_bb):
        obs = encoder.encode_state(populated_bb, 'w', None, no_castle)
        assert obs[0].sum() == 8.0

    def test_white_pawns_on_row_6(self, encoder, populated_bb):
        obs = encoder.encode_state(populated_bb, 'w', None, no_castle)
        assert obs[0][6].sum() == 8.0
        assert obs[0][:6].sum() == 0.0
        assert obs[0][7].sum() == 0.0

    def test_black_pawns_channel_6_on_row_1(self, encoder, populated_bb):
        obs = encoder.encode_state(populated_bb, 'w', None, no_castle)
        assert obs[6].sum() == 8.0
        assert obs[6][1].sum() == 8.0

    def test_white_king_channel_5_at_e1(self, encoder, populated_bb):
        obs = encoder.encode_state(populated_bb, 'w', None, no_castle)
        assert obs[5][7][4] == 1.0
        assert obs[5].sum() == 1.0

    def test_black_king_channel_11_at_e8(self, encoder, populated_bb):
        obs = encoder.encode_state(populated_bb, 'w', None, no_castle)
        assert obs[11][0][4] == 1.0
        assert obs[11].sum() == 1.0

    def test_empty_board_piece_channels_all_zero(self, encoder):
        bb = BitboardManager()
        obs = encoder.encode_state(bb, 'w', None, no_castle)
        assert obs[:12].sum() == 0.0


# ------------------------------------------------------------------ #
# Duck channel 12                                                      #
# ------------------------------------------------------------------ #

class TestDuckChannel:
    def test_duck_channel_zero_at_start(self, encoder, populated_bb):
        obs = encoder.encode_state(populated_bb, 'w', None, no_castle)
        assert obs[12].sum() == 0.0

    def test_duck_channel_set_after_placement(self, encoder, populated_bb):
        populated_bb.move_duck(3, 3)
        obs = encoder.encode_state(populated_bb, 'w', None, no_castle)
        assert obs[12][3][3] == 1.0
        assert obs[12].sum() == 1.0


# ------------------------------------------------------------------ #
# En passant channel 13                                               #
# ------------------------------------------------------------------ #

class TestEnPassantChannel:
    def test_ep_channel_zero_when_none(self, encoder, populated_bb):
        obs = encoder.encode_state(populated_bb, 'w', None, no_castle)
        assert obs[13].sum() == 0.0

    def test_ep_channel_set_when_valid(self, encoder, populated_bb):
        obs = encoder.encode_state(populated_bb, 'w', (5, 4), no_castle)
        assert obs[13][5][4] == 1.0

    def test_ep_bounds_guard_invalid_row(self, encoder, populated_bb):
        """Regression for fix #2: out-of-bounds ep target must not crash."""
        obs = encoder.encode_state(populated_bb, 'w', (8, 3), no_castle)
        assert obs[13].sum() == 0.0

    def test_ep_bounds_guard_negative(self, encoder, populated_bb):
        obs = encoder.encode_state(populated_bb, 'w', (-1, 0), no_castle)
        assert obs[13].sum() == 0.0


# ------------------------------------------------------------------ #
# Turn channel 14                                                      #
# ------------------------------------------------------------------ #

class TestTurnChannel:
    def test_turn_channel_all_ones_for_white(self, encoder, populated_bb):
        obs = encoder.encode_state(populated_bb, 'w', None, no_castle)
        assert obs[14].sum() == 64.0

    def test_turn_channel_all_zeros_for_black(self, encoder, populated_bb):
        obs = encoder.encode_state(populated_bb, 'b', None, no_castle)
        assert obs[14].sum() == 0.0


# ------------------------------------------------------------------ #
# Castling channels 15-18                                             #
# ------------------------------------------------------------------ #

class TestCastlingChannels:
    def test_no_castling_rights_all_zero(self, encoder, populated_bb):
        obs = encoder.encode_state(populated_bb, 'w', None, no_castle)
        assert obs[15:19].sum() == 0.0

    def test_all_castling_rights_all_filled(self, encoder, populated_bb):
        obs = encoder.encode_state(populated_bb, 'w', None, all_castle)
        for ch in range(15, 19):
            assert obs[ch].sum() == 64.0
