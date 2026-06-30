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
	"""The central hub connecting all logic modules.

	Uses mixin composition so each concern (move gen, history, turn management,
	endgame, RL interface) lives in its own file while sharing game state via self.
	Both UI and RL training inherit from this class.
	"""

	def init_ai(self):
		"""Initializes the alpha-beta AI used as fallback when no RL model is loaded."""
		# Depth 2 = one full turn lookahead (piece + duck) per side; deeper is too slow for UI.
		self.ai = DuckAI(depth=2)

	def init_board(self):
		"""Sets up starting position in both the 2D board and the parallel bitboard."""
		self.board_mgr = BoardManager()
		self.board = self.board_mgr.create_empty_board()

		# Bitboards are maintained alongside the 2D array: the 2D board is the
		# authoritative source of truth for game logic (easy to read/mutate), while
		# BitboardManager accelerates move-generation with 64-bit operations.
		self.bb_mgr = BitboardManager()

		for piece, r, c in self.board_mgr.get_initial_setup():
			self.board[r][c] = piece
			self.bb_mgr.add_piece(piece.color, piece.type, r, c)

	def sync_bitboards_to_2d(self):
		"""Rebuilds the bitboard from scratch to match the current 2D board.

		Called after editor mode or any state reload where the bitboard may have
		drifted from the 2D board. Full rebuild is safer than incremental patching
		because the editor can make arbitrary changes in any order.
		"""
		self.bb_mgr = BitboardManager()
		for r in range(8):
			for c in range(8):
				p = self.board[r][c]
				if p:
					self.bb_mgr.add_piece(p.color, p.type, r, c)
		# duck_pos may not exist yet if the editor was opened before a game started.
		if hasattr(self, 'duck_pos') and self.duck_pos != (-1, -1):
			self.bb_mgr.move_duck(self.duck_pos[0], self.duck_pos[1])

	def validate_editor_board(self):
		"""Checks that the position has exactly one king per side before starting play.

		In Duck Chess there is no check/checkmate, so the only structural requirement
		for a legal starting position is one king each — any other piece arrangement
		is permissible. Zero kings would mean someone has already won; two kings per
		side is unreachable in real play.
		"""
		w_k = sum(1 for r in range(8) for c in range(8) if self.board[r][c] and self.board[r][c].type == KING and self.board[r][c].color == 'w')
		b_k = sum(1 for r in range(8) for c in range(8) if self.board[r][c] and self.board[r][c].type == KING and self.board[r][c].color == 'b')
		return w_k == 1 and b_k == 1