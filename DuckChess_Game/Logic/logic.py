from DuckChess_Game.Logic.constants import *
from DuckChess_Game.Logic.board_manager import BoardManager
from DuckChess_Game.Logic.notation_helper import NotationHelper
from DuckChess_Game.Logic.move_generation import MoveGenerationMixin
from DuckChess_Game.Logic.history_manager import HistoryManagerMixin
from DuckChess_Game.Logic.turn_manager import TurnManagerMixin
from DuckChess_Game.Logic.endgame_checker import EndgameCheckerMixin
from DuckChess_Game.Logic.rl_mixin import RLMixin
from DuckChess_Game.Logic.ai import DuckAI
from DuckChess_Game.Logic.bitboard_manager import BitboardManager

class GameLogicMixin(
	MoveGenerationMixin, 
	HistoryManagerMixin, 
	TurnManagerMixin, 
	EndgameCheckerMixin, 
	RLMixin
):
	"""The central hub connecting all logic modules."""

	def init_ai(self):
		"""Initializes the AI decision engine."""
		self.ai = DuckAI(depth=2)

	def init_board(self):
		"""Initializes a fresh board using BoardManager setup, syncing 2D and 64-bit boards."""
		self.board_mgr = BoardManager()
		self.board = self.board_mgr.create_empty_board()
		
		self.bb_mgr = BitboardManager()

		for piece, r, c in self.board_mgr.get_initial_setup():
			self.board[r][c] = piece
			self.bb_mgr.add_piece(piece.color, piece.type, r, c)

	def sync_bitboards_to_2d(self):
		"""Forces the BitboardManager to perfectly match the current 2D board state."""
		self.bb_mgr = BitboardManager()
		for r in range(8):
			for c in range(8):
				p = self.board[r][c]
				if p:
					self.bb_mgr.add_piece(p.color, p.type, r, c)
		if hasattr(self, 'duck_pos') and self.duck_pos != (-1, -1):
			self.bb_mgr.move_duck(self.duck_pos[0], self.duck_pos[1])

	def validate_editor_board(self):
		"""Kings consistency check."""
		w_k = sum(1 for r in range(8) for c in range(8) if self.board[r][c] and self.board[r][c].type == KING and self.board[r][c].color == 'w')
		b_k = sum(1 for r in range(8) for c in range(8) if self.board[r][c] and self.board[r][c].type == KING and self.board[r][c].color == 'b')
		return w_k == 1 and b_k == 1