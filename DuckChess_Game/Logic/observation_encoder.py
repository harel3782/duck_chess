import numpy as np
from DuckChess_Game.Logic.constants import *

class ObservationEncoder:
	"""Handles the conversion of the board state into a 19x8x8 numeric tensor using fast Bitboards."""

	def encode_state(self, bb_mgr, turn, en_passant_target, can_castle_func):
		"""Generates the observation tensor representing the current game state."""
		obs = np.zeros((19, 8, 8), dtype=np.float32)

		# Channels 0-11: Piece positions loaded directly from bitboards
		piece_to_channel = {
			('w', PAWN): 0, ('w', KNIGHT): 1, ('w', BISHOP): 2, ('w', ROOK): 3, ('w', QUEEN): 4, ('w', KING): 5,
			('b', PAWN): 6, ('b', KNIGHT): 7, ('b', BISHOP): 8, ('b', ROOK): 9, ('b', QUEEN): 10, ('b', KING): 11
		}

		for color in ['w', 'b']:
			for p_type, channel in piece_to_channel.items():
				if p_type[0] != color: continue
				bb = bb_mgr.piece_boards[color][p_type[1]]
				if bb == 0: continue
				for i in range(64):
					if bb & (1 << i):
						obs[channel][i // 8][i % 8] = 1.0

		# Channel 12: Duck position
		if bb_mgr.duck_board != 0:
			for i in range(64):
				if bb_mgr.duck_board & (1 << i):
					obs[12][i // 8][i % 8] = 1.0
					break

		# Channel 13: En Passant target
		if en_passant_target:
			er, ec = en_passant_target
			if 0 <= er <= 7 and 0 <= ec <= 7:
				obs[13][er][ec] = 1.0

		# Channel 14: Turn (1.0 for White, 0.0 for Black)
		if turn == 'w':
			obs[14].fill(1.0)

		# Channels 15-18: Castling rights (Kingside/Queenside for White/Black)
		if can_castle_func(7, 4, True): obs[15].fill(1.0)
		if can_castle_func(7, 4, False): obs[16].fill(1.0)
		if can_castle_func(0, 4, True): obs[17].fill(1.0)
		if can_castle_func(0, 4, False): obs[18].fill(1.0)

		return obs