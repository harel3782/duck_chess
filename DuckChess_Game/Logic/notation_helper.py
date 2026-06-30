class NotationHelper:
	"""Handles conversion between board coordinates and chess notation.

	Internal coordinate system: row 0 = rank 8 (black's back rank, top of board),
	row 7 = rank 1 (white's back rank, bottom of board). The reversed rank string
	"87654321" maps r=0→'8', r=7→'1' without any arithmetic.
	"""

	@staticmethod
	def get_rank_file(r, c):
		"""Returns the rank character ('1'-'8') and file character ('a'-'h')."""
		return "87654321"[r], "abcdefgh"[c]

	@staticmethod
	def get_notation_coords(r, c):
		"""Converts (r, c) to algebraic notation like 'e4' (file then rank)."""
		return f"{'abcdefgh'[c]}{'87654321'[r]}"