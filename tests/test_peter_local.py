"""
Tests for DuckChess_Game/SBThree/peter_local.py

These tests are hermetic: they do NOT import the 'engine' pyo3 wheel.
All tests that need PeterLocalOpponent.reset() or get_action() mock the
engine module so the suite runs without the wheel being installed.

Square-index arithmetic and _decode_move helpers are tested on raw math,
independent of both the engine and the game logic.
"""
import importlib
import json
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np


# ------------------------------------------------------------------ #
# Helpers to import the module without the 'engine' wheel             #
# ------------------------------------------------------------------ #

def _get_peter_local():
    """Return the peter_local module (import-cached)."""
    return importlib.import_module("DuckChess_Game.SBThree.peter_local")


# ------------------------------------------------------------------ #
# 1. Square-index conversion                                           #
# ------------------------------------------------------------------ #

class TestSquareConversion(unittest.TestCase):
    def setUp(self):
        self.pl = _get_peter_local()

    def test_a1_roundtrip(self):
        # a1: Peter=0, our=(row=7, col=0, sq=56)
        our = self.pl._peter_sq_to_our_sq(0)
        self.assertEqual(our, 56)
        self.assertEqual(self.pl._our_sq_to_peter_sq(56), 0)

    def test_a8_roundtrip(self):
        # a8: Peter=56, our=(row=0, col=0, sq=0)
        our = self.pl._peter_sq_to_our_sq(56)
        self.assertEqual(our, 0)
        self.assertEqual(self.pl._our_sq_to_peter_sq(0), 56)

    def test_h1_roundtrip(self):
        # h1: Peter=7, our=(row=7, col=7, sq=63)
        our = self.pl._peter_sq_to_our_sq(7)
        self.assertEqual(our, 63)
        self.assertEqual(self.pl._our_sq_to_peter_sq(63), 7)

    def test_h8_roundtrip(self):
        # h8: Peter=63, our=(row=0, col=7, sq=7)
        our = self.pl._peter_sq_to_our_sq(63)
        self.assertEqual(our, 7)
        self.assertEqual(self.pl._our_sq_to_peter_sq(7), 63)

    def test_e2_roundtrip(self):
        # e2: rank=2, file=e(4) → Peter=12; our row=6,col=4 → sq=52
        peter_sq = 1 * 8 + 4   # rank-1 * 8 + file
        our_sq   = 6 * 8 + 4
        self.assertEqual(self.pl._peter_sq_to_our_sq(peter_sq), our_sq)
        self.assertEqual(self.pl._our_sq_to_peter_sq(our_sq), peter_sq)

    def test_e4_roundtrip(self):
        # e4: Peter=28, our=(row=4, col=4, sq=36)
        peter_sq = 3 * 8 + 4
        our_sq   = 4 * 8 + 4
        self.assertEqual(self.pl._peter_sq_to_our_sq(peter_sq), our_sq)
        self.assertEqual(self.pl._our_sq_to_peter_sq(our_sq), peter_sq)

    def test_all_64_squares_roundtrip(self):
        """Every square must roundtrip through both directions."""
        pl = self.pl
        for p in range(64):
            s = pl._peter_sq_to_our_sq(p)
            self.assertEqual(pl._our_sq_to_peter_sq(s), p,
                             f"Peter sq {p} did not roundtrip via our sq {s}")
        for s in range(64):
            p = pl._our_sq_to_peter_sq(s)
            self.assertEqual(pl._peter_sq_to_our_sq(p), s,
                             f"Our sq {s} did not roundtrip via peter sq {p}")


# ------------------------------------------------------------------ #
# 2. Action-index conversion                                           #
# ------------------------------------------------------------------ #

class TestActionConversion(unittest.TestCase):
    def setUp(self):
        self.pl = _get_peter_local()

    def test_regular_move_a2_a3(self):
        # Peter: a2(8) → a3(16);  our: sq52 → sq40; action = 52*64+40 = 3368
        pl = self.pl
        peter_from, peter_to = 8, 16
        expected_our_action = pl._peter_sq_to_our_sq(peter_from) * 64 + pl._peter_sq_to_our_sq(peter_to)
        self.assertEqual(pl._peter_move_to_our_action(peter_from, peter_to), expected_our_action)

    def test_duck_move_to_a2(self):
        # Peter duck: from==to==8 (a2).  Our encoding: 0*64 + our_sq_of_a2
        pl = self.pl
        peter_sq = 8   # a2
        our_to = pl._peter_sq_to_our_sq(peter_sq)
        expected = our_to   # 0 * 64 + our_to
        self.assertEqual(pl._peter_move_to_our_action(peter_sq, peter_sq), expected)

    def test_duck_move_action_is_less_than_64(self):
        # All duck actions should be in [0, 63] since from_sq is always 0
        pl = self.pl
        for p in range(64):
            action = pl._peter_move_to_our_action(p, p)
            self.assertLess(action, 64,
                            f"Duck action {action} for peter_sq {p} should be < 64")

    def test_regular_move_encode_decode_roundtrip(self):
        # For every pair of distinct squares, converting to action and back must be consistent.
        pl = self.pl
        for pf in range(0, 64, 8):       # sample from every rank
            for pt in range(0, 64, 11):  # sample sparse
                if pf == pt:
                    continue
                action = pl._peter_move_to_our_action(pf, pt)
                our_from_sq = action >> 6
                our_to_sq   = action & 63
                # Converting back to Peter must match
                self.assertEqual(pl._our_sq_to_peter_sq(our_from_sq), pf)
                self.assertEqual(pl._our_sq_to_peter_sq(our_to_sq),   pt)

    def test_our_action_to_peter_move_regular(self):
        # Regular piece move: our action 3368 → a2-a3 in Peter
        pl  = self.pl
        our_from = pl._peter_sq_to_our_sq(8)   # a2
        our_to   = pl._peter_sq_to_our_sq(16)  # a3
        action   = our_from * 64 + our_to

        result = pl._our_action_to_peter_move_json(action, is_duck_phase=False)
        m = json.loads(result)
        self.assertEqual(m["from"], 8)
        self.assertEqual(m["to"],   16)

    def test_our_action_to_peter_move_duck(self):
        # Duck placement to a2 (our sq 48): Peter must have from==to==8
        pl     = self.pl
        our_to = pl._peter_sq_to_our_sq(8)  # 48
        action = our_to                     # duck: 0 * 64 + our_to

        result = pl._our_action_to_peter_move_json(action, is_duck_phase=True)
        m = json.loads(result)
        self.assertEqual(m["from"], 8)
        self.assertEqual(m["to"],   8)


# ------------------------------------------------------------------ #
# 3. PeterLocalOpponent (mocked engine)                               #
# ------------------------------------------------------------------ #

def _make_mock_engine_module(run_return=None):
    """
    Return a fake 'engine' module whose Engine() acts like the pyo3 wheel.

    run_return — if given, Engine.run() returns json.dumps({"eval":0,"moves":[run_return]})
                 otherwise returns {"eval":0,"moves":[]}
    """
    pv_moves = [run_return] if run_return else []
    pv_json  = json.dumps({"eval": 0, "moves": pv_moves})

    engine_instance = MagicMock()
    engine_instance.run.return_value = pv_json
    engine_instance.apply_move.return_value = None   # success

    engine_mod = types.ModuleType("engine")
    engine_mod.Engine = MagicMock(return_value=engine_instance)
    return engine_mod, engine_instance


class TestPeterLocalOpponent(unittest.TestCase):
    def setUp(self):
        self.pl = _get_peter_local()

    def _make_opp(self, run_return=None):
        eng_mod, eng_inst = _make_mock_engine_module(run_return)
        opp = self.pl.PeterLocalOpponent(depth=3, seed=0)
        # Inject mocked module instead of real pyo3 wheel
        opp._engine_mod = eng_mod
        opp._peter = eng_mod.Engine()
        opp._peter.run.return_value = json.dumps(
            {"eval": 0, "moves": [run_return] if run_return else []}
        )
        opp._peter.apply_move.return_value = None
        return opp

    # ---- reset ---------------------------------------------------- #

    def test_reset_creates_engine(self):
        eng_mod, _ = _make_mock_engine_module()
        opp = self.pl.PeterLocalOpponent(depth=2, seed=7)
        opp._engine_mod = eng_mod
        opp.reset()
        eng_mod.Engine.assert_called_once_with(seed=7, care_about_threefold=True)

    def test_reset_replaces_engine(self):
        eng_mod, inst1 = _make_mock_engine_module()
        opp = self.pl.PeterLocalOpponent(depth=2, seed=0)
        opp._engine_mod = eng_mod
        opp.reset()
        first = opp._peter
        opp.reset()
        # Engine() should have been called twice
        self.assertEqual(eng_mod.Engine.call_count, 2)

    # ---- get_action ----------------------------------------------- #

    def test_get_action_regular_move(self):
        # Peter returns move {from:8, to:16} (a2→a3)
        pl  = self.pl
        opp = self._make_opp(run_return={"from": 8, "to": 16})

        our_from = pl._peter_sq_to_our_sq(8)
        our_to   = pl._peter_sq_to_our_sq(16)
        expected = our_from * 64 + our_to

        masks = np.zeros(4096, dtype=bool)
        masks[expected] = True

        self.assertEqual(opp.get_action(None, masks), expected)

    def test_get_action_duck_move(self):
        # Peter returns duck move {from:8, to:8}
        pl  = self.pl
        opp = self._make_opp(run_return={"from": 8, "to": 8})

        our_to   = pl._peter_sq_to_our_sq(8)   # 48
        expected = our_to                       # 0 * 64 + 48

        masks = np.zeros(4096, dtype=bool)
        masks[expected] = True

        self.assertEqual(opp.get_action(None, masks), expected)

    def test_get_action_falls_back_when_no_pv(self):
        # Peter returns empty PV → fallback to first valid mask entry
        opp = self._make_opp(run_return=None)
        masks = np.zeros(4096, dtype=bool)
        masks[123] = True
        action = opp.get_action(None, masks)
        self.assertEqual(action, 123)

    def test_get_action_falls_back_when_move_not_in_mask(self):
        # Peter's move is not in mask → random from valid
        pl  = self.pl
        opp = self._make_opp(run_return={"from": 8, "to": 16})

        masks = np.zeros(4096, dtype=bool)
        masks[999] = True   # Peter's move is NOT here

        action = opp.get_action(None, masks)
        self.assertEqual(action, 999)   # only valid choice

    def test_get_action_all_masked_returns_zero(self):
        opp = self._make_opp(run_return=None)
        masks = np.zeros(4096, dtype=bool)
        self.assertEqual(opp.get_action(None, masks), 0)

    # ---- mirror_action -------------------------------------------- #

    def test_mirror_regular_move(self):
        pl  = self.pl
        opp = self._make_opp()

        our_from = pl._peter_sq_to_our_sq(8)    # a2 → our sq 48
        our_to   = pl._peter_sq_to_our_sq(16)   # a3 → our sq 40
        action   = our_from * 64 + our_to

        opp.mirror_action(action, is_duck_phase=False)

        call_args = opp._peter.apply_move.call_args[0][0]
        m = json.loads(call_args)
        self.assertEqual(m["from"], 8)
        self.assertEqual(m["to"],   16)

    def test_mirror_duck_move(self):
        pl  = self.pl
        opp = self._make_opp()

        our_to = pl._peter_sq_to_our_sq(8)   # a2 → 48
        action = our_to                       # 0 * 64 + 48

        opp.mirror_action(action, is_duck_phase=True)

        call_args = opp._peter.apply_move.call_args[0][0]
        m = json.loads(call_args)
        self.assertEqual(m["from"], 8)
        self.assertEqual(m["to"],   8)

    def test_mirror_does_nothing_before_reset(self):
        pl  = self.pl
        opp = self.pl.PeterLocalOpponent(depth=3)
        # _peter is None → should not raise
        opp.mirror_action(42, is_duck_phase=False)   # no crash

    def test_set_model_is_noop(self):
        opp = self.pl.PeterLocalOpponent(depth=3)
        opp.set_model("any", "args")   # no crash, no effect


# ------------------------------------------------------------------ #
# 4. PeterLocalEnv (integration, mocked engine + headless game)       #
# ------------------------------------------------------------------ #

class TestPeterLocalEnv(unittest.TestCase):
    """
    Smoke-tests for PeterLocalEnv.  We mock PeterLocalOpponent so the
    test never touches pyo3 or the game logic's subprocess.
    """

    def setUp(self):
        self.pl = _get_peter_local()

    def _make_env(self, depth=3):
        from DuckChess_Game.SBThree.base.reward_calculator import TerminalReward
        from DuckChess_Game.SBThree.base.mask_strategy import ForcedKingCaptureMask

        opp = self.pl.PeterLocalOpponent(depth=depth)
        # Provide a mocked engine module before reset() is ever called
        eng_mod, _ = _make_mock_engine_module()
        opp._engine_mod = eng_mod

        config = self.pl.make_peter_config(depth=depth, stage_name="test_peter")
        config.opponent = opp   # replace with our pre-injected one

        env = self.pl.PeterLocalEnv(config, env_index=0)
        return env, opp, eng_mod

    def test_reset_calls_opponent_reset(self):
        env, opp, eng_mod = self._make_env()

        # Build a proper mock _peter so get_action() won't crash if the
        # opponent turn fires during reset (agent plays black → opp moves first).
        def _mock_reset():
            peter_mock = MagicMock()
            peter_mock.run.return_value = json.dumps({"eval": 0, "moves": []})
            peter_mock.apply_move.return_value = None
            opp._peter = peter_mock

        opp.reset = MagicMock(side_effect=_mock_reset)
        env.reset()
        opp.reset.assert_called_once()

    def test_env_has_correct_spaces(self):
        env, _, _ = self._make_env()
        self.assertEqual(env.action_space.n, 4096)
        self.assertEqual(env.observation_space.shape, (19, 8, 8))

    def test_apply_action_calls_mirror(self):
        env, opp, eng_mod = self._make_env()
        # Inject a working mock _peter so reset succeeds
        env._opponent._peter = MagicMock()
        env._opponent._peter.apply_move.return_value = None

        # Manually reset game state without calling PeterLocalEnv.reset
        env.engine.reset_game_state()
        env.learning_color = 'w'
        env.opponent_color = 'b'

        # Patch mirror_action to track calls
        opp.mirror_action = MagicMock()

        # Apply a dummy action (regular phase)
        # Use a legal action from the mask instead of guessing
        masks = env.action_masks()
        legal = np.where(masks)[0]
        if len(legal) == 0:
            self.skipTest("No legal actions in starting position — unexpected")
        action = int(legal[0])

        env._apply_action(action)

        opp.mirror_action.assert_called_once()
        call_kwargs = opp.mirror_action.call_args
        self.assertIn(action, call_kwargs[0])   # first positional arg is action


# ------------------------------------------------------------------ #
# 5. Config factories                                                  #
# ------------------------------------------------------------------ #

class TestConfigFactories(unittest.TestCase):
    def setUp(self):
        self.pl = _get_peter_local()

    def test_make_peter_config_returns_envconfig(self):
        from DuckChess_Game.SBThree.base.env_base import EnvConfig
        cfg = self.pl.make_peter_config(depth=3)
        self.assertIsInstance(cfg, EnvConfig)

    def test_make_peter_config_has_peter_opponent(self):
        cfg = self.pl.make_peter_config(depth=2)
        self.assertIsInstance(cfg.opponent, self.pl.PeterLocalOpponent)
        self.assertEqual(cfg.opponent.depth, 2)

    def test_easy_medium_hard_presets(self):
        easy   = self.pl.make_peter_easy_config()
        medium = self.pl.make_peter_medium_config()
        hard   = self.pl.make_peter_hard_config()
        self.assertEqual(easy.opponent.depth,   1)
        self.assertEqual(medium.opponent.depth, 3)
        self.assertEqual(hard.opponent.depth,   5)

    def test_mixed_env_factories_count(self):
        factories = self.pl.make_peter_mixed_env_factories([1, 2, 3, 3])
        self.assertEqual(len(factories), 4)

    def test_mixed_env_factories_return_envs(self):
        factories = self.pl.make_peter_mixed_env_factories([1, 2])
        for factory in factories:
            env = factory()
            self.assertIsInstance(env, self.pl.PeterLocalEnv)
            env.engine.reset_game_state()  # don't crash


# ------------------------------------------------------------------ #
# 6. Registry integration                                              #
# ------------------------------------------------------------------ #

class TestRegistryIntegration(unittest.TestCase):
    def test_peter_stages_in_registry(self):
        from DuckChess_Game.SBThree.env_registry import REGISTRY
        for key in ("peter_easy", "peter_medium", "peter_hard"):
            self.assertIn(key, REGISTRY, f"'{key}' missing from REGISTRY")

    def test_registry_factories_callable(self):
        from DuckChess_Game.SBThree.env_registry import REGISTRY
        pl = _get_peter_local()
        for key in ("peter_easy", "peter_medium", "peter_hard"):
            cfg = REGISTRY[key]()
            self.assertIsInstance(cfg.opponent, pl.PeterLocalOpponent)


if __name__ == "__main__":
    unittest.main(verbosity=2)
