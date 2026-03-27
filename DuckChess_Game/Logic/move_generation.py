from DuckChess_Game.Logic.constants import *
from DuckChess_Game.Logic.rules_checker import RulesChecker
from DuckChess_Game.Logic.bitboard_move_gen import BitboardMoveGenerator

class MoveGenerationMixin:
	"""Logic for generating legal moves, powered entirely by 64-bit Bitboards."""

	def get_piece_legal_moves(self, r, c):
		"""Calculates all physical squares a piece can move to using the Bitboard Engine."""
		if not hasattr(self, 'bb_mgr'): return []
		
		p = self.board[r][c]
		if not p: return []
		
		bb_gen = BitboardMoveGenerator(self.bb_mgr)
		moves = bb_gen.get_moves_for_square(r, c, p.type, p.color)
		
		# Add Castling
		if p.type == KING and not p.has_moved:
			if self.can_castle(r, c, True): moves.append((r, 6))
			if self.can_castle(r, c, False): moves.append((r, 2))
			
		# Add En Passant
		if p.type == PAWN and getattr(self, 'en_passant_target', None):
			direction = -1 if p.color == 'w' else 1
			for dc in [-1, 1]:
				nr, nc = r + direction, c + dc
				if (nr, nc) == getattr(self, 'en_passant_target', None) and (nr, nc) != getattr(self, 'duck_pos', (-1,-1)):
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