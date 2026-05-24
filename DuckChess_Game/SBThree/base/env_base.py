"""
BaseDuckChessEnv — unified Gymnasium environment for all Duck Chess RL stages.

All stage-specific behaviour is injected via EnvConfig:
  opponent  — OpponentStrategy   how the opponent selects moves
  reward    — RewardCalculator   how reward is computed each step
  mask      — MaskStrategy       which actions the learning agent (and opponent) see
"""
from __future__ import annotations

import os
import pickle
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from DuckChess_Game.Logic.logic import GameLogicMixin
from DuckChess_Game.SBThree.base.mask_strategy import MaskStrategy, StandardMask
from DuckChess_Game.SBThree.base.opponent_strategy import OpponentStrategy
from DuckChess_Game.SBThree.base.reward_calculator import RewardCalculator


# ------------------------------------------------------------------ #
# Headless engine (shared across all stages)                           #
# ------------------------------------------------------------------ #

class _HeadlessEngine(GameLogicMixin):
    """Pygame-free game engine for RL training."""

    def __init__(self) -> None:
        self.game_mode = 'rl_training'
        self.reset_game_state()


# ------------------------------------------------------------------ #
# Configuration dataclass                                              #
# ------------------------------------------------------------------ #

@dataclass
class EnvConfig:
    """All tunable parameters for one Duck Chess RL stage."""

    stage_name: str
    opponent: OpponentStrategy
    reward: RewardCalculator
    mask: MaskStrategy = field(default_factory=StandardMask)
    randomize_color: bool = True
    replay_dir: str = "saved_replays"
    replay_every: int = 1000   # episodes between saves; 0 = never
    replay_chief_only: bool = True  # only env_index==0 saves replays


# ------------------------------------------------------------------ #
# Base environment                                                     #
# ------------------------------------------------------------------ #

class BaseDuckChessEnv(gym.Env):
    """
    Unified Gymnasium environment for all Duck Chess RL stages.
    Pass an EnvConfig to get the full behaviour of any curriculum stage.
    """

    metadata: dict = {"render_modes": []}

    def __init__(
        self,
        config: EnvConfig,
        env_index: int = 0,
        render_mode=None,
    ) -> None:
        super().__init__()

        self._config = config
        self.env_index = env_index
        self.render_mode = render_mode

        self._opponent: OpponentStrategy = config.opponent
        self._reward: RewardCalculator = config.reward
        self._mask: MaskStrategy = config.mask

        self.action_space = spaces.Discrete(4096)
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(19, 8, 8), dtype=np.float32
        )

        self.engine: _HeadlessEngine = _HeadlessEngine()
        self.learning_color: str = 'w'
        self.opponent_color: str = 'b'
        self.episode_counter: int = 0
        self.current_episode_actions: List[int] = []

    # ---- Gymnasium interface ---------------------------------------- #

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.engine.reset_game_state()
        self.current_episode_actions = []
        self.episode_counter += 1

        if self._config.randomize_color:
            self.learning_color = np.random.choice(['w', 'b'])
        else:
            self.learning_color = 'w'
        self.opponent_color = 'b' if self.learning_color == 'w' else 'w'

        # If the agent plays black, the opponent moves first
        if self.learning_color == 'b':
            self._play_opponent_turn()

        return self.engine._get_obs(), {}

    def step(self, action: int):
        # Stalemate guard — agent has no legal moves
        if not np.any(self._mask.get_masks(self.engine)):
            return self.engine._get_obs(), 0.0, True, False, {}

        pre = self._reward.capture_pre_state(self.engine, action, self.learning_color)
        self._apply_action(action)
        self.current_episode_actions.append(int(action))
        post = self._reward.capture_post_state(self.engine, self.learning_color)

        terminated = getattr(self.engine, 'game_over', False)

        # After the agent's duck placement the phase flips back to move_piece —
        # that is the signal that the agent's full turn (piece + duck) is done.
        if not terminated and self.engine.phase == 'move_piece':
            self._play_opponent_turn()
            terminated = getattr(self.engine, 'game_over', False)

        reward = self._reward.calculate(
            pre, post, self.engine, self.learning_color, terminated
        )

        if terminated:
            self._maybe_save_replay()

        return self.engine._get_obs(), reward, terminated, False, {}

    def action_masks(self) -> np.ndarray:
        return self._mask.get_masks(self.engine)

    def render(self) -> None:
        pass

    def close(self) -> None:
        pass

    # ---- Opponent hot-swap (called by LeagueCallback) --------------- #

    def set_opponent(self, latest_path: str) -> None:
        """Load a single model as the opponent (Stages 1–9)."""
        self._opponent.set_model(latest_path)

    def set_opponents(
        self,
        latest_path: str,
        historical_path: Optional[str] = None,
    ) -> None:
        """Load latest + historical models for league play (Stages 10+)."""
        self._opponent.set_model(latest_path, historical_path)

    # ---- Internal helpers ------------------------------------------- #

    def _apply_action(self, action: int) -> None:
        start, end = self.engine._decode_move(action)
        if self.engine.phase == 'move_piece':
            self.engine.execute_move(start, end, animated=False)
        else:
            self.engine.place_duck(end, animated=False)

    def _play_opponent_turn(self) -> None:
        while (
            self.engine.turn == self.opponent_color
            and not getattr(self.engine, 'game_over', False)
        ):
            opp_masks = self._mask.get_masks(self.engine)
            if not np.any(opp_masks):
                self.engine.game_over = True
                self.engine.winner = 'draw'
                break
            opp_action = self._opponent.get_action(self.engine, opp_masks)
            self._apply_action(opp_action)
            self.current_episode_actions.append(int(opp_action))

    def _maybe_save_replay(self, reason: str = "periodic") -> None:
        if self._config.replay_every <= 0:
            return
        if self._config.replay_chief_only and self.env_index != 0:
            return
        if self.episode_counter % self._config.replay_every == 0:
            self._save_replay(reason)

    def _save_replay(self, reason: str = "periodic") -> None:
        save_dir = os.path.join(self._config.replay_dir, self._config.stage_name)
        os.makedirs(save_dir, exist_ok=True)
        safe_reason = "".join(c for c in reason if c.isalnum() or c == '_')[:30]
        uid = uuid.uuid4().hex[:6]
        pid = os.getpid()
        fname = os.path.join(
            save_dir,
            f"{safe_reason}_ep{self.episode_counter}_{uid}_pid{pid}_{int(time.time())}.pkl",
        )
        try:
            with open(fname, 'wb') as f:
                pickle.dump(
                    {
                        'action_history': self.current_episode_actions,
                        'learning_color': self.learning_color,
                    },
                    f,
                )
        except Exception:
            pass
