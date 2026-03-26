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
		"""Generates a unique string representing the current board state."""
		board_str = ""
		for r in range(8):
			for c in range(8):
				p = self.board[r][c]
				if p: board_str += f"{p.color}{p.type}"
				else: board_str += "."
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
		files_differ, ranks_differ = True, True
		for (dr, dc) in duplicates:
			if dc == sc: files_differ = False
			if dr == sr: ranks_differ = False
		start_rank, start_file = self.get_rank_file(sr, sc)
		if files_differ: return start_file
		if ranks_differ: return start_rank
		return start_file + start_rank

	def check_game_end_conditions(self):
		"""Checks for game termination rules."""
		if self.game_over: return
		if self.half_move_clock >= 100:
			self.game_over = True; self.winner = 'draw'; return
		signature = self.generate_fen_signature()
		self.rep_history[signature] = self.rep_history.get(signature, 0) + 1
		if self.rep_history[signature] >= 3:
			self.game_over = True; self.winner = 'draw'; return
		has_moves = False
		for r in range(8):
			for c in range(8):
				p = self.board[r][c]
				if p and p.color == self.turn:
					if self.get_piece_legal_moves(r, c):
						has_moves = True; break
			if has_moves: break
		if not has_moves:
			self.game_over = True
			self.winner = 'b' if self.turn == 'w' else 'w'

	def execute_move(self, start, end, animated=True):
		sr, sc = start; er, ec = end
		p = self.board[sr][sc]; target = self.board[er][ec]
		sound = 'move'
		if p.type == PAWN or target is not None: self.half_move_clock = 0
		else: self.half_move_clock += 1
		if animated and hasattr(self, 'animate_move_visual'):
			self.animate_move_visual(start, end, p, is_duck=False)
		
		# Move processing
		if p.type == KING and abs(sc - ec) == 2:
			ks = (ec > sc); rc, nrc = (7, 5) if ks else (0, 3)
			self.board[sr][nrc], self.board[sr][rc] = self.board[sr][rc], None
			self.board[sr][nrc].has_moved = True
		self.board[er][ec], self.board[sr][sc] = p, None
		p.has_moved = True
		self.en_passant_target = ((sr + er) // 2, sc) if (p.type == PAWN and abs(sr - er) == 2) else None
		
		self.last_move_arrow = (start, end)
		if target and target.type == KING:
			self.game_over = True; self.winner = self.turn
			# Snapshot only on game end, otherwise wait for duck
			self.save_snapshot()
		
		if not self.game_over:
			self.prev_duck_pos, self.phase = self.duck_pos, 'move_duck'

	def place_duck(self, pos, animated=True):
		if self.board[pos[0]][pos[1]] or pos == self.prev_duck_pos: return
		if animated and self.duck_pos != (-1, -1) and hasattr(self, 'animate_move_visual'):
			self.animate_move_visual(self.duck_pos, pos, None, is_duck=True)
		
		# Log entry update
		log_entry = f"{self.current_move_str} @ {self.get_notation_coords(pos[0], pos[1])}"
		if self.turn == 'w': self.move_log.append(f"{self.turn_number}. {log_entry}")
		else: self.move_log.append(f"{self.turn_number}... {log_entry}"); self.turn_number += 1
		
		self.duck_pos = pos
		self.phase, self.turn = 'move_piece', ('b' if self.turn == 'w' else 'w')
		
		# Save snapshot only here - at the end of a complete turn
		self.save_snapshot()
		self.check_game_end_conditions()

	def load_replay_file(self, filepath):
		"""Loads a .pkl replay file and correctly populates history by turn."""
		try:
			with open(filepath, 'rb') as f:
				game_data = pickle.load(f)
		except Exception as e:
			print(f"Failed to load replay: {e}")
			return

		actions = game_data.get('action_history', [])
		if not actions: return

		self.reset_game_state() # Initial snapshot at index 0 [cite: 72]
		self.game_mode = 'replay'
		self.state = 'game'

		for act in actions:
			(sr, sc), (er, ec) = self._decode_move(act)
			if self.phase == 'move_piece':
				self.execute_move((sr, sc), (er, ec), animated=False)
			elif self.phase == 'move_duck':
				self.place_duck((er, ec), animated=False)
			# snapshot is handled internally by place_duck() or game end 

		self.view_index = len(self.history) - 1