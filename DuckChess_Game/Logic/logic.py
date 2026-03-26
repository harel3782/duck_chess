from DuckChess_Game.Logic.constants import *
from DuckChess_Game.Logic.board_manager import BoardManager
from DuckChess_Game.Logic.notation_helper import NotationHelper
from DuckChess_Game.Logic.move_generation import MoveGenerationMixin
from DuckChess_Game.Logic.state_manager import StateManagerMixin
from DuckChess_Game.Logic.rl_mixin import RLMixin
from DuckChess_Game.Logic.ai import DuckAI

class GameLogicMixin(MoveGenerationMixin, StateManagerMixin, RLMixin):
	"""The central hub connecting all logic modules[cite: 10]."""

	def init_ai(self):
		"""Initializes the AI decision engine."""
		self.ai = DuckAI(depth=2)

	def init_board(self):
		"""Initializes a fresh board using BoardManager setup [cite: 10-11]."""
		self.board_mgr = BoardManager()
		self.board = self.board_mgr.create_empty_board()
		for piece, r, c in self.board_mgr.get_initial_setup():
			self.board[r][c] = piece

	def validate_editor_board(self):
		"""Kings consistency check[cite: 12, 122]."""
		w_k = sum(1 for r in range(8) for c in range(8) if self.board[r][c] and self.board[r][c].type == KING and self.board[r][c].color == 'w')
		b_k = sum(1 for r in range(8) for c in range(8) if self.board[r][c] and self.board[r][c].type == KING and self.board[r][c].color == 'b')
		return w_k == 1 and b_k == 1