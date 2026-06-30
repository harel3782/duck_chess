from DuckChess_Game.Logic.observation_encoder import ObservationEncoder
from DuckChess_Game.Logic.action_masker import ActionMasker
from DuckChess_Game.Logic.notation_helper import NotationHelper

class RLMixin:
	"""Thin adapter exposing _get_obs / action_masks / _decode_move to GameLogicMixin.

	Delegates all real work to ObservationEncoder and ActionMasker. Both helpers
	are stateless, so a new instance is created per call — no shared state to corrupt
	between the UI and RL training paths.
	"""

	def _get_obs(self):
		"""Returns the current board state encoded as a 19×8×8 float32 tensor."""
		encoder = ObservationEncoder()
		return encoder.encode_state(
			bb_mgr=self.bb_mgr,
			turn=self.turn,
			en_passant_target=getattr(self, 'en_passant_target', None),
			can_castle_func=self.can_castle
		)

	def action_masks(self):
		"""Returns a boolean array mapping all legally available moves for the current state."""
		masker = ActionMasker()
		return masker.get_valid_action_masks(
			bb_mgr=self.bb_mgr,
			turn=self.turn,
			phase=getattr(self, 'phase', 'move_piece'),
			get_legal_moves_func=self.get_piece_legal_moves,
			duck_pos=self.duck_pos,
			prev_duck_pos=getattr(self, 'prev_duck_pos', (-1, -1))
		)

	def _decode_move(self, action_index):
		"""Translates an RL action index back to board coordinates."""
		masker = ActionMasker()
		return masker.decode_move(action_index)

	def debug_print_observation(self):
		"""Prints active squares for channels 0-14 (pieces, duck, EP, turn) to the console.
		Channels 15-18 (castling rights) are omitted for brevity.
		"""
		# Guard against flooding stdout during training or replay playback.
		if getattr(self, 'game_mode', '') in ['rl_training', 'replay']: return
		
		obs = self._get_obs()
		channel_names = {
			0: "White Pawns", 1: "White Knights", 2: "White Bishops",
			3: "White Rooks", 4: "White Queens", 5: "White King",
			6: "Black Pawns", 7: "Black Knights", 8: "Black Bishops",
			9: "Black Rooks", 10: "Black Queens", 11: "Black King",
			12: "Duck Position", 13: "En Passant Target"
		}

		print("\n" + "=" * 40)
		print("OBSERVATION TENSOR STATE")
		print("=" * 40)

		for channel in range(14):
			active_squares = []
			for r in range(8):
				for c in range(8):
					if obs[channel][r][c] == 1.0:
						coords = NotationHelper.get_notation_coords(r, c)
						active_squares.append(coords)

			if active_squares:
				print(f"[{channel}] {channel_names[channel]:<18}: {', '.join(active_squares)}")

		print("-" * 40)
		# Channel 14 is a constant plane: all cells are 1.0 for white, 0.0 for black.
		# Reading any single cell ([0][0]) is sufficient to determine the turn.
		current_turn = "White" if obs[14][0][0] == 1.0 else "Black"
		print(f"[14] Turn               : {current_turn}")