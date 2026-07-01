"""Tests for BaseDuckChessEnv — reset, step, action_masks, hot-swap."""
import numpy as np
import pytest

from DuckChess_Game.SBThree.base.env_base import BaseDuckChessEnv, EnvConfig
from DuckChess_Game.SBThree.base.mask_strategy import ForcedKingCaptureMask, StandardMask
from DuckChess_Game.SBThree.base.opponent_strategy import RandomOpponent
from DuckChess_Game.SBThree.base.reward_calculator import TerminalReward


@pytest.fixture
def minimal_config():
    return EnvConfig(
        stage_name="test",
        opponent=RandomOpponent(),
        reward=TerminalReward(),
        mask=StandardMask(),
        randomize_color=False,
        replay_every=0,
        replay_chief_only=False,
    )


@pytest.fixture
def env(minimal_config):
    return BaseDuckChessEnv(minimal_config, env_index=0)


@pytest.fixture
def rand_color_env():
    config = EnvConfig(
        stage_name="test_rand",
        opponent=RandomOpponent(),
        reward=TerminalReward(),
        mask=StandardMask(),
        randomize_color=True,
        replay_every=0,
    )
    return BaseDuckChessEnv(config, env_index=0)


# ------------------------------------------------------------------ #
# Observation and action spaces                                        #
# ------------------------------------------------------------------ #

class TestSpaces:
    def test_observation_shape(self, env):
        obs, _ = env.reset()
        assert obs.shape == (19, 8, 8)

    def test_observation_dtype(self, env):
        obs, _ = env.reset()
        assert obs.dtype == np.float32

    def test_action_space_size(self, env):
        from gymnasium import spaces
        assert isinstance(env.action_space, spaces.Discrete)
        assert env.action_space.n == 4096

    def test_action_masks_shape(self, env):
        env.reset()
        assert env.action_masks().shape == (4096,)

    def test_action_masks_boolean(self, env):
        env.reset()
        assert env.action_masks().dtype == bool


# ------------------------------------------------------------------ #
# reset()                                                              #
# ------------------------------------------------------------------ #

class TestReset:
    def test_returns_tuple(self, env):
        result = env.reset()
        assert len(result) == 2

    def test_info_is_dict(self, env):
        _, info = env.reset()
        assert isinstance(info, dict)

    def test_episode_counter_increments(self, env):
        env.reset()
        env.reset()
        assert env.episode_counter == 2

    def test_always_white_when_not_randomized(self, env):
        for _ in range(5):
            env.reset()
            assert env.learning_color == 'w'

    def test_randomize_color_varies(self, rand_color_env):
        colors = set()
        for _ in range(20):
            rand_color_env.reset()
            colors.add(rand_color_env.learning_color)
        assert colors == {'w', 'b'}, "Color should be randomised across 20 resets"

    def test_action_masks_non_empty_after_reset(self, env):
        env.reset()
        assert np.any(env.action_masks())


# ------------------------------------------------------------------ #
# step()                                                               #
# ------------------------------------------------------------------ #

class TestStep:
    def test_returns_five_tuple(self, env):
        env.reset()
        masks = env.action_masks()
        action = int(np.where(masks)[0][0])
        result = env.step(action)
        assert len(result) == 5

    def test_obs_shape(self, env):
        env.reset()
        masks = env.action_masks()
        action = int(np.where(masks)[0][0])
        obs, _, _, _, _ = env.step(action)
        assert obs.shape == (19, 8, 8)

    def test_truncated_always_false(self, env):
        env.reset()
        masks = env.action_masks()
        action = int(np.where(masks)[0][0])
        _, _, _, truncated, _ = env.step(action)
        assert truncated is False

    def test_reward_is_float(self, env):
        env.reset()
        masks = env.action_masks()
        action = int(np.where(masks)[0][0])
        _, reward, _, _, _ = env.step(action)
        assert isinstance(reward, float)

    def test_game_terminates(self, env):
        """A complete game must eventually terminate."""
        env.reset()
        for _ in range(1000):
            masks = env.action_masks()
            action = int(np.where(masks)[0][0])
            _, _, terminated, _, _ = env.step(action)
            if terminated:
                break
        else:
            pytest.fail("Game did not terminate within 1000 steps")

    def test_terminal_reward_win(self, env):
        env.reset()
        env.engine.game_over = True
        env.engine.winner = 'w'
        env.learning_color = 'w'
        masks = env.action_masks()
        action = int(np.where(masks)[0][0])
        _, reward, terminated, _, _ = env.step(action)
        assert terminated
        assert reward == pytest.approx(1.0)


# ------------------------------------------------------------------ #
# ForcedKingCaptureMask applied via BaseDuckChessEnv                   #
# ------------------------------------------------------------------ #

class TestForcedKingCaptureMaskIntegration:
    def test_only_king_capture_when_available(self):
        from DuckChess_Game.Logic.constants import KING, ROOK
        from DuckChess_Game.Logic.pieces import Piece

        config = EnvConfig(
            stage_name="fkc_test",
            opponent=RandomOpponent(),
            reward=TerminalReward(),
            mask=ForcedKingCaptureMask(),
            randomize_color=False,
            replay_every=0,
        )
        env = BaseDuckChessEnv(config)
        env.reset()

        # Place black king reachable by white rook
        env.engine.board[4][4] = Piece('b', KING)
        env.engine.bb_mgr.add_piece('b', KING, 4, 4)
        env.engine.board[4][0] = Piece('w', ROOK)
        env.engine.bb_mgr.add_piece('w', ROOK, 4, 0)

        masks = env.action_masks()
        valid = np.where(masks)[0]
        assert len(valid) >= 1
        for a in valid:
            _, end = env.engine._decode_move(int(a))
            target = env.engine.board[end[0]][end[1]]
            assert target is not None and target.type == KING, \
                "ForcedKingCaptureMask should restrict to king captures only"


# ------------------------------------------------------------------ #
# set_opponents hot-swap                                               #
# ------------------------------------------------------------------ #

class TestHotSwap:
    def test_set_opponents_nonexistent_is_safe(self, env):
        env.reset()
        env.set_opponents("/nonexistent/latest.zip", "/nonexistent/hist.zip")

    def test_set_opponent_nonexistent_is_safe(self, env):
        env.reset()
        env.set_opponent("/nonexistent/model.zip")
