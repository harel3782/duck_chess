import numpy as np
from DuckChess_Game.Logic.constants import *

class ObservationEncoder:
	"""Handles the conversion of the board state into a 19x8x8 numeric tensor for the RL agent."""

	def encode_state(self, board, duck_pos, turn, en_passant_target, can_castle_func):
		"""Generates the observation tensor representing the current game state."""
		obs = np.zeros((19, 8, 8), dtype=np.float32)

		# Channels 0-11: Piece positions
		piece_to_channel = {
			('w', PAWN): 0, ('w', KNIGHT): 1, ('w', BISHOP): 2, ('w', ROOK): 3, ('w', QUEEN): 4, ('w', KING): 5,
			('b', PAWN): 6, ('b', KNIGHT): 7, ('b', BISHOP): 8, ('b', ROOK): 9, ('b', QUEEN): 10, ('b', KING): 11
		}

		for r in range(8):
			for c in range(8):
				p = board[r][c]
				if p:
					channel = piece_to_channel.get((p.color, p.type))
					if channel is not None:
						obs[channel][r][c] = 1.0

		# Channel 12: Duck position
		if duck_pos != (-1, -1):
			obs[12][duck_pos[0]][duck_pos[1]] = 1.0

		# Channel 13: En Passant target
		if en_passant_target:
			obs[13][en_passant_target[0]][en_passant_target[1]] = 1.0

		# Channel 14: Turn (1.0 for White, 0.0 for Black)
		if turn == 'w':
			obs[14].fill(1.0)

		# Channels 15-18: Castling rights (Kingside/Queenside for White/Black)
		if can_castle_func(7, 4, True): obs[15].fill(1.0)  # White Kingside
		if can_castle_func(7, 4, False): obs[16].fill(1.0) # White Queenside
		if can_castle_func(0, 4, True): obs[17].fill(1.0)  # Black Kingside
		if can_castle_func(0, 4, False): obs[18].fill(1.0) # Black Queenside

		return obs