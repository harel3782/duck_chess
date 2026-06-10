import numpy as np
import os
from typing import Dict, Any

from DuckChess_Game.SBThree.base.env_base import BaseDuckChessEnv, EnvConfig
from DuckChess_Game.SBThree.base.reward_calculator import RewardCalculator
from DuckChess_Game.SBThree.base.opponent_strategy import (
	OpponentStrategy, RandomOpponent, AlphaBetaOpponent
)
from DuckChess_Game.SBThree.base.mask_strategy import StandardMask
from DuckChess_Game.Logic.rules_checker import RulesChecker


class TacticalReward(RewardCalculator):
	"""
	Progressive tactical reward for Stage 14 Recovery.
	Builds on Stage 13's dense signals with slightly reduced weights.
	Signals: material capture (moderate weight), undefended loss (penalty),
	check bonus (tactical reward).
	"""

	def __init__(
		self,
		material_weight: float = 0.2,
		loss_multiplier: float = 2.0,
		check_bonus: float = 0.1,
		win: float = 1.0,
		loss: float = -1.0,
		draw: float = 0.0,
	):
		self.material_weight = material_weight
		self.loss_multiplier = loss_multiplier
		self.check_bonus = check_bonus
		self.win = win
		self.loss = loss
		self.draw = draw

	def capture_pre_state(self, engine, action, learning_color: str) -> Dict[str, Any]:
		"""Snapshot material score before action."""
		from DuckChess_Game.Logic.logic import GameLogicMixin

		material = engine.calculate_material_score(engine.board)
		# Adjust sign: positive = white advantage
		if learning_color == 'b':
			material = -material
		return {"material": material}

	def capture_post_state(self, engine, learning_color: str) -> Dict[str, Any]:
		"""
		Snapshot material score and opponent check status after action.
		Check bonus is only meaningful after piece phase (before duck placement).
		"""
		from DuckChess_Game.Logic.logic import GameLogicMixin

		material = engine.calculate_material_score(engine.board)
		if learning_color == 'b':
			material = -material

		opponent_color = 'w' if learning_color == 'b' else 'b'
		opp_in_check = False

		# Only signal check after piece move (move_piece phase completed, before duck phase)
		if engine.phase == 'move_piece':
			checker = RulesChecker()
			opp_in_check = checker.is_in_check(opponent_color, engine.board, engine.duck_pos)

		return {"material": material, "opp_in_check": opp_in_check}

	def calculate(self, pre: Dict, post: Dict, engine, learning_color: str, terminated: bool) -> float:
		"""
		Assemble reward from material deltas, check bonus, and terminal signal.
		"""
		if terminated:
			if engine.winner == learning_color:
				return self.win
			elif engine.winner in ('draw', None):
				return self.draw
			else:
				return self.loss

		reward = 0.0

		# Material capture reward with asymmetric loss penalty
		mat_delta = post["material"] - pre["material"]
		if mat_delta >= 0:
			reward += mat_delta * self.material_weight
		else:
			# Penalize undefended loss
			reward += mat_delta * self.material_weight * self.loss_multiplier

		# Check bonus: reward for giving check
		if post.get("opp_in_check", False):
			reward += self.check_bonus

		return reward


class Stage14Opponent(OpponentStrategy):
	"""
	Balanced 50/50 blend of AlphaBeta greedy and Random.
	Progressive recovery opponent pool — less brutal than Stage 13.
	Static opponent pool — no dynamic updates.
	"""

	def __init__(self):
		"""Initialize with fixed AlphaBeta and Random."""
		self._alpha_beta = AlphaBetaOpponent()
		self._random = RandomOpponent()

	def get_action(self, engine, masks: np.ndarray) -> int:
		"""
		Stochastic opponent selection: 50% AlphaBeta (greedy material),
		50% Random (balance without Stage 11 reference harshness).
		"""
		if np.random.rand() < 0.5:
			return self._alpha_beta.get_action(engine, masks)
		else:
			return self._random.get_action(engine, masks)

	def set_model(self, latest_path, historical_path=None):
		"""
		Intentionally no-op. Stage 14 uses a static opponent pool.
		This prevents external callbacks from accidentally enabling dynamic updates.
		"""
		pass


def make_stage14_config() -> EnvConfig:
	"""Factory for Stage 14 Progressive Recovery environment configuration."""
	return EnvConfig(
		stage_name="stage14_recovery",
		opponent=Stage14Opponent(),
		reward=TacticalReward(
			material_weight=0.2,
			loss_multiplier=2.0,
			check_bonus=0.1,
			win=1.0,
			loss=-1.0,
			draw=0.0,
		),
		mask=StandardMask(),
		randomize_color=True,
		replay_every=1000,
		replay_chief_only=True,
	)


class DuckChessEnvStage14(BaseDuckChessEnv):
	"""Stage 14 Progressive Recovery: consolidate entropy recovery with stable learning."""

	def __init__(self, render_mode=None, env_index=0):
		super().__init__(make_stage14_config(), env_index=env_index, render_mode=render_mode)
