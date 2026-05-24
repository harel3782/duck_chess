import numpy as np

class ActionMasker:
	"""Handles the generation of action masks and decoding RL action indices."""

	def get_valid_action_masks(self, bb_mgr, turn, phase, get_legal_moves_func, duck_pos, prev_duck_pos):
		"""Generates a boolean array of length 4096 representing all valid moves."""
		masks = np.zeros(4096, dtype=bool)

		if phase == 'move_piece':
			# Fast iteration using occupancy
			my_pieces = bb_mgr.white_occupancy if turn == 'w' else bb_mgr.black_occupancy
			for i in range(64):
				if my_pieces & (1 << i):
					r, c = i // 8, i % 8
					valid_destinations = get_legal_moves_func(r, c)
					for (dr, dc) in valid_destinations:
						action_idx = self.encode_move((r, c), (dr, dc))
						masks[action_idx] = True
						
		elif phase == 'move_duck':
			# Extremely fast valid duck square calculation using bitwise NOT
			valid_duck_squares = ~(bb_mgr.all_occupancy) & 0xFFFFFFFFFFFFFFFF
			if prev_duck_pos != (-1, -1):
				valid_duck_squares &= ~(1 << (prev_duck_pos[0] * 8 + prev_duck_pos[1]))
			
			for i in range(64):
				if valid_duck_squares & (1 << i):
					dr, dc = i // 8, i % 8
					action_idx = self.encode_move((0, 0), (dr, dc))
					masks[action_idx] = True

		return masks

	def encode_move(self, start, end):
		"""Converts start and end coordinates to an integer index (0-4095)."""
		sr, sc = start
		er, ec = end
		if sr == -1: sr, sc = 0, 0
		return int((sr * 8 + sc) * 64 + (er * 8 + ec))

	def decode_move(self, action_index):
		"""Converts an integer index (0-4095) back to start and end coordinates."""
		action_index = int(action_index) 
		start_sq = action_index // 64
		end_sq = action_index % 64
		return (start_sq // 8, start_sq % 8), (end_sq // 8, end_sq % 8)