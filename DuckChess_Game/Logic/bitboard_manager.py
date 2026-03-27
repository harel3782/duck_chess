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
		
		# Occupancy bitboards (cached for fast move generation)
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
		"""Updates the duck's single bitboard."""
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
		"""Validates that the 2D array and the 64-bit boards are perfectly synchronized."""
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