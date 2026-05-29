"""Tests for EnvFactory and env_registry."""
import pytest

from DuckChess_Game.SBThree.base.env_base import BaseDuckChessEnv, EnvConfig
from DuckChess_Game.SBThree.env_factory import EnvFactory
from DuckChess_Game.SBThree.env_registry import REGISTRY


# ------------------------------------------------------------------ #
# Registry completeness                                                #
# ------------------------------------------------------------------ #

_STAGE_KEYS = {f"stage{i}" for i in range(1, 13)}
_PETER_KEYS = {"peter_easy", "peter_medium", "peter_hard"}
_ALL_KEYS   = _STAGE_KEYS | _PETER_KEYS


class TestRegistry:
    def test_has_expected_entry_count(self):
        assert len(REGISTRY) == len(_ALL_KEYS)

    def test_all_stage_keys_present(self):
        assert _STAGE_KEYS.issubset(set(REGISTRY.keys()))

    def test_peter_keys_present(self):
        assert _PETER_KEYS.issubset(set(REGISTRY.keys()))

    def test_each_entry_is_callable(self):
        for name, factory in REGISTRY.items():
            assert callable(factory), f"REGISTRY[{name!r}] is not callable"

    def test_each_factory_returns_env_config(self):
        for name, factory in REGISTRY.items():
            cfg = factory()
            assert isinstance(cfg, EnvConfig), \
                f"REGISTRY[{name!r}]() did not return EnvConfig"

    def test_factories_produce_independent_instances(self):
        cfg1 = REGISTRY["stage11"]()
        cfg2 = REGISTRY["stage11"]()
        assert cfg1 is not cfg2, "Factory should return a new EnvConfig each call"
        assert cfg1.opponent is not cfg2.opponent, \
            "Each EnvConfig should have its own opponent instance"


# ------------------------------------------------------------------ #
# EnvFactory.create                                                    #
# ------------------------------------------------------------------ #

class TestEnvFactoryCreate:
    def test_returns_base_env_instance(self):
        env = EnvFactory.create("stage11")
        assert isinstance(env, BaseDuckChessEnv)
        env.close()

    def test_stage12_returns_env(self):
        env = EnvFactory.create("stage12")
        assert isinstance(env, BaseDuckChessEnv)
        env.close()

    def test_unknown_stage_raises_key_error(self):
        with pytest.raises(KeyError, match="unknown_stage"):
            EnvFactory.create("unknown_stage")

    def test_env_index_forwarded(self):
        env = EnvFactory.create("stage11", env_index=3)
        assert env.env_index == 3
        env.close()

    def test_env_resets_and_steps(self):
        import numpy as np
        env = EnvFactory.create("stage11")
        obs, _ = env.reset()
        assert obs.shape == (19, 8, 8)
        masks = env.action_masks()
        action = int(np.where(masks)[0][0])
        obs2, reward, terminated, truncated, _ = env.step(action)
        assert obs2.shape == (19, 8, 8)
        assert truncated is False
        env.close()


# ------------------------------------------------------------------ #
# EnvFactory.list_stages                                               #
# ------------------------------------------------------------------ #

class TestEnvFactoryListStages:
    def test_returns_list_of_strings(self):
        stages = EnvFactory.list_stages()
        assert isinstance(stages, list)
        assert all(isinstance(s, str) for s in stages)

    def test_returns_expected_stage_count(self):
        assert len(EnvFactory.list_stages()) == len(_ALL_KEYS)

    def test_is_sorted(self):
        stages = EnvFactory.list_stages()
        assert stages == sorted(stages)


# ------------------------------------------------------------------ #
# Stage-specific config spot-checks                                    #
# ------------------------------------------------------------------ #

class TestStageConfigSpotChecks:
    def test_stage1_no_randomize_color(self):
        from DuckChess_Game.SBThree.env_registry import make_stage1_config
        cfg = make_stage1_config()
        assert cfg.randomize_color is False

    def test_stage11_randomize_color(self):
        from DuckChess_Game.SBThree.env_registry import make_stage11_config
        cfg = make_stage11_config()
        assert cfg.randomize_color is True

    def test_stage11_chief_only_replay(self):
        from DuckChess_Game.SBThree.env_registry import make_stage11_config
        cfg = make_stage11_config()
        assert cfg.replay_chief_only is True

    def test_stage12_chief_only_replay(self):
        from DuckChess_Game.SBThree.env_registry import make_stage12_config
        cfg = make_stage12_config()
        assert cfg.replay_chief_only is True

    def test_stage10_not_chief_only(self):
        from DuckChess_Game.SBThree.env_registry import make_stage10_config
        cfg = make_stage10_config()
        assert cfg.replay_chief_only is False

    def test_stage12_draw_reward_is_0_1(self):
        from DuckChess_Game.SBThree.env_registry import make_stage12_config
        from DuckChess_Game.SBThree.base.reward_calculator import TerminalReward
        cfg = make_stage12_config()
        assert isinstance(cfg.reward, TerminalReward)
        assert cfg.reward.draw == pytest.approx(0.1)

    def test_stage11_sparse_rewards(self):
        from DuckChess_Game.SBThree.env_registry import make_stage11_config
        from DuckChess_Game.SBThree.base.reward_calculator import TerminalReward
        cfg = make_stage11_config()
        assert isinstance(cfg.reward, TerminalReward)

    def test_stage10_shaped_rewards(self):
        from DuckChess_Game.SBThree.env_registry import make_stage10_config
        from DuckChess_Game.SBThree.base.reward_calculator import ShapedReward
        cfg = make_stage10_config()
        assert isinstance(cfg.reward, ShapedReward)
        assert cfg.reward.step_penalty == pytest.approx(0.007)

    def test_stage11_league_opponent(self):
        from DuckChess_Game.SBThree.env_registry import make_stage11_config
        from DuckChess_Game.SBThree.base.opponent_strategy import LeagueOpponent
        cfg = make_stage11_config()
        assert isinstance(cfg.opponent, LeagueOpponent)
        assert cfg.opponent.alpha_beta_prob == pytest.approx(0.30)

    def test_stage12_league_opponent_no_alpha_beta(self):
        from DuckChess_Game.SBThree.env_registry import make_stage12_config
        from DuckChess_Game.SBThree.base.opponent_strategy import LeagueOpponent
        cfg = make_stage12_config()
        assert isinstance(cfg.opponent, LeagueOpponent)
        assert cfg.opponent.alpha_beta_prob == pytest.approx(0.0)
