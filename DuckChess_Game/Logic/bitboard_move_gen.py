from DuckChess_Game.Logic.constants import *

class BitboardMoveGenerator:
	"""Generates legal moves using extremely fast 64-bit bitwise operations."""
	
	# Masks to prevent pieces from wrapping around board edges
	NOT_A_FILE = 0xFEFEFEFEFEFEFEFE
	NOT_H_FILE = 0x7F7F7F7F7F7F7F7F
	NOT_AB_FILE = 0xFCFCFCFCFCFCFCFC
	NOT_GH_FILE = 0x3F3F3F3F3F3F3F3F

	def __init__(self, bb_mgr):
		self.bb = bb_mgr

	def get_moves_for_square(self, r, c, piece_type, color):
		"""Returns a list of valid destination tuples (r, c) for a piece."""
		sq = r * 8 + c
		piece_bb = 1 << sq
		moves_bb = 0
		
		own_pieces = self.bb.white_occupancy if color == 'w' else self.bb.black_occupancy
		enemy_pieces = self.bb.black_occupancy if color == 'w' else self.bb.white_occupancy
		all_pieces = self.bb.all_occupancy
		duck = self.bb.duck_board

		if piece_type == KNIGHT:
			moves_bb = self._get_knight_attacks(piece_bb)
		elif piece_type == KING:
			moves_bb = self._get_king_attacks(piece_bb)
		elif piece_type == PAWN:
			moves_bb = self._get_pawn_moves(piece_bb, color, all_pieces, enemy_pieces, duck)
		elif piece_type in [BISHOP, ROOK, QUEEN]:
			moves_bb = self._get_sliding_moves(piece_bb, piece_type, all_pieces, duck)

		# Remove moves that land on own pieces or the duck
		valid_moves_bb = moves_bb & ~own_pieces & ~duck
		
		# Convert the bitboard back to a list of (r, c) coordinates
		return self._bb_to_coords(valid_moves_bb)

	def _get_knight_attacks(self, knight_bb):
		"""Calculates all possible knight jumps using bit shifts."""
		l1 = (knight_bb >> 1) & self.NOT_H_FILE
		l2 = (knight_bb >> 2) & self.NOT_GH_FILE
		r1 = (knight_bb << 1) & self.NOT_A_FILE
		r2 = (knight_bb << 2) & self.NOT_AB_FILE
		h1 = l1 | r1
		h2 = l2 | r2
		return (h1 << 16) | (h1 >> 16) | (h2 << 8) | (h2 >> 8)

	def _get_king_attacks(self, king_bb):
		"""Calculates all 1-step king moves."""
		l1 = (king_bb >> 1) & self.NOT_H_FILE
		r1 = (king_bb << 1) & self.NOT_A_FILE
		h = king_bb | l1 | r1
		return (h << 8) | (h >> 8) | l1 | r1

	def _get_pawn_moves(self, pawn_bb, color, all_pieces, enemy_pieces, duck):
		"""Calculates pawn pushes and captures."""
		moves = 0
		blockers = all_pieces | duck
		if color == 'w':
			push1 = (pawn_bb >> 8) & ~blockers
			moves |= push1
			if pawn_bb & 0x00FF000000000000: # White starting row mask
				push2 = (push1 >> 8) & ~blockers
				moves |= push2
			moves |= ((pawn_bb >> 9) & self.NOT_H_FILE) & enemy_pieces
			moves |= ((pawn_bb >> 7) & self.NOT_A_FILE) & enemy_pieces
		else:
			push1 = (pawn_bb << 8) & ~blockers
			moves |= push1
			if pawn_bb & 0x000000000000FF00: # Black starting row mask
				push2 = (push1 << 8) & ~blockers
				moves |= push2
			moves |= ((pawn_bb << 9) & self.NOT_A_FILE) & enemy_pieces
			moves |= ((pawn_bb << 7) & self.NOT_H_FILE) & enemy_pieces
		return moves

	def _get_sliding_moves(self, piece_bb, piece_type, all_pieces, duck):
		"""Generates sliding moves (Rook, Bishop, Queen)."""
		moves = 0
		dirs = []
		if piece_type in [ROOK, QUEEN]: dirs.extend([8, -8, 1, -1]) 
		if piece_type in [BISHOP, QUEEN]: dirs.extend([9, 7, -9, -7])
			
		blockers = all_pieces | duck
		
		for d in dirs:
			ray = piece_bb
			for _ in range(7):
				if d == 1: ray = (ray << 1) & self.NOT_A_FILE
				elif d == -1: ray = (ray >> 1) & self.NOT_H_FILE
				elif d == 8: ray = (ray << 8)
				elif d == -8: ray = (ray >> 8)
				elif d == 9: ray = (ray << 9) & self.NOT_A_FILE
				elif d == -9: ray = (ray >> 9) & self.NOT_H_FILE
				elif d == 7: ray = (ray << 7) & self.NOT_H_FILE
				elif d == -7: ray = (ray >> 7) & self.NOT_A_FILE
				
				if ray == 0: break
				moves |= ray
				if ray & blockers: break # Stop if we hit a piece or duck
				
		return moves

	def _bb_to_coords(self, bb):
		"""Converts a bitboard back to a list of (r, c) tuples."""
		coords = []
		for i in range(64):
			if (bb & (1 << i)): coords.append((i // 8, i % 8))
		return coords