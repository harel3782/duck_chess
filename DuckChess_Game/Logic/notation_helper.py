class NotationHelper:
	"""Handles conversion between board coordinates and chess notation."""

	@staticmethod
	def get_rank_file(r, c):
		"""Returns the rank (1-8) and file (a-h) for given indices."""
		return "87654321"[r], "abcdefgh"[c]

	@staticmethod
	def get_notation_coords(r, c):
		"""Converts (r, c) to notation like 'e4'."""
		return f"{'abcdefgh'[c]}{'87654321'[r]}"