from DuckChess_Game.UI.settings import *

class MoveGenerationMixin:
	"""Handles legal move calculations, castling rules, and check detection."""

	def get_piece_legal_moves(self, r, c):
		p = self.board[r][c]
		if not p: return []
		moves = []

		def ok(nr, nc):
			return 0 <= nr < 8 and 0 <= nc < 8

		# 1. King Moves
		if p.type == KING:
			dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
			for dr, dc in dirs:
				nr, nc = r + dr, c + dc
				if ok(nr, nc) and (nr, nc) != self.duck_pos:
					t = self.board[nr][nc]
					if not t or t.color != p.color: moves.append((nr, nc))
			# Castling
			if not p.has_moved:
				if self.can_castle(r, c, True): moves.append((r, 6))
				if self.can_castle(r, c, False): moves.append((r, 2))
			return moves

		# 2. Sliding Pieces (Queen, Rook, Bishop)
		dirs = []
		if p.type == QUEEN:
			dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
		elif p.type == ROOK:
			dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
		elif p.type == BISHOP:
			dirs = [(1, 1), (1, -1), (-1, 1), (-1, -1)]

		if dirs:
			for dr, dc in dirs:
				for i in range(1, 8):
					nr, nc = r + dr * i, c + dc * i
					if not ok(nr, nc) or (nr, nc) == self.duck_pos: break
					t = self.board[nr][nc]
					if not t:
						moves.append((nr, nc))
					else:
						if t.color != p.color: moves.append((nr, nc))
						break
			return moves

		# 3. Knight Moves
		if p.type == KNIGHT:
			for dr, dc in [(2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)]:
				nr, nc = r + dr, c + dc
				if ok(nr, nc) and (nr, nc) != self.duck_pos:
					t = self.board[nr][nc]
					if not t or t.color != p.color: moves.append((nr, nc))
			return moves

		# 4. Pawn Moves
		if p.type == PAWN:
			d = -1 if p.color == 'w' else 1
			# Forward 1
			if ok(r + d, c) and not self.board[r + d][c] and (r + d, c) != self.duck_pos:
				moves.append((r + d, c))
				# Forward 2
				start_rank = 6 if p.color == 'w' else 1
				if r == start_rank and ok(r + d * 2, c) and not self.board[r + d * 2][c] and (r + d * 2, c) != self.duck_pos:
					moves.append((r + d * 2, c))
			# Captures
			for dc in [-1, 1]:
				nr, nc = r + d, c + dc
				if ok(nr, nc):
					t = self.board[nr][nc]
					# Normal Capture
					if t and t.color != p.color and (nr, nc) != self.duck_pos:
						moves.append((nr, nc))
					# En Passant
					elif not t and (nr, nc) == self.en_passant_target and (nr, nc) != self.duck_pos:
						moves.append((nr, nc))
			return moves
		return []

	def can_castle(self, r, c, is_ks):
		rc = 7 if is_ks else 0
		rook = self.board[r][rc]
		if not rook or rook.type != ROOK or rook.has_moved: return False
		path_cols = [5, 6] if is_ks else [1, 2, 3]
		for cl in path_cols:
			if self.board[r][cl] or (r, cl) == self.duck_pos: return False
		return True

	def is_in_check(self, color, board_state=None):
		"""Checks if the King is under attack. Note: In Duck Chess, check is valid but not game-ending."""
		if board_state is None: board_state = self.board
		king_pos = None
		for r in range(8):
			for c in range(8):
				p = board_state[r][c]
				if p and p.type == KING and p.color == color:
					king_pos = (r, c)
					break
			if king_pos: break
		if not king_pos: return False  # King captured?

		enemy = 'b' if color == 'w' else 'w'
		kr, kc = king_pos

		# Check Knights
		for dr, dc in [(2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)]:
			nr, nc = kr + dr, kc + dc
			if 0 <= nr < 8 and 0 <= nc < 8:
				p = board_state[nr][nc]
				if p and p.color == enemy and p.type == KNIGHT: return True

		# Check Sliding
		dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
		for dr, dc in dirs:
			for i in range(1, 8):
				nr, nc = kr + dr * i, kc + dc * i
				if not (0 <= nr < 8 and 0 <= nc < 8): break
				if (nr, nc) == self.duck_pos: break  # Duck blocks checks!
				p = board_state[nr][nc]
				if p:
					if p.color == enemy:
						if p.type == QUEEN: return True
						if p.type == ROOK and (dr == 0 or dc == 0): return True
						if p.type == BISHOP and (dr != 0 and dc != 0): return True
					break

		# Check Pawns
		pawn_dir = -1 if color == 'w' else 1
		for dc in [-1, 1]:
			nr, nc = kr + pawn_dir, kc + dc
			if 0 <= nr < 8 and 0 <= nc < 8:
				p = board_state[nr][nc]
				if p and p.color == enemy and p.type == PAWN: return True

		# Check Enemy King
		for dr in [-1, 0, 1]:
			for dc in [-1, 0, 1]:
				if dr == 0 and dc == 0: continue
				nr, nc = kr + dr, kc + dc
				if 0 <= nr < 8 and 0 <= nc < 8:
					p = board_state[nr][nc]
					if p and p.color == enemy and p.type == KING: return True
		return False