import numpy as np
import os
from typing import Dict, Any

from DuckChess_Game.SBThree.base.env_base import BaseDuckChessEnv, EnvConfig
from DuckChess_Game.SBThree.base.reward_calculator import RewardCalculator
from DuckChess_Game.SBThree.base.opponent_strategy import (
	OpponentStrategy, SelfPlayOpponent, AlphaBetaOpponent
)
from DuckChess_Game.SBThree.base.mask_strategy import StandardMask
from DuckChess_Game.Logic.rules_checker import RulesChecker


class TacticalReward(RewardCalculator):
	"""
	Dense tactical reward for Stage 13 Shock Therapy.
	Signals: material capture (high weight), undefended loss (harsh multiplier),
	check bonus (immediate tactical reward).
	"""

	def __init__(
		self,
		material_weight: float = 0.3,
		loss_multiplier: float = 2.5,
		check_bonus: float = 0.15,
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
			# Penalize undefended loss more harshly
			reward += mat_delta * self.material_weight * self.loss_multiplier

		# Check bonus: immediate reward for giving check
		if post.get("opp_in_check", False):
			reward += self.check_bonus

		return reward


class Stage13Opponent(OpponentStrategy):
	"""
	Fixed 50/50 blend of AlphaBeta greedy and Stage 11 reference model.
	Static opponent pool — no dynamic updates. set_model() is a no-op.
	"""

	STAGE11_PATH = "models/duck_ppo/stage 11/stage11_sparse_v8.zip"

	def __init__(self):
		"""Initialize with fixed AlphaBeta and Stage 11 checkpoint."""
		self._alpha_beta = AlphaBetaOpponent()
		self._stage11 = SelfPlayOpponent()

		# Load Stage 11 reference checkpoint once; never update
		if os.path.exists(self.STAGE11_PATH):
			self._stage11.set_model(self.STAGE11_PATH)
		else:
			# Fallback: if Stage 11 missing, Stage11 will play randomly
			print(f"Warning: Stage 11 checkpoint not found at {self.STAGE11_PATH}")

	def get_action(self, engine, masks: np.ndarray) -> int:
		"""
		Stochastic opponent selection: 50% AlphaBeta (greedy material), 50% Stage 11 model.
		"""
		if np.random.rand() < 0.5:
			return self._alpha_beta.get_action(engine, masks)
		else:
			return self._stage11.get_action(engine, masks)

	def set_model(self, latest_path, historical_path=None):
		"""
		Intentionally no-op. Stage 13 uses a static opponent pool.
		This prevents external callbacks from accidentally enabling dynamic updates.
		"""
		pass


def make_stage13_config() -> EnvConfig:
	"""Factory for Stage 13 Shock Therapy environment configuration."""
	return EnvConfig(
		stage_name="stage13_shock",
		opponent=Stage13Opponent(),
		reward=TacticalReward(
			material_weight=0.3,
			loss_multiplier=2.5,
			check_bonus=0.15,
			win=1.0,
			loss=-1.0,
			draw=0.0,
		),
		mask=StandardMask(),
		randomize_color=True,
		replay_every=1000,
		replay_chief_only=True,
	)


class DuckChessEnvStage13(BaseDuckChessEnv):
	"""Stage 13 Shock Therapy: aggressive recovery from entropy collapse."""

	def __init__(self, render_mode=None, env_index=0):
		super().__init__(make_stage13_config(), env_index=env_index, render_mode=render_mode)
