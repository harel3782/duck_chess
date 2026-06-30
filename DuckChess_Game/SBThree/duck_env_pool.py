"""
duck_env_pool.py — v2 training environment: per-episode opponent pool + random starts.

Fixes the two structural causes of the king-rush exploit (see PLAN_V2.md):

  1. Opponent monoculture  -> each episode samples its opponent from a pool
     (Peter d1/d2/d3, self-play latest, historical checkpoint, random mover),
     so no single fixed opponent can be exploited.
  2. Fixed starting position -> a fraction of episodes begin after k random
     legal plies for BOTH sides, so memorized opening lines stop working.

Reward is sparse terminal (win +1 / loss -1 / draw 0). Besides being the
correct anti-exploit practice, this makes the PPO value head a calibrated
win-probability estimator — which search.py later uses as its leaf evaluator.

The terminal `info` dict carries {'opponent': name, 'outcome': win|loss|draw}
so the training callback can track per-opponent win rates (exploit alarm:
win rate spiking vs ONE pool member while entropy collapses).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from DuckChess_Game.SBThree.base.env_base import BaseDuckChessEnv, EnvConfig
from DuckChess_Game.SBThree.base.mask_strategy import ForcedKingCaptureMask
from DuckChess_Game.SBThree.base.opponent_strategy import (
    RandomOpponent, SelfPlayOpponent,
)
from DuckChess_Game.SBThree.base.reward_calculator import TerminalReward
from DuckChess_Game.SBThree.peter_local import PeterLocalOpponent


# Pool weights: ~50% Peter (depth randomized), ~30% self-play latest,
# ~20% historical checkpoints + random mover. See PLAN_V2.md Step 1.
DEFAULT_POOL_WEIGHTS: Dict[str, float] = {
    "peter_d1":  0.10,
    "peter_d2":  0.20,
    "peter_d3":  0.20,
    "sp_latest": 0.30,
    "sp_hist":   0.10,
    "random":    0.10,
}


class PoolEnv(BaseDuckChessEnv):
    """BaseDuckChessEnv that re-samples its opponent every episode."""

    def __init__(
        self,
        env_index: int = 0,
        pool_weights: Optional[Dict[str, float]] = None,
        random_start_prob: float = 0.4,
        random_start_turns: Tuple[int, int] = (2, 8),
        stage_name: str = "v2_pool",
        replay_every: int = 0,
        hist_seed_paths: Optional[Sequence[str]] = None,
    ) -> None:
        self._weights = dict(pool_weights or DEFAULT_POOL_WEIGHTS)
        self.random_start_prob = random_start_prob
        self.random_start_turns = random_start_turns

        self._peters: Dict[str, PeterLocalOpponent] = {
            f"peter_d{d}": PeterLocalOpponent(depth=d, seed=1000 + env_index * 10 + d)
            for d in (1, 2, 3)
        }
        self._sp_latest = SelfPlayOpponent()
        self._sp_hist = SelfPlayOpponent()
        self._random = RandomOpponent()
        self._strategies = {
            **self._peters,
            "sp_latest": self._sp_latest,
            "sp_hist": self._sp_hist,
            "random": self._random,
        }
        # Until the first v2 checkpoint exists, self-play slots can be seeded
        # with old-generation models (rush-style) — defending against the rush
        # is exactly the skill the new model needs.
        if hist_seed_paths:
            seeds = list(hist_seed_paths)
            self._sp_latest.set_model(seeds[0])
            self._sp_hist.set_model(seeds[-1])

        self._active_name: str = "random"
        self._active_peter: Optional[PeterLocalOpponent] = None
        self._rng = np.random.default_rng(20260612 + env_index)

        config = EnvConfig(
            stage_name=stage_name,
            opponent=self._random,
            reward=TerminalReward(win=1.0, loss=-1.0, draw=0.0),
            mask=ForcedKingCaptureMask(),
            randomize_color=True,
            replay_every=replay_every,
            replay_chief_only=True,
        )
        super().__init__(config, env_index=env_index)

    # ---- per-episode opponent sampling ------------------------------ #

    def reset(self, seed=None, options=None):
        # Retry guard: random-start plies can (rarely) end the game.
        for _ in range(10):
            obs, info = self._reset_once(seed)
            if not getattr(self.engine, "game_over", False):
                return obs, info
        return obs, info

    def _reset_once(self, seed):
        names = list(self._weights)
        probs = np.array([self._weights[n] for n in names], dtype=np.float64)
        probs /= probs.sum()
        self._active_name = str(self._rng.choice(names, p=probs))
        self._opponent = self._strategies[self._active_name]
        self._active_peter = self._peters.get(self._active_name)
        if self._active_peter is not None:
            self._active_peter.reset()

        obs, info = super().reset(seed=seed)

        if (
            not getattr(self.engine, "game_over", False)
            and self._rng.random() < self.random_start_prob
        ):
            self._randomize_start()
            obs = self.engine._get_obs()
        return obs, info

    def _randomize_start(self) -> None:
        """Play random legal half-moves for BOTH sides, ending on the agent's
        piece-move phase. Mirrored to Peter's shadow engine via _apply_action."""
        lo, hi = self.random_start_turns
        target = int(self._rng.integers(lo, hi + 1)) * 4  # full turn-pairs -> half-moves
        n = 0
        while n < target or not (
            self.engine.turn == self.learning_color
            and self.engine.phase == "move_piece"
        ):
            if getattr(self.engine, "game_over", False) or n > 200:
                return
            masks = self._mask.get_masks(self.engine)
            valid = np.where(masks)[0]
            if len(valid) == 0:
                return
            self._apply_action(int(self._rng.choice(valid)))
            n += 1

    # ---- Peter shadow-engine mirroring (only when Peter is active) --- #

    def _apply_action(self, action: int) -> None:
        is_duck = self.engine.phase == "move_duck"
        super()._apply_action(action)
        if self._active_peter is not None:
            self._active_peter.mirror_action(action, is_duck_phase=is_duck)

    # ---- terminal info for per-opponent win-rate tracking ------------ #

    def step(self, action: int):
        obs, reward, terminated, truncated, info = super().step(action)
        if terminated:
            winner = getattr(self.engine, "winner", None)
            info = dict(info)
            info["opponent"] = self._active_name
            if winner in (None, "draw"):
                info["outcome"] = "draw"
            else:
                info["outcome"] = "win" if winner == self.learning_color else "loss"
        return obs, reward, terminated, truncated, info

    # ---- league hot-swap (called by the training callback) ----------- #

    def set_opponents(self, latest_path: str, historical_path: Optional[str] = None) -> None:
        self._sp_latest.set_model(latest_path)
        if historical_path:
            self._sp_hist.set_model(historical_path)
