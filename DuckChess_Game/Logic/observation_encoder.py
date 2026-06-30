import numpy as np
from DuckChess_Game.Logic.constants import *

class ObservationEncoder:
	"""Converts board state into a 19×8×8 float32 tensor for the RL policy network.

	Channel layout (one 8×8 plane each):
	  0-5   White pieces: P N B R Q K
	  6-11  Black pieces: P N B R Q K
	  12    Duck position
	  13    En passant target square (at most one cell is 1.0)
	  14    Side to move (all 1.0 = White, all 0.0 = Black)
	  15-18 Castling rights: WK, WQ, BK, BQ (entire plane filled when right is available)
	"""

	def encode_state(self, bb_mgr, turn, en_passant_target, can_castle_func):
		"""Populates the 19×8×8 tensor from the current bitboard state."""
		obs = np.zeros((19, 8, 8), dtype=np.float32)

		# Channels 0-11: one plane per (color, piece-type) combination.
		# Binary (0/1) rather than piece-count because each square holds at most one piece.
		piece_to_channel = {
			('w', PAWN): 0, ('w', KNIGHT): 1, ('w', BISHOP): 2, ('w', ROOK): 3, ('w', QUEEN): 4, ('w', KING): 5,
			('b', PAWN): 6, ('b', KNIGHT): 7, ('b', BISHOP): 8, ('b', ROOK): 9, ('b', QUEEN): 10, ('b', KING): 11
		}

		for color in ['w', 'b']:
			for p_type, channel in piece_to_channel.items():
				if p_type[0] != color: continue
				bb = bb_mgr.piece_boards[color][p_type[1]]
				if bb == 0: continue  # skip empty boards without unpacking all 64 bits
				for i in range(64):
					if bb & (1 << i):
						obs[channel][i // 8][i % 8] = 1.0

		# Channel 12: Duck position. The duck is a single piece so we stop after the first bit.
		if bb_mgr.duck_board != 0:
			for i in range(64):
				if bb_mgr.duck_board & (1 << i):
					obs[12][i // 8][i % 8] = 1.0
					break

		# Channel 13: En passant target. A single cell is 1.0; all others stay 0.0.
		# Bounds-check guards against a stale target that slipped past the edge of the board.
		if en_passant_target:
			er, ec = en_passant_target
			if 0 <= er <= 7 and 0 <= ec <= 7:
				obs[13][er][ec] = 1.0

		# Channel 14: Side to move encoded as a constant plane so every spatial cell
		# the conv layers see carries the same turn signal — no need to look it up centrally.
		if turn == 'w':
			obs[14].fill(1.0)

		# Channels 15-18: Castling rights, also broadcast as full planes for the same reason.
		# White starts on row 7, Black on row 0 (board is stored rank-8-first).
		if can_castle_func(7, 4, True):  obs[15].fill(1.0)  # white kingside
		if can_castle_func(7, 4, False): obs[16].fill(1.0)  # white queenside
		if can_castle_func(0, 4, True):  obs[17].fill(1.0)  # black kingside
		if can_castle_func(0, 4, False): obs[18].fill(1.0)  # black queenside

		return obs