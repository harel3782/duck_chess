from DuckChess_Game.Logic.constants import *

class MoveExecutor:
	"""Executes physical changes to the board state and generates notation."""

	def execute_piece_move(self, board, start, end):
		"""Moves a piece and handles special cases like Castling/EP."""
		sr, sc = start
		er, ec = end
		piece = board[sr][sc]
		target = board[er][ec]

		# Logic for En Passant, Castling, and simple moves...
		board[er][ec] = piece
		board[sr][sc] = None
		piece.has_moved = True
		
		return target # Return captured piece if any