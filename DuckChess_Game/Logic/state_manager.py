import pygame
import random
import pickle
from DuckChess_Game.UI.settings import *
from DuckChess_Game.UI.pieces import Piece
from DuckChess_Game.Logic.ai import DuckAI

class StateManagerMixin:
	"""Handles the game loop, turn progression, piece movement, and win/draw conditions."""

	def init_ai(self):
		self.ai = DuckAI(depth=2)

	def init_board(self):
		setup = [(ROOK, 0, 0), (KNIGHT, 0, 1), (BISHOP, 0, 2), (QUEEN, 0, 3), (KING, 0, 4), (BISHOP, 0, 5),
				 (KNIGHT, 0, 6), (ROOK, 0, 7),
				 (ROOK, 7, 0), (KNIGHT, 7, 1), (BISHOP, 7, 2), (QUEEN, 7, 3), (KING, 7, 4), (BISHOP, 7, 5),
				 (KNIGHT, 7, 6), (ROOK, 7, 7)]
		for t, r, c in setup: self.board[r][c] = Piece('b' if r == 0 else 'w', t)
		for c in range(8): self.board[1][c], self.board[6][c] = Piece('b', PAWN), Piece('w', PAWN)

	def clear_board(self):
		"""Removes all pieces from the board."""
		self.board = [[None] * 8 for _ in range(8)]
		self.duck_pos = (-1, -1)
		self.turn = 'w'
		self.move_log = []
		self.history = []

	def set_piece(self, r, c, piece_type, color):
		"""Manually places a piece."""
		if piece_type == 'duck':
			self.duck_pos = (r, c)
			self.board[r][c] = None
		else:
			if self.duck_pos == (r, c): self.duck_pos = (-1, -1)
			self.board[r][c] = Piece(color, piece_type)

	def validate_editor_board(self):
		"""Ensures the custom board is playable (Kings exist)."""
		w_king = sum(1 for r in range(8) for c in range(8) if
					 self.board[r][c] and self.board[r][c].type == KING and self.board[r][c].color == 'w')
		b_king = sum(1 for r in range(8) for c in range(8) if
					 self.board[r][c] and self.board[r][c].type == KING and self.board[r][c].color == 'b')
		return w_king == 1 and b_king == 1

	def get_rank_file(self, r, c):
		return "87654321"[r], "abcdefgh"[c]

	def get_notation_coords(self, r, c):
		return f"{'abcdefgh'[c]}{'87654321'[r]}"

	def calculate_material_score(self, board_state):
		score = 0
		for r in range(8):
			for c in range(8):
				p = board_state[r][c]
				if p: score += PIECE_VALUES[p.type] * (1 if p.color == 'w' else -1)
		return score

	def generate_fen_signature(self):
		"""Generates a unique string representing the current board state + duck + turn."""
		board_str = ""
		for r in range(8):
			for c in range(8):
				p = self.board[r][c]
				if p:
					board_str += f"{p.color}{p.type}"
				else:
					board_str += "."

		return f"{board_str}|{self.duck_pos}|{self.turn}|{self.en_passant_target}"

	def get_disambiguation(self, start, end, piece):
		if piece.type == PAWN: return ""
		duplicates = []
		sr, sc = start
		for r in range(8):
			for c in range(8):
				if (r, c) == start: continue
				p = self.board[r][c]
				if p and p.type == piece.type and p.color == piece.color:
					moves = self.get_piece_legal_moves(r, c)
					if end in moves: duplicates.append((r, c))
		if not duplicates: return ""
		files_differ = True
		ranks_differ = True
		for (dr, dc) in duplicates:
			if dc == sc: files_differ = False
			if dr == sr: ranks_differ = False
		start_rank, start_file = self.get_rank_file(sr, sc)
		if files_differ: return start_file
		if ranks_differ: return start_rank
		return start_file + start_rank

	def check_game_end_conditions(self):
		"""Checks for 50-move rule, 3-fold repetition, and Stalemate (Loss)."""
		if self.game_over: return

		# 1. 50-Move Rule (100 half-moves)
		if self.half_move_clock >= 100:
			self.game_over = True
			self.winner = 'draw'
			print("Game Over: 50-Move Rule")
			return

		# 2. 3-Fold Repetition
		signature = self.generate_fen_signature()
		self.rep_history[signature] = self.rep_history.get(signature, 0) + 1
		if self.rep_history[signature] >= 3:
			self.game_over = True
			self.winner = 'draw'
			print("Game Over: 3-Fold Repetition")
			return

		# 3. Stalemate Logic (Player has no legal moves -> LOSS)
		has_moves = False
		for r in range(8):
			for c in range(8):
				p = self.board[r][c]
				if p and p.color == self.turn:
					if self.get_piece_legal_moves(r, c):
						has_moves = True
						break
			if has_moves: break

		if not has_moves:
			self.game_over = True
			self.winner = 'b' if self.turn == 'w' else 'w'
			print(f"Game Over: Stalemate (Win for {self.winner.upper()})")

	def execute_move(self, start, end, animated=True):
		sr, sc = start
		er, ec = end
		p = self.board[sr][sc]
		target = self.board[er][ec]
		sound = 'move'

		# --- 50-Move Rule Logic: Reset on Pawn move or Capture ---
		if p.type == PAWN or target is not None:
			self.half_move_clock = 0
		else:
			self.half_move_clock += 1

		# Sound Logic
		if target:
			sound = 'capture'
		elif p.type == PAWN and not target and sc != ec:
			sound = 'capture'

		# Animation
		if animated and hasattr(self, 'animate_move_visual'):
			self.animate_move_visual(start, end, p, is_duck=False)

		# Notation
		move_str = ""
		if p.type == KING and abs(sc - ec) == 2:
			move_str = "O-O" if ec > sc else "O-O-O"
			sound = 'castle'
		else:
			if p.type != PAWN:
				move_str += p.type
				move_str += self.get_disambiguation(start, end, p)
			is_capture = (target is not None) or (p.type == PAWN and sc != ec and not target)
			if is_capture:
				if p.type == PAWN: move_str += self.get_notation_coords(sr, sc)[0]
				move_str += "x"
				sound = 'capture'
			move_str += self.get_notation_coords(er, ec)

		# Update Board
		if p.type == PAWN and not target and sc != ec:
			self.board[sr][ec] = None  # En Passant Capture

		if p.type == KING and abs(sc - ec) == 2:
			ks = (ec > sc)
			rc, nrc = (7, 5) if ks else (0, 3)
			self.board[sr][nrc], self.board[sr][rc] = self.board[sr][rc], None
			self.board[sr][nrc].has_moved = True

		self.board[er][ec], self.board[sr][sc] = p, None
		p.has_moved = True

		next_ep = None
		if p.type == PAWN and abs(sr - er) == 2: next_ep = ((sr + er) // 2, sc)
		self.en_passant_target = next_ep

		enemy_color = 'b' if self.turn == 'w' else 'w'
		if self.is_in_check(enemy_color): move_str += "+"

		self.current_move_str = move_str
		self.last_move_arrow = (start, end)

		# King Capture Check
		if target and target.type == KING:
			self.game_over = True
			self.winner = self.turn
			sound = 'game_over'
			final_move_str = move_str.replace("x", "") + "#"
			self.current_move_str = final_move_str
			if self.turn == 'w':
				self.move_log.append(f"{self.turn_number}. {final_move_str}")
			else:
				self.move_log.append(f"{self.turn_number}... {final_move_str}")
			self.save_snapshot()

		if hasattr(self, 'play_sound'): self.play_sound(sound)

		# Promotion / Next Phase
		if not self.game_over:
			promote_rank = 0 if p.color == 'w' else 7
			if p.type == PAWN and er == promote_rank:

				is_ai_turn = (getattr(self, 'game_mode', '') == 'rl_training') or \
							 (getattr(self, 'game_mode', '') == 'white_ai' and self.turn == 'b') or \
							 (getattr(self, 'game_mode', '') == 'black_ai' and self.turn == 'w')

				if is_ai_turn:
					p.type = random.choice([QUEEN, ROOK, BISHOP, KNIGHT])
					self.current_move_str += f"={p.type}"
					if hasattr(self, 'play_sound'): self.play_sound('promote')
					self.prev_duck_pos = self.duck_pos
					self.phase = 'move_duck'

					if hasattr(self, 'debug_print_observation') and getattr(self, 'game_mode', '') != 'rl_training':
						self.debug_print_observation()
				else:
					self.promotion_pending = True
					self.promotion_coords = (er, ec)
					if hasattr(self, 'play_sound'): self.play_sound('notify')
			else:
				self.prev_duck_pos = self.duck_pos
				self.phase = 'move_duck'

				if hasattr(self, 'debug_print_observation') and getattr(self, 'game_mode', '') != 'rl_training':
					self.debug_print_observation()

	def promote_pawn(self, type_char):
		r, c = self.promotion_coords
		self.board[r][c].type = type_char
		self.current_move_str += f"={type_char}"
		enemy_color = 'b' if self.turn == 'w' else 'w'
		if self.is_in_check(enemy_color):
			if "+" not in self.current_move_str: self.current_move_str += "+"
		self.promotion_pending = False
		self.promotion_coords = None
		if hasattr(self, 'play_sound'): self.play_sound('promote')
		self.prev_duck_pos = self.duck_pos
		self.phase = 'move_duck'

	def place_duck(self, pos, animated=True):
		if self.board[pos[0]][pos[1]] or pos == self.prev_duck_pos: return

		if animated and self.duck_pos != (-1, -1) and hasattr(self, 'animate_move_visual'):
			self.animate_move_visual(self.duck_pos, pos, None, is_duck=True)

		log_entry = f"{self.current_move_str} @ {self.get_notation_coords(pos[0], pos[1])}"
		if self.turn == 'w':
			self.move_log.append(f"{self.turn_number}. {log_entry}")
		else:
			self.move_log.append(f"{self.turn_number}... {log_entry}")
			self.turn_number += 1

		self.duck_pos = pos
		if hasattr(self, 'play_sound'): self.play_sound('notify')

		# --- UPDATE STATE ---
		self.phase = 'move_piece'
		self.turn = 'b' if self.turn == 'w' else 'w'
		self.save_snapshot()

		# --- CHECK 3-FOLD, 50-MOVE, AND STALEMATE ---
		self.check_game_end_conditions()

		# AI Turn Trigger
		is_ai_next = (self.game_mode == 'white_ai' and self.turn == 'b') or \
					 (self.game_mode == 'black_ai' and self.turn == 'w')
		if is_ai_next and not self.game_over:
			self.waiting_for_ai = True
			self.ai_wait_start = pygame.time.get_ticks()
		else:
			self.waiting_for_ai = False

	def ai_turn(self):
		if self.view_index != len(self.history) - 1: return
		if self.game_over: return
		if not self.waiting_for_ai: return
		if pygame.time.get_ticks() - self.ai_wait_start < 400: return

		if self.phase == 'move_piece':
			move = self.ai.get_piece_move(self.board, self.turn, self.get_piece_legal_moves)
			if move:
				self.execute_move(move[0], move[1], animated=True)
			else:
				self.game_over = True
				self.winner = 'b' if self.turn == 'w' else 'w'

		elif self.phase == 'move_duck':
			target = self.ai.get_duck_move(self.board, self.duck_pos, self.prev_duck_pos)
			if target: self.place_duck(target, animated=True)

	def load_replay_file(self, filepath):
		"""
		Loads a .pkl replay file, resets the board, and silently executes
		all actions to populate the history array for the GUI viewer.
		"""
		try:
			with open(filepath, 'rb') as f:
				game_data = pickle.load(f)
		except Exception as e:
			print(f"Failed to load replay: {e}")
			return

		actions = game_data.get('action_history', [])
		if not actions:
			print("No action history found in this replay.")
			return

		self.reset_game_state()
		self.game_mode = 'replay'
		self.state = 'game'

		for act in actions:
			(sr, sc), (er, ec) = self._decode_move(act)
			if self.phase == 'move_piece':
				self.execute_move((sr, sc), (er, ec), animated=False)
			elif self.phase == 'move_duck':
				self.place_duck((er, ec), animated=False)

		self.view_index = 0
		print(f"Successfully loaded replay with {len(actions) // 2} full turns.")