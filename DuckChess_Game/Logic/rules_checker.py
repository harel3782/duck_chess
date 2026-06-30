from DuckChess_Game.Logic.constants import *

class RulesChecker:
	"""Validates global game states like Check conditions.

	Stateless — a fresh instance is created per call, making it safe to use
	from both the UI and RL training paths concurrently.
	"""

	def is_in_check(self, color, board, duck_pos):
		"""Returns True if the king of `color` is under attack.

		Returns False if no king is found — handles the post-king-capture state
		without crashing (the game_over flag should already be set by then).
		"""
		king_pos = self._find_king(color, board)
		if not king_pos: return False

		enemy = 'b' if color == 'w' else 'w'
		kr, kc = king_pos

		return (self._is_attacked_by_knight(kr, kc, enemy, board) or 
				self._is_attacked_by_sliding(kr, kc, enemy, board, duck_pos) or 
				self._is_attacked_by_pawn(kr, kc, enemy, board) or
				self._is_attacked_by_king(kr, kc, enemy, board))

	def _find_king(self, color, board):
		"""Locates the king's current coordinates."""
		for r in range(8):
			for c in range(8):
				p = board[r][c]
				if p and p.type == KING and p.color == color:
					return (r, c)
		return None

	def _is_attacked_by_knight(self, r, c, enemy, board):
		"""Checks for L-shape attacks from enemy knights."""
		dirs = [(2,1), (2,-1), (-2,1), (-2,-1), (1,2), (1,-2), (-1,2), (-1,-2)]
		for dr, dc in dirs:
			nr, nc = r + dr, c + dc
			if 0 <= nr < 8 and 0 <= nc < 8:
				p = board[nr][nc]
				if p and p.color == enemy and p.type == KNIGHT:
					return True
		return False

	def _is_attacked_by_sliding(self, r, c, enemy, board, duck_pos):
		"""Checks for straight and diagonal attacks from Queens, Rooks, and Bishops.

		Duck Chess addition: the duck terminates any sliding ray, blocking attacks
		through it just like a piece would — but without being capturable.
		"""
		for dr, dc in [(1,0), (-1,0), (0,1), (0,-1)]:
			for i in range(1, 8):
				nr, nc = r + dr*i, c + dc*i
				if not (0 <= nr < 8 and 0 <= nc < 8) or (nr, nc) == duck_pos: break
				p = board[nr][nc]
				if p:
					if p.color == enemy and p.type in (ROOK, QUEEN): return True
					break

		# Bishops and Queens (Diagonal)
		for dr, dc in [(1,1), (1,-1), (-1,1), (-1,-1)]:
			for i in range(1, 8):
				nr, nc = r + dr*i, c + dc*i
				if not (0 <= nr < 8 and 0 <= nc < 8) or (nr, nc) == duck_pos: break
				p = board[nr][nc]
				if p:
					if p.color == enemy and p.type in (BISHOP, QUEEN): return True
					break
		return False

	def _is_attacked_by_pawn(self, r, c, enemy, board):
		"""Checks for diagonal pawn captures targeting the king at (r, c).

		d encodes the enemy's forward direction: white advances toward row 0 (d=-1),
		black toward row 7 (d=+1). `r - d` looks one rank behind the king in the
		enemy pawn's forward direction — where an attacking pawn would stand.
		"""
		d = -1 if enemy == 'w' else 1
		for dc in [-1, 1]:
			nr, nc = r - d, c + dc
			if 0 <= nr < 8 and 0 <= nc < 8:
				p = board[nr][nc]
				if p and p.color == enemy and p.type == PAWN:
					return True
		return False

	def _is_attacked_by_king(self, r, c, enemy, board):
		"""Checks if the enemy king is adjacent (prevents kings touching)."""
		for dr in [-1, 0, 1]:
			for dc in [-1, 0, 1]:
				if dr == 0 and dc == 0: continue
				nr, nc = r + dr, c + dc
				if 0 <= nr < 8 and 0 <= nc < 8:
					p = board[nr][nc]
					if p and p.color == enemy and p.type == KING:
						return True
		return False