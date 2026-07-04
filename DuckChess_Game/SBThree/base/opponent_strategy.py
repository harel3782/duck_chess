"""
Opponent strategy implementations for Duck Chess RL environments.

Each strategy encapsulates one AI behaviour pattern and exposes a
single `get_action(engine, masks) -> int` interface so the base
environment is completely decoupled from opponent logic.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np


class OpponentStrategy(ABC):
	"""Base class for all opponent AI strategies."""

	@abstractmethod
	def get_action(self, engine, masks: np.ndarray) -> int:
		"""Return a valid action index given the current game state."""
		...

	def set_model(self, latest_path: Optional[str], historical_path: Optional[str] = None) -> None:
		"""Hot-swap the loaded model(s) during league training callbacks."""
		pass


# ------------------------------------------------------------------ #
# Concrete strategies                                                  #
# ------------------------------------------------------------------ #

class RandomOpponent(OpponentStrategy):
	"""Uniform random selection over all valid actions."""

	def get_action(self, engine, masks: np.ndarray) -> int:
		valid = np.where(masks)[0]
		return int(np.random.choice(valid))


class GreedyOpponent(OpponentStrategy):
	"""Prefers any capture over non-captures; falls back to random."""

	def get_action(self, engine, masks: np.ndarray) -> int:
		if engine.phase == 'move_piece':
			captures = []
			for a in np.where(masks)[0]:
				_, end = engine._decode_move(int(a))
				if engine.board[end[0]][end[1]] is not None:
					captures.append(a)
			if captures:
				return int(np.random.choice(captures))
		return int(np.random.choice(np.where(masks)[0]))


class AlphaBetaOpponent(OpponentStrategy):
	"""
	Depth-1 greedy minimax: always captures king if available,
	otherwise picks the move that maximises the opponent's material
	score using a temporary board simulation (no tree search).
	"""

	def get_action(self, engine, masks: np.ndarray) -> int:
		from DuckChess_Game.Logic.constants import KING, PIECE_VALUES

		valid = np.where(masks)[0]
		if len(valid) == 0:
			return 0

		if engine.phase == 'move_piece':
			# King capture always wins immediately
			for a in valid:
				_, end = engine._decode_move(int(a))
				target = engine.board[end[0]][end[1]]
				if target and target.type == KING:
					return int(a)

			# Best material-gain move via board simulation
			opponent_color = engine.turn
			best_score = float('-inf')
			best_action = int(valid[0])

			for a in valid:
				start, end = engine._decode_move(int(a))
				piece = engine.board[start[0]][start[1]]
				target = engine.board[end[0]][end[1]]

				engine.board[end[0]][end[1]] = piece
				engine.board[start[0]][start[1]] = None
				score = engine.calculate_material_score(engine.board)
				val = score if opponent_color == 'w' else -score
				engine.board[start[0]][start[1]] = piece
				engine.board[end[0]][end[1]] = target

				if val > best_score:
					best_score, best_action = val, int(a)

			return best_action

		# Duck phase: random placement
		return int(np.random.choice(valid))


class SelfPlayOpponent(OpponentStrategy):
	"""Uses a single loaded MaskablePPO model; falls back to random."""

	def __init__(self) -> None:
		self._model = None

	def get_action(self, engine, masks: np.ndarray) -> int:
		if self._model is None:
			return int(np.random.choice(np.where(masks)[0]))
		obs = engine._get_obs()
		action, _ = self._model.predict(obs, action_masks=masks, deterministic=False)
		return int(action)

	def set_model(self, latest_path: Optional[str], historical_path: Optional[str] = None) -> None:
		if not latest_path:
			return
		if not os.path.exists(latest_path):
			return
		try:
			from sb3_contrib import MaskablePPO
			self._model = MaskablePPO.load(latest_path, device='cpu')
		except Exception:
			self._model = None


class LeagueOpponent(OpponentStrategy):
	"""
	Configurable league opponent that blends multiple strategies:

	  - ``alpha_beta_prob``:    fraction of moves resolved by AlphaBeta
	  - ``random_prob``:        fraction resolved by pure random choice
	  - ``historical_fraction``: of the remaining budget, how much uses
	                             the historical model (the rest uses latest)

	Typical configurations
	-----------------------
	Stage 10  AlphaBeta=0.0,  random=0.20, hist_frac=0.375  (30% hist, 50% latest)
	Stage 11  AlphaBeta=0.30, random=0.00, hist_frac=0.50   (35% hist, 35% latest)
	Stage 12  AlphaBeta=0.00, random=0.00, hist_frac=0.50   (50% hist, 50% latest)
	"""

	def __init__(
		self,
		alpha_beta_prob: float = 0.0,
		random_prob: float = 0.0,
		historical_fraction: float = 0.5,
	) -> None:
		self.alpha_beta_prob = alpha_beta_prob
		self.random_prob = random_prob
		self.historical_fraction = historical_fraction

		self._latest: Optional[object] = None
		self._historical: Optional[object] = None
		self._alpha_beta = AlphaBetaOpponent()
		self._random = RandomOpponent()

	def get_action(self, engine, masks: np.ndarray) -> int:
		roll = np.random.rand()

		if roll < self.alpha_beta_prob:
			return self._alpha_beta.get_action(engine, masks)
		roll -= self.alpha_beta_prob

		if roll < self.random_prob:
			return self._random.get_action(engine, masks)
		roll -= self.random_prob

		# Remaining budget split between historical and latest
		obs = engine._get_obs()
		if roll < self.historical_fraction and self._historical is not None:
			action, _ = self._historical.predict(obs, action_masks=masks, deterministic=False)
			return int(action)
		if self._latest is not None:
			action, _ = self._latest.predict(obs, action_masks=masks, deterministic=False)
			return int(action)

		return self._random.get_action(engine, masks)

	def set_model(self, latest_path: Optional[str], historical_path: Optional[str] = None) -> None:
		from sb3_contrib import MaskablePPO

		if latest_path and os.path.exists(latest_path):
			try:
				self._latest = MaskablePPO.load(latest_path, device='cpu')
			except Exception:
				self._latest = None

		if historical_path and os.path.exists(historical_path):
			try:
				self._historical = MaskablePPO.load(historical_path, device='cpu')
			except Exception:
				self._historical = None
