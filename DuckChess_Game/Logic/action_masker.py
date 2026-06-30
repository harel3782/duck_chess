import numpy as np

class ActionMasker:
	"""Handles the generation of action masks and decoding RL action indices.

	The action space is 64 × 64 = 4096: every ordered (from_square, to_square) pair,
	including illegal ones. The mask is a boolean array where True means "legal in the
	current position and phase." MaskablePPO zeroes out logits for False entries,
	ensuring the model never samples an illegal action.
	"""

	def get_valid_action_masks(self, bb_mgr, turn, phase, get_legal_moves_func, duck_pos, prev_duck_pos):
		"""Returns a 4096-length bool array: True = legal action for the current phase."""
		masks = np.zeros(4096, dtype=bool)

		if phase == 'move_piece':
			# Iterate only over squares occupied by the current player using the
			# occupancy bitboard — avoids scanning all 64 squares of the 2D array.
			my_pieces = bb_mgr.white_occupancy if turn == 'w' else bb_mgr.black_occupancy
			for i in range(64):
				if my_pieces & (1 << i):
					r, c = i // 8, i % 8
					valid_destinations = get_legal_moves_func(r, c)
					for (dr, dc) in valid_destinations:
						action_idx = self.encode_move((r, c), (dr, dc))
						masks[action_idx] = True

		elif phase == 'move_duck':
			# Invert all_occupancy to get every empty square in one operation.
			# The & 0xFFFF... truncates to 64 bits because Python's ~ on an int
			# produces an arbitrary-precision negative number, not a 64-bit mask.
			valid_duck_squares = ~(bb_mgr.all_occupancy) & 0xFFFFFFFFFFFFFFFF
			# Duck must actually move — remove the square it currently occupies.
			if prev_duck_pos != (-1, -1):
				valid_duck_squares &= ~(1 << (prev_duck_pos[0] * 8 + prev_duck_pos[1]))

			for i in range(64):
				if valid_duck_squares & (1 << i):
					dr, dc = i // 8, i % 8
					# Duck placements encode with a dummy (0,0) "from" square; see decode_move.
					action_idx = self.encode_move((0, 0), (dr, dc))
					masks[action_idx] = True

		return masks

	def encode_move(self, start, end):
		"""Encodes (from_square, to_square) as a single index: from_sq * 64 + to_sq."""
		sr, sc = start
		er, ec = end
		# Normalize the (-1,-1) duck sentinel to (0,0) to match the decode_move convention.
		if sr == -1: sr, sc = 0, 0
		return int((sr * 8 + sc) * 64 + (er * 8 + ec))

	def decode_move(self, action_index):
		"""Converts an integer index (0-4095) back to start and end coordinates.

		NOTE: index block 0..63 (start==(0,0)) is OVERLOADED — it is both a piece
		move FROM a8 and a duck placement (ducks encode a dummy (0,0) start). This
		function cannot tell them apart; only the engine PHASE disambiguates, so a
		decoded index must always be interpreted in the context of the current
		phase (see BaseDuckChessEnv._apply_action, which asserts that invariant)."""
		action_index = int(action_index) 
		start_sq = action_index // 64
		end_sq = action_index % 64
		return (start_sq // 8, start_sq % 8), (end_sq // 8, end_sq % 8)