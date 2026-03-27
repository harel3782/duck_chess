from DuckChess_Game.Logic.constants import *
from DuckChess_Game.Logic.rules_checker import RulesChecker
from DuckChess_Game.Logic.bitboard_move_gen import BitboardMoveGenerator

class MoveGenerationMixin:
	"""Logic for generating legal moves, delegating check validation to RulesChecker."""

	def get_piece_legal_moves(self, r, c):
		"""Calculates all physical squares a piece can move to."""
		
		# --- OLD 2D ARRAY LOGIC ---
		old_moves = self._get_legal_moves_2d(r, c)
		
		# --- NEW 64-BIT BITBOARD LOGIC ---
		if hasattr(self, 'bb_mgr'):
			bb_gen = BitboardMoveGenerator(self.bb_mgr)
			p = self.board[r][c]
			new_moves = bb_gen.get_moves_for_square(r, c, p.type, p.color)
			
			# Add Castling manually to new_moves (as it depends on complex board state)
			if p.type == KING and not p.has_moved:
				if self.can_castle(r, c, True): new_moves.append((r, 6))
				if self.can_castle(r, c, False): new_moves.append((r, 2))
				
			# Add En Passant manually to new_moves
			if p.type == PAWN and getattr(self, 'en_passant_target', None):
				direction = -1 if p.color == 'w' else 1
				for dc in [-1, 1]:
					nr, nc = r + direction, c + dc
					if (nr, nc) == self.en_passant_target and (nr, nc) != getattr(self, 'duck_pos', (-1,-1)):
						new_moves.append((nr, nc))

			# --- PARALLEL SANITY CHECK ---
			old_set = set(old_moves)
			new_set = set(new_moves)
			if old_set != new_set:
				print(f"\n[!] MOVE GEN SYNC ERROR for {p.color}{p.type} at ({r}, {c})")
				print(f" -> 2D Moves: {sorted(list(old_set))}")
				print(f" -> BB Moves: {sorted(list(new_set))}")
				print(f" -> Missing in BB: {old_set - new_set}")
				print(f" -> Extra in BB: {new_set - old_set}")

		return old_moves

	def _get_legal_moves_2d(self, r, c):
		"""The legacy 2D array move generation logic."""
		p = self.board[r][c]
		if not p: return []
		moves = []
		
		def ok(nr, nc): return 0 <= nr < 8 and 0 <= nc < 8

		duck = getattr(self, 'duck_pos', (-1, -1))

		if p.type == KING:
			dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
			for dr, dc in dirs:
				nr, nc = r + dr, c + dc
				if ok(nr, nc) and (nr, nc) != duck:
					target = self.board[nr][nc]
					if not target or target.color != p.color: moves.append((nr, nc))
			if not p.has_moved:
				if self.can_castle(r, c, True): moves.append((r, 6))
				if self.can_castle(r, c, False): moves.append((r, 2))
			return moves

		dirs = []
		if p.type == QUEEN: dirs = [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]
		elif p.type == ROOK: dirs = [(1,0),(-1,0),(0,1),(0,-1)]
		elif p.type == BISHOP: dirs = [(1,1),(1,-1),(-1,1),(-1,-1)]

		for dr, dc in dirs:
			for i in range(1, 8):
				nr, nc = r + dr * i, c + dc * i
				if not ok(nr, nc) or (nr, nc) == duck: break
				target = self.board[nr][nc]
				if not target: moves.append((nr, nc))
				else:
					if target.color != p.color: moves.append((nr, nc))
					break
		
		if p.type == KNIGHT:
			for dr, dc in [(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(1,-2),(-1,2),(-1,-2)]:
				nr, nc = r + dr, c + dc
				if ok(nr, nc) and (nr, nc) != duck:
					target = self.board[nr][nc]
					if not target or target.color != p.color: moves.append((nr, nc))

		if p.type == PAWN:
			direction = -1 if p.color == 'w' else 1
			if ok(r + direction, c) and not self.board[r + direction][c] and (r + direction, c) != duck:
				moves.append((r + direction, c))
				start_row = 6 if p.color == 'w' else 1
				if r == start_row and not self.board[r + direction*2][c] and (r + direction*2, c) != duck:
					moves.append((r + direction*2, c))
			for dc in [-1, 1]:
				nr, nc = r + direction, c + dc
				if ok(nr, nc):
					target = self.board[nr][nc]
					if target and target.color != p.color and (nr, nc) != duck:
						moves.append((nr, nc))
					elif (nr, nc) == getattr(self, 'en_passant_target', None) and (nr, nc) != duck:
						moves.append((nr, nc))

		return moves

	def is_in_check(self, color, board_state=None):
		"""Delegates check detection to the stateless RulesChecker component."""
		if board_state is None: board_state = self.board
		checker = RulesChecker()
		return checker.is_in_check(color, board_state, getattr(self, 'duck_pos', (-1,-1)))

	def can_castle(self, r, c, is_ks):
		"""Validation for Castling rights."""
		rook_col = 7 if is_ks else 0
		rook = self.board[r][rook_col]
		if not rook or rook.type != ROOK or rook.has_moved: return False
		path = [5, 6] if is_ks else [1, 2, 3]
		for col in path:
			if self.board[r][col] or (r, col) == getattr(self, 'duck_pos', (-1,-1)): return False
		return True