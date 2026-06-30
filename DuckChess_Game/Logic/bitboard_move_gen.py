from DuckChess_Game.Logic.constants import *

class BitboardMoveGenerator:
	"""Generates legal moves using extremely fast 64-bit bitwise operations."""
	
	# Bit-shift wrap guards. Shifting a piece on the A-file left by 1 column (<<1)
	# would land on the H-file of the rank above — ANDing with NOT_A_FILE clears
	# those bits before the shift. Similar guards apply to H-file (right edge) and
	# the two-column knight leaps (NOT_AB_FILE, NOT_GH_FILE).
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
		"""Calculates all 8 knight destinations via two groups of horizontal+vertical shifts.

		Group h1 (±1 file): shift 2 ranks up/down → the long-axis jumps.
		Group h2 (±2 files): shift 1 rank up/down → the short-axis jumps.
		File masks applied before shifts to prevent the ±1/±2 column steps from
		wrapping across the board edge.
		"""
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
		"""Calculates pawn pushes and diagonal captures.

		Row 0 = rank 8 (top), row 7 = rank 1 (bottom) in this coordinate system.
		White advances toward row 0, so >>8 moves forward; black advances toward
		row 7, so <<8 moves forward.

		The duck is merged into blockers so it stops pawn pushes, but it is NOT
		in enemy_pieces, so a pawn cannot capture the duck diagonally.
		"""
		moves = 0
		blockers = all_pieces | duck
		if color == 'w':
			push1 = (pawn_bb >> 8) & ~blockers
			moves |= push1
			# 0x00FF000000000000 = row 6 = rank 2 — white's starting rank.
			# push2 starts from push1 (not pawn_bb) so a blocked first step
			# also blocks the double push.
			if pawn_bb & 0x00FF000000000000:
				push2 = (push1 >> 8) & ~blockers
				moves |= push2
			moves |= ((pawn_bb >> 9) & self.NOT_H_FILE) & enemy_pieces
			moves |= ((pawn_bb >> 7) & self.NOT_A_FILE) & enemy_pieces
		else:
			push1 = (pawn_bb << 8) & ~blockers
			moves |= push1
			# 0x000000000000FF00 = row 1 = rank 7 — black's starting rank.
			if pawn_bb & 0x000000000000FF00:
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
				moves |= ray           # include the blocker's square (enables captures)
				if ray & blockers: break  # but stop extending past it
				
		return moves

	def _bb_to_coords(self, bb):
		"""Converts a bitboard back to a list of (r, c) tuples."""
		coords = []
		for i in range(64):
			if (bb & (1 << i)): coords.append((i // 8, i % 8))
		return coords