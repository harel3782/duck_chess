from DuckChess_Game.Logic.constants import *
from DuckChess_Game.Logic.rules_checker import RulesChecker

class MoveGenerationMixin:
	"""Logic for generating legal moves, delegating check validation to RulesChecker."""

	def __init__(self):
		# Initialize the specialized rules engine
		self.rules = RulesChecker()

	def get_piece_legal_moves(self, r, c):
		"""Calculates all physical squares a piece can move to, ignoring check constraints[cite: 13]."""
		p = self.board[r][c]
		if not p: return []
		moves = []
		
		def ok(nr, nc): return 0 <= nr < 8 and 0 <= nc < 8

		# King Movement Logic [cite: 14]
		if p.type == KING:
			dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
			for dr, dc in dirs:
				nr, nc = r + dr, c + dc
				if ok(nr, nc) and (nr, nc) != self.duck_pos:
					target = self.board[nr][nc]
					if not target or target.color != p.color:
						moves.append((nr, nc))
			# Castling [cite: 14, 16]
			if not p.has_moved:
				if self.can_castle(r, c, True): moves.append((r, 6))
				if self.can_castle(r, c, False): moves.append((r, 2))
			return moves

		# Sliding Logic (Queen, Rook, Bishop) [cite: 14]
		dirs = []
		if p.type == QUEEN: dirs = [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]
		elif p.type == ROOK: dirs = [(1,0),(-1,0),(0,1),(0,-1)]
		elif p.type == BISHOP: dirs = [(1,1),(1,-1),(-1,1),(-1,-1)]

		for dr, dc in dirs:
			for i in range(1, 8):
				nr, nc = r + dr * i, c + dc * i
				if not ok(nr, nc) or (nr, nc) == self.duck_pos: break
				target = self.board[nr][nc]
				if not target: moves.append((nr, nc))
				else:
					if target.color != p.color: moves.append((nr, nc))
					break
		
		# Knight Logic [cite: 15]
		if p.type == KNIGHT:
			for dr, dc in [(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(1,-2),(-1,2),(-1,-2)]:
				nr, nc = r + dr, c + dc
				if ok(nr, nc) and (nr, nc) != self.duck_pos:
					target = self.board[nr][nc]
					if not target or target.color != p.color:
						moves.append((nr, nc))

		# Pawn Logic including En Passant [cite: 16]
		if p.type == PAWN:
			direction = -1 if p.color == 'w' else 1
			# Standard forward
			if ok(r + direction, c) and not self.board[r + direction][c] and (r + direction, c) != self.duck_pos:
				moves.append((r + direction, c))
				start_row = 6 if p.color == 'w' else 1
				if r == start_row and not self.board[r + direction*2][c] and (r + direction*2, c) != self.duck_pos:
					moves.append((r + direction*2, c))
			# Captures
			for dc in [-1, 1]:
				nr, nc = r + direction, c + dc
				if ok(nr, nc):
					target = self.board[nr][nc]
					if target and target.color != p.color and (nr, nc) != self.duck_pos:
						moves.append((nr, nc))
					elif (nr, nc) == self.en_passant_target and (nr, nc) != self.duck_pos:
						moves.append((nr, nc))

		return moves

	def is_in_check(self, color, board_state=None):
		"""Delegates check detection to the RulesChecker component."""
		if board_state is None: board_state = self.board
		return self.rules.is_in_check(color, board_state, self.duck_pos)

	def can_castle(self, r, c, is_ks):
		"""Validation for Castling rights[cite: 16]."""
		rook_col = 7 if is_ks else 0
		rook = self.board[r][rook_col]
		if not rook or rook.type != ROOK or rook.has_moved: return False
		path = [5, 6] if is_ks else [1, 2, 3]
		for col in path:
			if self.board[r][col] or (r, col) == self.duck_pos: return False
		return True