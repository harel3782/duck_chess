from DuckChess_Game.Logic.constants import *

class MoveExecutor:
	"""Executes physical board changes including En Passant and Castling."""

	def execute_piece_move(self, board, start, end, en_passant_target=None):
		"""Moves a piece and handles special cases like Castling and EP."""
		sr, sc = start
		er, ec = end
		piece = board[sr][sc]
		captured = board[er][ec]

		# 1. Handle En Passant Capture
		if piece.type == PAWN and (er, ec) == en_passant_target:
			captured = board[sr][ec]
			board[sr][ec] = None

		# 2. Handle Castling (King moves 2 squares)
		if piece.type == KING and abs(sc - ec) == 2:
			rook_sr = sr
			rook_sc = 7 if ec > sc else 0
			rook_er = sr
			rook_ec = 5 if ec > sc else 3
			
			rook = board[rook_sr][rook_sc]
			if rook:
				board[rook_er][rook_ec] = rook
				board[rook_sr][rook_sc] = None
				rook.has_moved = True

		# 3. Standard Move Execution
		board[er][ec] = piece
		board[sr][sc] = None
		piece.has_moved = True
		
		return captured