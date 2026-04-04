import gymnasium as gym
import numpy as np
from gymnasium import spaces
import torch as th
import pickle
import time
import os

from DuckChess_Game.Logic.logic import GameLogicMixin
from DuckChess_Game.Logic.rules_checker import RulesChecker
from DuckChess_Game.Logic.constants import KING, KNIGHT, BISHOP, PIECE_VALUES

class HeadlessEngine(GameLogicMixin):
	"""A lightweight version of the game strictly for fast RL training."""
	def __init__(self):
		self.game_mode = 'rl_training'
		self.reset_game_state()

class DuckChessEnvStage9(gym.Env):
	"""Stage 9 Environment: Smart Self-Play with Tactical Overrides to punish hanging pieces."""
	def __init__(self, render_mode=None):
		super(DuckChessEnvStage9, self).__init__()
		self.action_space = spaces.Discrete(4096)
		self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(19, 8, 8), dtype=np.float32)
		self.render_mode = render_mode
		
		self.engine = HeadlessEngine()
		self.opponent_model = None
		self.episode_counter = 0
		self.current_episode_actions = []
		
		self.learning_color = 'w'
		self.opponent_color = 'b'
		
		# Strategic Scaling Factors
		self.material_scale = 0.05
		self.loss_penalty_multiplier = 1.5
		self.castling_bonus = 0.2
		self.development_bonus = 0.05
		self.defense_bonus = 0.03
		self.duck_blocking_scale = 0.015
		self.step_penalty = -0.005
		self.checker = RulesChecker()

	def set_opponent(self, model_path):
		"""Loads a saved MaskablePPO model to act as the opponent."""
		from sb3_contrib import MaskablePPO
		if os.path.exists(model_path):
			try:
				self.opponent_model = MaskablePPO.load(model_path, device="cpu")
			except Exception as e:
				print(f"Error loading opponent model: {e}")

	def _count_threats(self, color):
		threats = 0
		board = self.engine.board
		duck = self.engine.duck_pos
		for r in range(8):
			for c in range(8):
				p = board[r][c]
				if p and p.color == color:
					if self.checker.is_in_check(color, board, duck):
						threats += 1
		return threats

	def _calculate_mobility(self, color):
		"""Calculates the total number of legal moves available to a specific color."""
		mobility = 0
		for r in range(8):
			for c in range(8):
				p = self.engine.board[r][c]
				if p and p.color == color:
					moves = self.engine.get_piece_legal_moves(r, c)
					mobility += len(moves)
		return mobility

	def reset(self, seed=None, options=None):
		super().reset(seed=seed)
		self.engine.reset_game_state()
		self.current_episode_actions = []
		self.episode_counter += 1
		self.learning_color = np.random.choice(['w', 'b'])
		self.opponent_color = 'b' if self.learning_color == 'w' else 'w'
		
		# If the learning agent is Black, the opponent must move first
		if self.learning_color == 'b':
			self._play_opponent_turn()
			
		return self.get_observation(), {}

	def get_observation(self):
		return self.engine._get_obs()

	def action_masks(self):
		masks = self.engine.action_masks()
		if not np.any(masks):
			masks[0] = True
			return masks

		if getattr(self.engine, 'phase', '') == 'move_piece':
			forced_capture_mask = np.zeros(4096, dtype=bool)
			found_king_capture = False
			board = self.engine.board
			
			for action in np.where(masks)[0]:
				start, end = self.engine._decode_move(action)
				target_piece = board[end[0]][end[1]]
				if target_piece and target_piece.type == KING and target_piece.color != self.engine.turn:
					forced_capture_mask[action] = True
					found_king_capture = True
					
			if found_king_capture:
				return forced_capture_mask
		return masks

	def _get_smart_opponent_mask(self, original_mask):
		"""
		Twist 2: Filters out suicidal King moves for the opponent.
		Creates a custom mask where moving the King into check is illegal.
		"""
		smart_mask = original_mask.copy()
		if getattr(self.engine, 'phase', '') != 'move_piece':
			return smart_mask

		board = self.engine.board
		
		for action in np.where(smart_mask)[0]:
			start, end = self.engine._decode_move(action)
			piece = board[start[0]][start[1]]
			
			if piece and piece.type == KING:
				# Temporarily apply move to check for safety
				target_piece = board[end[0]][end[1]]
				board[end[0]][end[1]] = piece
				board[start[0]][start[1]] = None
				
				# Check if the square is safe from the learning agent's attacks
				is_attacked = self.checker.is_in_check(self.opponent_color, board, self.engine.duck_pos)
				
				# Revert the board state
				board[start[0]][start[1]] = piece
				board[end[0]][end[1]] = target_piece
				
				# If the move results in check, disable it for the opponent
				if is_attacked:
					smart_mask[action] = False

		# Fallback: if all moves lead to check (forced loss), use the original mask
		if not np.any(smart_mask):
			return original_mask
			
		return smart_mask

	def _get_opponent_action(self):
		"""Pure Self-Play Logic with Tactical Overrides."""
		current_mask = self.action_masks()
		valid_actions = np.where(current_mask)[0]
		
		if len(valid_actions) == 0:
			return 0

		if self.engine.phase == 'move_piece':
			# Twist 1: Favorable Captures
			# If the opponent can capture a higher value piece with a lower value piece, do it 100% of the time.
			best_capture = None
			max_gain = 0
			
			for action in valid_actions:
				start, end = self.engine._decode_move(action)
				attacker = self.engine.board[start[0]][start[1]]
				target = self.engine.board[end[0]][end[1]]
				
				if attacker and target:
					att_val = PIECE_VALUES.get(attacker.type, 0)
					tgt_val = PIECE_VALUES.get(target.type, 0)
					
					# Only capture if the target is strictly more valuable than the attacker
					if tgt_val > att_val:
						gain = tgt_val - att_val
						if gain > max_gain:
							max_gain = gain
							best_capture = action
							
			# Execute the brutal tactical punish immediately
			if best_capture is not None:
				return best_capture

		# Apply Twist 2 mask to prevent the opponent from handing away the King
		smart_mask = self._get_smart_opponent_mask(current_mask)
		
		# Rely on the loaded opponent model to make standard strategic decisions
		if self.opponent_model is not None:
			obs = self.get_observation()
			with th.no_grad():
				action, _ = self.opponent_model.predict(obs, action_masks=smart_mask, deterministic=False)
			return action
			
		# Fallback if no model is loaded
		return np.random.choice(np.where(smart_mask)[0])

	def _save_replay(self, reason):
		save_dir = os.path.join("saved_replays", "stage 9")
		os.makedirs(save_dir, exist_ok=True)
		safe_reason = "".join([c for c in reason if c.isalpha() or c.isdigit() or c=='_'])[:30]
		filename = os.path.join(save_dir, f"{safe_reason}_ep{self.episode_counter}_{int(time.time())}.pkl")
		try:
			with open(filename, 'wb') as f:
				pickle.dump({
					'action_history': self.current_episode_actions,
					'learning_color': self.learning_color,
					'opponent_color': self.opponent_color
				}, f)
		except: pass

	def _apply_action(self, action):
		start, end = self.engine._decode_move(action)
		if self.engine.phase == 'move_piece':
			self.engine.execute_move(start, end, animated=False)
		elif self.engine.phase == 'move_duck':
			self.engine.place_duck(end, animated=False)

	def _play_opponent_turn(self):
		while self.engine.turn == self.opponent_color and not getattr(self.engine, 'game_over', False):
			if not np.any(self.action_masks()):
				self.engine.game_over = True
				self.engine.winner = 'draw'
				break
			opp_action = self._get_opponent_action()
			self._apply_action(opp_action)
			self.current_episode_actions.append(int(opp_action))

	def step(self, action):
		try:
			if not np.any(self.action_masks()):
				return self.get_observation(), 0.0, True, False, {}

			threats_before = self._count_threats(self.learning_color)
			old_material = self.engine.calculate_material_score(self.engine.board)

			opp_mobility_before = 0
			if self.engine.phase == 'move_duck':
				opp_mobility_before = self._calculate_mobility(self.opponent_color)

			pos_bonus = 0
			if self.engine.phase == 'move_piece':
				start, end = self.engine._decode_move(action)
				piece = self.engine.board[start[0]][start[1]]
				if piece is not None:
					if piece.type == KING and abs(start[1] - end[1]) == 2:
						pos_bonus += self.castling_bonus
					elif piece.type in [KNIGHT, BISHOP]:
						back_rank = 7 if self.learning_color == 'w' else 0
						if start[0] == back_rank and end[0] != back_rank:
							pos_bonus += self.development_bonus

			self._apply_action(action)
			self.current_episode_actions.append(int(action))

			duck_bonus = 0
			blocking_bonus = 0

			if self.engine.phase == 'move_piece':
				threats_after = self._count_threats(self.learning_color)
				if threats_before > threats_after:
					duck_bonus = (threats_before - threats_after) * self.defense_bonus

				opp_mobility_after = self._calculate_mobility(self.opponent_color)
				if opp_mobility_before > opp_mobility_after:
					blocking_bonus = (opp_mobility_before - opp_mobility_after) * self.duck_blocking_scale
				
				if not getattr(self.engine, 'game_over', False):
					self._play_opponent_turn()

			new_material = self.engine.calculate_material_score(self.engine.board)
			
			if self.learning_color == 'w':
				material_diff = new_material - old_material
			else:
				material_diff = old_material - new_material

			if material_diff < 0:
				material_reward = material_diff * self.material_scale * self.loss_penalty_multiplier
			else:
				material_reward = material_diff * self.material_scale

			reward = material_reward + duck_bonus + pos_bonus + blocking_bonus + self.step_penalty
			terminated = getattr(self.engine, 'game_over', False)
			
			if terminated:
				if self.engine.winner == self.learning_color:
					reward += 1.0
				elif self.engine.winner == self.opponent_color:
					reward -= 1.0

			if terminated and self.episode_counter % 1000 == 0:
				self._save_replay("periodic_sample")

			return self.get_observation(), reward, terminated, False, {}

		except Exception as e:
			self._save_replay(f"CRASH_{type(e).__name__}")
			raise e

	def render(self): pass
	def close(self): pass