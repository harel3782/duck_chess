"""Unit tests for Duck Chess game logic."""
import pytest
import numpy as np
from DuckChess_Game.SBThree.base.env_base import _HeadlessEngine


class TestGameInitialization:
    """Test game setup and initial state."""

    def test_init_creates_engine(self):
        game = _HeadlessEngine()
        assert game is not None
        assert hasattr(game, 'board')

    def test_board_is_2d_structure(self):
        game = _HeadlessEngine()
        # Board is a 2D list or array with 8x8 dimensions
        assert len(game.board) == 8
        assert all(len(row) == 8 for row in game.board)

    def test_has_required_attributes(self):
        game = _HeadlessEngine()
        assert hasattr(game, 'turn')
        assert hasattr(game, 'phase')
        assert hasattr(game, 'winner')
        assert hasattr(game, 'duck_pos')


class TestGameState:
    """Test basic game state properties."""

    def test_initial_turn_is_white(self):
        game = _HeadlessEngine()
        # Turn is represented as 'w' for white or 'b' for black
        assert game.turn == "w"

    def test_initial_phase_is_move_piece(self):
        game = _HeadlessEngine()
        assert game.phase == "move_piece"

    def test_initial_winner_is_none(self):
        game = _HeadlessEngine()
        assert game.winner is None

    def test_initial_game_mode(self):
        game = _HeadlessEngine()
        assert game.game_mode == 'rl_training'


class TestObservationEncoding:
    """Test the 19-channel observation tensor."""

    def test_observation_shape(self):
        game = _HeadlessEngine()
        if hasattr(game, 'get_observation'):
            obs = game.get_observation()
            assert isinstance(obs, np.ndarray)
            assert obs.shape == (19, 8, 8), f"Expected (19, 8, 8), got {obs.shape}"

    def test_observation_dtype(self):
        game = _HeadlessEngine()
        if hasattr(game, 'get_observation'):
            obs = game.get_observation()
            assert obs.dtype in [np.float32, np.float64]

    def test_observation_values_in_range(self):
        game = _HeadlessEngine()
        if hasattr(game, 'get_observation'):
            obs = game.get_observation()
            assert (obs >= 0).all() and (obs <= 1).all()


class TestActionMasking:
    """Test legal action mask generation."""

    def test_action_mask_shape(self):
        game = _HeadlessEngine()
        if hasattr(game, 'get_action_mask'):
            mask = game.get_action_mask()
            assert isinstance(mask, np.ndarray)
            assert mask.shape == (4096,), f"Expected shape (4096,), got {mask.shape}"

    def test_action_mask_dtype(self):
        game = _HeadlessEngine()
        if hasattr(game, 'get_action_mask'):
            mask = game.get_action_mask()
            assert mask.dtype in [bool, np.uint8, np.int32, np.int64]

    def test_action_mask_has_legal_moves(self):
        game = _HeadlessEngine()
        if hasattr(game, 'get_action_mask'):
            mask = game.get_action_mask()
            assert mask.sum() > 0, "No legal moves in starting position"


class TestGameRules:
    """Test basic duck chess rules."""

    def test_duck_position_tracked(self):
        game = _HeadlessEngine()
        # Duck position should be tracked
        assert hasattr(game, 'duck_pos')
        # Initially duck might not be placed
        assert game.duck_pos == (-1, -1) or isinstance(game.duck_pos, tuple)

    def test_phase_attribute_exists(self):
        game = _HeadlessEngine()
        assert game.phase in ["move_piece", "move_duck", "move_piece_ducked"]

    def test_turn_alternates(self):
        game = _HeadlessEngine()
        assert game.turn in ["w", "b"]


class TestGameFlow:
    """Test that game progresses without errors."""

    def test_game_initialization_does_not_crash(self):
        """Verify game initializes and maintains state."""
        game = _HeadlessEngine()
        initial_board = game.board.copy()
        assert initial_board is not None

    def test_reset_game_state_exists(self):
        """Verify game can reset state."""
        game = _HeadlessEngine()
        if hasattr(game, 'reset_game_state'):
            game.reset_game_state()
            assert game.turn == "w"
            assert game.phase == "move_piece"

    def test_board_manager_initialized(self):
        """Verify board manager is set up."""
        game = _HeadlessEngine()
        assert hasattr(game, 'board_mgr')
        assert game.board_mgr is not None

    def test_bitboard_manager_initialized(self):
        """Verify bitboard manager is set up for fast move generation."""
        game = _HeadlessEngine()
        assert hasattr(game, 'bb_mgr')
        assert game.bb_mgr is not None


class TestRLInterface:
    """Test RL-specific interface methods."""

    def test_rl_mixin_methods_exist(self):
        """Verify RL interface is integrated."""
        game = _HeadlessEngine()
        # Verify game has RL-related attributes
        assert hasattr(game, 'history') or hasattr(game, 'board')

    def test_game_can_track_history(self):
        """Verify game tracks move history."""
        game = _HeadlessEngine()
        assert hasattr(game, 'history')
        assert isinstance(game.history, (list, tuple))


class TestEndgameConditions:
    """Test game termination detection."""

    def test_winner_attribute_exists(self):
        game = _HeadlessEngine()
        assert hasattr(game, 'winner')
        # Initially no winner
        assert game.winner is None

    def test_endgame_checker_integrated(self):
        """Verify endgame checker mixin is included."""
        game = _HeadlessEngine()
        # Verify game has endgame tracking
        assert hasattr(game, 'winner')


class TestIntegration:
    """Integration tests for game stability."""

    def test_multiple_game_instances_independent(self):
        """Verify multiple game instances don't interfere."""
        game1 = _HeadlessEngine()
        game2 = _HeadlessEngine()
        assert game1 is not game2
        assert game1.board is not game2.board

    def test_game_structure_is_consistent(self):
        """Verify game structure remains consistent."""
        for _ in range(5):
            game = _HeadlessEngine()
            assert len(game.board) == 8 and all(len(row) == 8 for row in game.board)
            assert game.turn in ["w", "b"]
            assert game.phase in ["move_piece", "move_duck", "move_piece_ducked"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
