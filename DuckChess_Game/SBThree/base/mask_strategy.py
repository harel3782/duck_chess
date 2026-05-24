"""
Action mask strategy implementations for Duck Chess RL environments.

The mask strategy controls which actions the LEARNING AGENT sees.
It does not affect the opponent (the opponent strategy applies its
own logic when selecting actions).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class MaskStrategy(ABC):
	"""Base class for action masking strategies."""

	@abstractmethod
	def get_masks(self, engine) -> np.ndarray:
		"""Return a boolean array of length 4096 marking valid actions."""
		...


class StandardMask(MaskStrategy):
	"""
	Passes through the engine's legal-move mask with a single safety net:
	if no moves exist (stalemate / edge case) index 0 is enabled so the
	environment never hangs inside SB3's masked sampling.
	"""

	def get_masks(self, engine) -> np.ndarray:
		masks = engine.action_masks()
		if not np.any(masks):
			masks[0] = True
		return masks


class ForcedKingCaptureMask(MaskStrategy):
	"""
	During the piece-move phase: if any legal move captures the enemy king,
	restrict the mask to only those moves.  The learning agent is forced to
	finish a won game immediately rather than stalling.

	Falls back to StandardMask behaviour when no king-capture exists or
	when in the duck-placement phase.
	"""

	def get_masks(self, engine) -> np.ndarray:
		masks = engine.action_masks()
		if not np.any(masks):
			masks[0] = True
			return masks

		if engine.phase == 'move_piece':
			from DuckChess_Game.Logic.constants import KING

			forced = np.zeros(4096, dtype=bool)
			found = False
			board = engine.board

			for action in np.where(masks)[0]:
				_, end = engine._decode_move(int(action))
				target = board[end[0]][end[1]]
				if target and target.type == KING and target.color != engine.turn:
					forced[action] = True
					found = True

			if found:
				return forced

		return masks
