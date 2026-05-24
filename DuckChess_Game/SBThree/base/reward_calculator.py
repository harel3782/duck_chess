"""
Reward calculator implementations for Duck Chess RL environments.

Each calculator exposes three methods called by BaseDuckChessEnv.step():
  1. capture_pre_state(engine, action, learning_color)  — before _apply_action
  2. capture_post_state(engine, learning_color)          — after _apply_action, before opponent
  3. calculate(pre, post, engine, learning_color, terminated) -> float

Keeping state capture and reward maths inside the calculator means
BaseDuckChessEnv.step() is strategy-agnostic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

import numpy as np


# ------------------------------------------------------------------ #
# Abstract base                                                        #
# ------------------------------------------------------------------ #

class RewardCalculator(ABC):

	@abstractmethod
	def capture_pre_state(self, engine, action: int, learning_color: str) -> Dict[str, Any]:
		"""Snapshot the game state BEFORE the learning agent acts."""
		...

	@abstractmethod
	def capture_post_state(self, engine, learning_color: str) -> Dict[str, Any]:
		"""
		Snapshot game state AFTER _apply_action but BEFORE the opponent plays.
		This is the point at which shaped intermediate rewards are evaluated.
		"""
		...

	@abstractmethod
	def calculate(
		self,
		pre: Dict[str, Any],
		post: Dict[str, Any],
		engine,
		learning_color: str,
		terminated: bool,
	) -> float:
		"""Compute the scalar reward for this step."""
		...


# ------------------------------------------------------------------ #
# Terminal-only (sparse) reward                                        #
# ------------------------------------------------------------------ #

class TerminalReward(RewardCalculator):
	"""
	Returns 0.0 for all non-terminal steps.
	Ideal for PPO-based learning where gamma handles credit assignment.
	"""

	def __init__(self, win: float = 1.0, loss: float = -1.0, draw: float = 0.0) -> None:
		self.win = win
		self.loss = loss
		self.draw = draw

	def capture_pre_state(self, engine, action: int, learning_color: str) -> Dict:
		return {}

	def capture_post_state(self, engine, learning_color: str) -> Dict:
		return {}

	def calculate(self, pre, post, engine, learning_color: str, terminated: bool) -> float:
		if not terminated:
			return 0.0
		winner = getattr(engine, 'winner', None)
		if winner == learning_color:
			return self.win
		if winner in ('draw', None):
			return self.draw
		return self.loss


# ------------------------------------------------------------------ #
# Shaped reward (material, positional, endgame)                       #
# ------------------------------------------------------------------ #

class ShapedReward(RewardCalculator):
	"""
	Dense reward shaping used in training stages 4-10.

	Parameters default to 0 so you can enable only the components you need:

	  material_weight   — per-unit material differential reward
	  loss_multiplier   — extra penalty multiplier on material losses
	  castling_bonus    — one-time reward when the learning agent castles
	  development_bonus — reward for moving minor pieces off home rank
	  defense_weight    — reward for reducing check threats on own king
	  blocking_scale    — reward for reducing opponent's duck-phase mobility
	  mobility_scale    — reward proportional to own mobility after duck placement
	  step_penalty      — constant per-step cost (encourages shorter games)
	  endgame_threshold — material advantage above which endgame logic activates
	  king_push_bonus   — reward for pushing opponent king toward board edge
	  win / loss / draw — terminal bonuses (added on top of shaped reward)
	"""

	def __init__(
		self,
		material_weight: float = 0.05,
		loss_multiplier: float = 1.0,
		castling_bonus: float = 0.0,
		development_bonus: float = 0.0,
		defense_weight: float = 0.0,
		blocking_scale: float = 0.0,
		mobility_scale: float = 0.0,
		step_penalty: float = 0.0,
		endgame_threshold: float = float('inf'),
		king_push_bonus: float = 0.0,
		win: float = 1.0,
		loss: float = -1.0,
		draw: float = 0.0,
	) -> None:
		self.material_weight = material_weight
		self.loss_multiplier = loss_multiplier
		self.castling_bonus = castling_bonus
		self.development_bonus = development_bonus
		self.defense_weight = defense_weight
		self.blocking_scale = blocking_scale
		self.mobility_scale = mobility_scale
		self.step_penalty = step_penalty
		self.endgame_threshold = endgame_threshold
		self.king_push_bonus = king_push_bonus
		self.win = win
		self.loss = loss
		self.draw = draw

	# ---- helpers -------------------------------------------------- #

	@staticmethod
	def _count_check(engine, color: str) -> int:
		from DuckChess_Game.Logic.rules_checker import RulesChecker
		return 1 if RulesChecker().is_in_check(color, engine.board, engine.duck_pos) else 0

	@staticmethod
	def _calculate_mobility(engine, color: str) -> int:
		total = 0
		for r in range(8):
			for c in range(8):
				p = engine.board[r][c]
				if p and p.color == color:
					total += len(engine.get_piece_legal_moves(r, c))
		return total

	@staticmethod
	def _find_king(engine, color: str):
		from DuckChess_Game.Logic.constants import KING
		for r in range(8):
			for c in range(8):
				p = engine.board[r][c]
				if p and p.type == KING and p.color == color:
					return (r, c)
		return None

	@staticmethod
	def _center_distance(pos) -> float:
		r, c = pos
		return max(abs(r - 3.5), abs(c - 3.5))

	@staticmethod
	def _development_score(engine, color: str) -> int:
		"""Count minor pieces that have left their home rank."""
		from DuckChess_Game.Logic.constants import KNIGHT, BISHOP
		home_rank = 7 if color == 'w' else 0
		developed = 0
		for r in range(8):
			for c in range(8):
				p = engine.board[r][c]
				if p and p.color == color and p.type in (KNIGHT, BISHOP) and r != home_rank:
					developed += 1
		return developed

	# ---- pre / post capture --------------------------------------- #

	def capture_pre_state(self, engine, action: int, learning_color: str) -> Dict:
		opp_color = 'b' if learning_color == 'w' else 'w'
		phase = engine.phase

		pre: Dict[str, Any] = {
			'phase': phase,
			'material': engine.calculate_material_score(engine.board),
			'threats': self._count_check(engine, learning_color),
		}

		if phase == 'move_piece':
			pre['mobility_learning'] = self._calculate_mobility(engine, learning_color)
			pre['opp_king'] = self._find_king(engine, opp_color)

			# Detect castling BEFORE the move is applied
			start, end = engine._decode_move(action)
			p = engine.board[start[0]][start[1]]
			from DuckChess_Game.Logic.constants import KING
			pre['castling'] = (
				self.castling_bonus
				if p and p.type == KING and abs(start[1] - end[1]) == 2
				else 0.0
			)

			if self.development_bonus:
				pre['development'] = self._development_score(engine, learning_color)
		elif phase == 'move_duck':
			pre['opp_mob'] = self._calculate_mobility(engine, opp_color)

		return pre

	def capture_post_state(self, engine, learning_color: str) -> Dict:
		opp_color = 'b' if learning_color == 'w' else 'w'
		phase = engine.phase   # phase AFTER the action was applied

		post: Dict[str, Any] = {
			'phase': phase,
			'material': engine.calculate_material_score(engine.board),
		}

		# Duck was just placed (phase transitioned to move_piece)
		if phase == 'move_piece':
			post['mobility_learning'] = self._calculate_mobility(engine, learning_color)
			post['threats'] = self._count_check(engine, learning_color)
			post['opp_king'] = self._find_king(engine, opp_color)
			if self.development_bonus:
				post['development'] = self._development_score(engine, learning_color)

		# Piece was just moved (phase transitioned to move_duck)
		elif phase == 'move_duck':
			post['opp_mob'] = self._calculate_mobility(engine, opp_color)

		return post

	# ---- reward --------------------------------------------------- #

	def calculate(self, pre, post, engine, learning_color: str, terminated: bool) -> float:
		reward = 0.0
		opp_color = 'b' if learning_color == 'w' else 'w'
		sign = 1 if learning_color == 'w' else -1

		# --- Terminal bonus ---------------------------------------- #
		if terminated:
			winner = getattr(engine, 'winner', None)
			if winner == learning_color:
				reward += self.win
			elif winner in ('draw', None):
				reward += self.draw
			else:
				reward += self.loss
			return reward

		# --- Material ---------------------------------------------- #
		if self.material_weight:
			mat_pre = pre.get('material', 0)
			mat_post = post.get('material', 0)
			diff = (mat_post - mat_pre) * sign
			if diff < 0:
				diff *= self.loss_multiplier
			reward += diff * self.material_weight

		# --- Step penalty (with endgame scaling) -------------------- #
		if self.step_penalty:
			my_adv = post.get('material', 0) * sign
			if my_adv >= self.endgame_threshold:
				multiplier = 1.0 + my_adv / 5.0
				reward -= self.step_penalty * multiplier
			else:
				reward -= self.step_penalty

		# --- Phase-specific shaped rewards -------------------------- #
		post_phase = post.get('phase', '')

		if post_phase == 'move_piece':
			# Duck was just placed → evaluate post-duck-placement state

			if self.castling_bonus:
				reward += pre.get('castling', 0.0)

			if self.development_bonus:
				dev_pre = pre.get('development', 0)
				dev_post = post.get('development', 0)
				if dev_post > dev_pre:
					reward += (dev_post - dev_pre) * self.development_bonus

			if self.defense_weight:
				threats_pre = pre.get('threats', 0)
				threats_post = post.get('threats', 0)
				if threats_pre > threats_post:
					reward += (threats_pre - threats_post) * self.defense_weight

			if self.mobility_scale:
				reward += post.get('mobility_learning', 0) * self.mobility_scale

			if self.king_push_bonus and self.endgame_threshold < float('inf'):
				my_adv = post.get('material', 0) * sign
				if my_adv >= self.endgame_threshold:
					king_before = pre.get('opp_king')
					king_after = post.get('opp_king')
					if king_before and king_after:
						dist_before = self._center_distance(king_before)
						dist_after = self._center_distance(king_after)
						if dist_after > dist_before:
							reward += (dist_after - dist_before) * self.king_push_bonus

		elif post_phase == 'move_duck':
			# Piece was just moved → evaluate duck-blocking opportunity
			if self.blocking_scale:
				opp_mob_pre = pre.get('opp_mob', 0)
				opp_mob_post = post.get('opp_mob', 0)
				if opp_mob_pre > opp_mob_post:
					reward += (opp_mob_pre - opp_mob_post) * self.blocking_scale

		return reward
