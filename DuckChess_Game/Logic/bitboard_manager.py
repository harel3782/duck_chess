from DuckChess_Game.Logic.constants import *

class BitboardManager:
	"""
	Manages the 64-bit integer representations of the chessboard.
	Square 0 is h1 (bottom right), Square 63 is a8 (top left).
	"""
	def __init__(self):
		# 12 Bitboards for the chess pieces
		self.piece_boards = {
			'w': {PAWN: 0, KNIGHT: 0, BISHOP: 0, ROOK: 0, QUEEN: 0, KING: 0},
			'b': {PAWN: 0, KNIGHT: 0, BISHOP: 0, ROOK: 0, QUEEN: 0, KING: 0}
		}
		
		# 1 Bitboard for the Duck
		self.duck_board = 0
		
		# Derived union boards, kept in sync after every add/remove.
		# Move generators read these on every call, so caching avoids OR-ing
		# 6 piece boards together repeatedly per position.
		# NOTE: all_occupancy does NOT include the duck — duck blocking is
		# handled separately in move generation because the duck obstructs
		# both sides equally, unlike normal piece occupancy.
		self.white_occupancy = 0
		self.black_occupancy = 0
		self.all_occupancy = 0

	# --- BIT MANIPULATION HELPERS ---

	def set_bit(self, bitboard, square):
		"""Sets the bit at the given square index (0-63) to 1."""
		return int(bitboard | (1 << int(square)))

	def clear_bit(self, bitboard, square):
		"""Clears the bit at the given square index (0-63) to 0."""
		return int(bitboard & ~(1 << int(square)))

	def get_bit(self, bitboard, square):
		"""Returns True if the bit at the given square is 1."""
		return (int(bitboard) & (1 << int(square))) != 0

	def coords_to_square(self, r, c):
		"""
		Converts 2D array coordinates to a flat 0-63 index.
		r=7, c=0 (a1) -> index 56
		"""
		return int(r * 8 + c)

	# --- BOARD UPDATES ---

	def add_piece(self, color, piece_type, r, c):
		"""Adds a piece to the relevant bitboards."""
		sq = self.coords_to_square(r, c)
		self.piece_boards[color][piece_type] = self.set_bit(self.piece_boards[color][piece_type], sq)
		self._update_occupancies()

	def remove_piece(self, color, piece_type, r, c):
		"""Removes a piece from the relevant bitboards."""
		sq = self.coords_to_square(r, c)
		self.piece_boards[color][piece_type] = self.clear_bit(self.piece_boards[color][piece_type], sq)
		self._update_occupancies()

	def move_duck(self, r, c):
		"""Moves the duck to (r, c), or clears it when called with the (-1,-1) sentinel."""
		# Reset to 0 first: the duck occupies exactly one square, so the old bit
		# must be cleared unconditionally before setting the new position.
		self.duck_board = 0
		if r != -1 and c != -1:
			sq = self.coords_to_square(r, c)
			self.duck_board = self.set_bit(self.duck_board, sq)

	def _update_occupancies(self):
		"""Recalculates the combined occupancy boards."""
		self.white_occupancy = 0
		for bb in self.piece_boards['w'].values():
			self.white_occupancy |= int(bb)
			
		self.black_occupancy = 0
		for bb in self.piece_boards['b'].values():
			self.black_occupancy |= int(bb)
			
		self.all_occupancy = self.white_occupancy | self.black_occupancy

	def debug_print_bitboard(self, bitboard, name="Bitboard"):
		"""Prints a 64-bit integer as an 8x8 grid for debugging."""
		print(f"\n--- {name} ---")
		for r in range(8):
			row_str = ""
			for c in range(8):
				sq = self.coords_to_square(r, c)
				row_str += "1 " if self.get_bit(bitboard, sq) else ". "
			print(row_str)
		print("-" * 20)

	def verify_sync(self, board_2d, duck_pos_2d):
		"""Cross-checks bitboards against the 2D board; prints the first mismatch and returns False.

		Called after every duck placement in production (see place_duck). O(64 × 12)
		but cheap compared to a full move-generation pass. Logs rather than raises so
		a sync error surfaces as a warning without crashing a live game.
		"""
		for r in range(8):
			for c in range(8):
				sq = self.coords_to_square(r, c)
				p_2d = board_2d[r][c]

				# 1. Check piece synchronization
				for color in ['w', 'b']:
					for p_type in [PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING]:
						bb_has_piece = self.get_bit(self.piece_boards[color][p_type], sq)
						board_has_piece = (p_2d is not None and p_2d.color == color and p_2d.type == p_type)

						if bb_has_piece != board_has_piece:
							print(f"\n[!] SYNC ERROR: Mismatch at ({r}, {c}) for {color}{p_type}!")
							print(f" -> 2D Board says: {board_has_piece}")
							print(f" -> Bitboard says: {bb_has_piece}")
							return False

				# 2. Check duck synchronization
				bb_has_duck = self.get_bit(self.duck_board, sq)
				board_has_duck = (duck_pos_2d == (r, c))
				
				if bb_has_duck != board_has_duck:
					print(f"\n[!] SYNC ERROR: Duck mismatch at ({r}, {c})!")
					return False

		return True

	def generate_fen(self, turn, duck_pos):
		"""Serializes the current bitboard position to a duck-chess FEN string.

		Internal coords are (r, c) with r=0 -> rank 1 and c=0 -> file 'a',
		so we emit ranks 8 (r=7) down to 1 (r=0), matching Peter's engine.
		"""
		fen = []
		for r in range(7, -1, -1):
			empty = 0
			rank_str = ""
			for c in range(8):
				found = False
				for color in ['w', 'b']:
					for p_type, board in self.piece_boards[color].items():
						if self.get_bit(board, self.coords_to_square(r, c)):
							if empty > 0:
								rank_str += str(empty)
								empty = 0
							# Piece constants are already FEN letters ('P','N','B','R','Q','K').
							rank_str += p_type.upper() if color == 'w' else p_type.lower()
							found = True
							break
					if found: break
				if not found:
					empty += 1
			if empty > 0: rank_str += str(empty)
			fen.append(rank_str)

		fen_str = "/".join(fen)
		# duck_pos[1] = column → file letter; duck_pos[0] = row → rank number.
		duck_notation = chr(ord('a') + duck_pos[1]) + str(duck_pos[0] + 1)
		return f"{fen_str} {turn} - - 0 1 [{duck_notation}]"

	def print_current_state(self):
		"""Debug dump of the board, printed rank 8 (top) down to rank 1."""
		piece_symbols = {
			'w': {PAWN: 'P', KNIGHT: 'N', BISHOP: 'B', ROOK: 'R', QUEEN: 'Q', KING: 'K'},
			'b': {PAWN: 'p', KNIGHT: 'n', BISHOP: 'b', ROOK: 'r', QUEEN: 'q', KING: 'k'}
		}

		print("\n=== CURRENT BITBOARD STATE ===")
		for r in range(7, -1, -1):
			row_str = f"Row {r} | "
			for c in range(8):
				sq = self.coords_to_square(r, c)
				char_to_print = '.'

				if self.get_bit(self.duck_board, sq):
					char_to_print = 'D'
				else:
					found = False
					for color in ['w', 'b']:
						for p_type, symbol in piece_symbols[color].items():
							if self.get_bit(self.piece_boards[color][p_type], sq):
								char_to_print = symbol
								found = True
								break
						if found:
							break

				row_str += f"{char_to_print} "
			print(row_str)

		print("      -----------------")
		print("Col:   0 1 2 3 4 5 6 7")
		print("==============================\n")