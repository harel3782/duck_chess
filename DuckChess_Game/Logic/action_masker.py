import numpy as np

class ActionMasker:
	"""Handles the generation of action masks and decoding RL action indices."""

	def get_valid_action_masks(self, board, turn, phase, get_legal_moves_func, duck_pos, prev_duck_pos):
		"""Generates a boolean array of length 4096 representing all valid moves."""
		masks = np.zeros(4096, dtype=bool)

		if phase == 'move_piece':
			for r in range(8):
				for c in range(8):
					p = board[r][c]
					if p and p.color == turn:
						valid_destinations = get_legal_moves_func(r, c)
						for (dr, dc) in valid_destinations:
							action_idx = self.encode_move((r, c), (dr, dc))
							masks[action_idx] = True
		elif phase == 'move_duck':
			for r in range(8):
				for c in range(8):
					if not board[r][c] and (r, c) != prev_duck_pos:
						action_idx = self.encode_move(duck_pos, (r, c))
						masks[action_idx] = True

		return masks

	def encode_move(self, start, end):
		"""Converts start and end coordinates to an integer index (0-4095)."""
		sr, sc = start
		er, ec = end
		if sr == -1: sr, sc = 0, 0 # Fallback for initial duck placement
		return int((sr * 8 + sc) * 64 + (er * 8 + ec))

	def decode_move(self, action_index):
		"""Converts an integer index (0-4095) back to start and end coordinates."""
		# STRIP NUMPY TYPE: Convert strictly to standard python integer
		action_index = int(action_index) 
		start_sq = action_index // 64
		end_sq = action_index % 64
		return (start_sq // 8, start_sq % 8), (end_sq // 8, end_sq % 8)