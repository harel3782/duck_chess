from DuckChess_Game.Logic.constants import *

class MoveExecutor:
	"""Executes physical board changes including En Passant and Castling in both memory models."""

	def execute_piece_move(self, board, start, end, en_passant_target=None, bb_mgr=None):
		"""Moves a piece and handles special cases like Castling and EP."""
		sr, sc = start
		er, ec = end
		# Null-move guard: start==end would clear the piece from the 2D board
		# while leaving the bitboard intact, causing a guaranteed sync error.
		if sr == er and sc == ec:
			return None
		piece = board[sr][sc]
		captured = board[er][ec]

		# 1. Handle En Passant Capture
		if piece.type == PAWN and (er, ec) == en_passant_target:
			# The captured pawn sits on (sr, ec) — same rank as the capturing pawn,
			# same file as the landing square — not on the landing square itself (er, ec).
			# A plain push that happens to land on the EP target square (when the adjacent
			# pawn was already removed) must not be treated as a capture, hence the guard.
			ep_captured = board[sr][ec]
			if ep_captured is not None:
				captured = ep_captured
				board[sr][ec] = None
				if bb_mgr:
					bb_mgr.remove_piece(ep_captured.color, ep_captured.type, sr, ec)

		# 2. Handle Castling (King moves 2 squares)
		if piece.type == KING and abs(sc - ec) == 2:
			rook_sr = sr
			rook_sc = 7 if ec > sc else 0   # kingside rook at col 7, queenside at col 0
			rook_er = sr
			rook_ec = 5 if ec > sc else 3   # kingside rook lands at col 5, queenside at col 3
			
			rook = board[rook_sr][rook_sc]
			if rook:
				board[rook_er][rook_ec] = rook
				board[rook_sr][rook_sc] = None
				rook.has_moved = True
				if bb_mgr:
					bb_mgr.remove_piece(rook.color, rook.type, rook_sr, rook_sc)
					bb_mgr.add_piece(rook.color, rook.type, rook_er, rook_ec)

		# 3. Standard Move Execution
		# board[er][ec] is checked (not captured) because for EP the captured pawn
		# was already removed from the bitboard in step 1 and board[er][ec] is now
		# None — so this block correctly skips the double-remove.
		if captured and captured != piece:
			if bb_mgr and board[er][ec]:
				bb_mgr.remove_piece(captured.color, captured.type, er, ec)

		if bb_mgr:
			bb_mgr.remove_piece(piece.color, piece.type, sr, sc)
			bb_mgr.add_piece(piece.color, piece.type, er, ec)

		board[er][ec] = piece
		board[sr][sc] = None
		piece.has_moved = True
		
		return captured