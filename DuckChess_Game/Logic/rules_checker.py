from DuckChess_Game.Logic.constants import *

class RulesChecker:
	"""Validates global game states like Check, Repetition, and End conditions."""

	def is_in_check(self, color, board, duck_pos):
		"""Checks if the King of the given color is under attack."""
		king_pos = self._find_king(color, board)
		if not king_pos: return False

		enemy = 'b' if color == 'w' else 'w'
		kr, kc = king_pos

		# Check sliding pieces and jump pieces (logic migrated from logic.py)
		# Note: Duck position blocks checks in Duck Chess
		return self._is_attacked_by_knight(kr, kc, enemy, board) or \
			   self._is_attacked_by_sliding(kr, kc, enemy, board, duck_pos) or \
			   self._is_attacked_by_pawn(kr, kc, enemy, board)

	def _find_king(self, color, board):
		for r in range(8):
			for c in range(8):
				p = board[r][c]
				if p and p.type == KING and p.color == color:
					return (r, c)
		return None

	# ... (Supporting private methods for attack detection based on provided logic.py) ...