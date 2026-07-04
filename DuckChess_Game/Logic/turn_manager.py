import time
from DuckChess_Game.Logic.constants import *
from DuckChess_Game.Logic.notation_helper import NotationHelper
from DuckChess_Game.Logic.move_executor import MoveExecutor

class TurnManagerMixin:
	"""Handles movement logic, state updates, and 50-move rule maintenance.

	Every full turn is two phases stored in self.phase:
	  'move_piece' → player moves a piece (execute_move) → transitions to 'move_duck'
	  'move_duck'  → player places the duck (place_duck)  → flips turn back to 'move_piece'
	Exception: capturing the enemy king ends the game immediately, skipping duck placement.
	"""

	def execute_move(self, start, end, animated=True):
		"""Executes a move, updates clocks, and sets the last move highlight."""
		p = self.board[start[0]][start[1]]
		if not p: return

		# --- RECORD ACTION FOR JSON REPLAYS ---
		if getattr(self, 'game_mode', '') != 'replay':
			if not hasattr(self, 'replay_actions'): self.replay_actions = []
			self.replay_actions.append({'type': 'piece', 'start': start, 'end': end})

		self.last_move_arrow = (start, end)
		ep_target = getattr(self, 'en_passant_target', None)
		is_capture = self.board[end[0]][end[1]] or (p.type == PAWN and end == ep_target)
		
		# Identify Castling: King moves 2 horizontal squares
		is_castle = (p.type == KING and abs(start[1] - end[1]) == 2)
		
		move_str = p.type if p.type != PAWN else ""
		if is_capture: move_str += "x"
		move_str += NotationHelper.get_notation_coords(end[0], end[1])
		self.current_move_str = move_str

		if animated and hasattr(self, 'animate_move_visual'):
			self.animate_move_visual(start, end, p, is_duck=False)

		# Pass the bitboard manager to the executor to keep states synced
		bb_mgr = getattr(self, 'bb_mgr', None)
		captured = MoveExecutor().execute_piece_move(self.board, start, end, ep_target, bb_mgr)

		if p.type == PAWN and abs(start[0] - end[0]) == 2:
			self.en_passant_target = ((start[0] + end[0]) // 2, start[1])
		else:
			self.en_passant_target = None

		if p.type == PAWN or is_capture:
			self.half_move_clock = 0
		else:
			self.half_move_clock = getattr(self, 'half_move_clock', 0) + 1

		# --- SOUND LOGIC ---
		enemy_color = 'b' if self.turn == 'w' else 'w'
		is_check = self.is_in_check(enemy_color)

		if hasattr(self, 'play_sound') and getattr(self, 'game_mode', '') != 'replay':
			if is_check:
				self.play_sound('move_check')
			elif is_castle:
				self.play_sound('castle')
			elif captured:
				self.play_sound('capture')
			else:
				self.play_sound('move')

		if captured and captured.type == KING:
			# Duck Chess win condition: capturing the king ends the game instantly.
			# No check/checkmate — the king is taken like any other piece.
			# Duck placement is skipped; the turn never flips.
			self.current_move_str += "#"
			if self.turn == 'w':
				self.move_log.append(f"{self.turn_number}. {self.current_move_str}")
			else:
				self.move_log.append(f"{self.turn_number}... {self.current_move_str}")

			self.game_over, self.winner = True, self.turn
			if hasattr(self, 'play_sound') and getattr(self, 'game_mode', '') != 'replay':
				self.play_sound('game_over')
			self.save_snapshot()
		else:
			promote_rank = 0 if p.color == 'w' else 7
			if p.type == PAWN and end[0] == promote_rank:
				self._handle_auto_promotion(p, end)
			else:
				# Snapshot the duck's current position before the duck phase begins.
				# place_duck uses prev_duck_pos to forbid replanting on the same square.
				self.prev_duck_pos, self.phase = self.duck_pos, 'move_duck'

	def _handle_auto_promotion(self, pawn, pos):
		"""Logic for automatic promotion."""
		game_mode = getattr(self, 'game_mode', '')
		is_auto = game_mode in ('rl_training', 'replay') or \
				 (game_mode == 'white_ai' and self.turn == 'b') or \
				 (game_mode == 'black_ai' and self.turn == 'w')
		if is_auto:
			if hasattr(self, 'bb_mgr'):
				self.bb_mgr.remove_piece(pawn.color, PAWN, pos[0], pos[1])
				self.bb_mgr.add_piece(pawn.color, QUEEN, pos[0], pos[1])

			pawn.type, self.current_move_str = QUEEN, self.current_move_str + "=Q"
			if hasattr(self, 'play_sound') and game_mode != 'replay': 
				self.play_sound('promote')
			self.prev_duck_pos, self.phase = self.duck_pos, 'move_duck'
		else:
			self.promotion_pending, self.promotion_coords = True, pos

	def promote_pawn(self, type_char):
		"""Handles manual pawn promotion from the UI."""
		if not getattr(self, 'promotion_coords', None): return
		
		# --- RECORD ACTION FOR JSON REPLAYS ---
		if getattr(self, 'game_mode', '') != 'replay':
			if not hasattr(self, 'replay_actions'): self.replay_actions = []
			self.replay_actions.append({'type': 'promote', 'piece': type_char})

		r, c = self.promotion_coords
		pawn = self.board[r][c]

		if hasattr(self, 'bb_mgr'):
			self.bb_mgr.remove_piece(pawn.color, PAWN, r, c)
			self.bb_mgr.add_piece(pawn.color, type_char, r, c)

		pawn.type = type_char
		self.current_move_str += f"={type_char}"
		self.promotion_pending = False
		self.promotion_coords = None
		
		enemy_color = 'b' if self.turn == 'w' else 'w'
		is_check = self.is_in_check(enemy_color)

		if hasattr(self, 'play_sound'): 
			if is_check: self.play_sound('move_check')
			else: self.play_sound('promote')
			
		self.prev_duck_pos, self.phase = self.duck_pos, 'move_duck'

	def place_duck(self, pos, animated=True):
		"""Finalizes turn by placing the duck, then hands control to the other side."""
		# Reject occupied squares and the duck's own previous square (can't stay in place).
		if self.board[pos[0]][pos[1]] or pos == getattr(self, 'prev_duck_pos', (-1, -1)): return
		
		# --- RECORD ACTION FOR JSON REPLAYS ---
		if getattr(self, 'game_mode', '') != 'replay':
			if not hasattr(self, 'replay_actions'): self.replay_actions = []
			self.replay_actions.append({'type': 'duck', 'pos': pos})

		coords = NotationHelper.get_notation_coords(pos[0], pos[1])
		log_entry = f"{self.current_move_str} @ {coords}"
		
		if hasattr(self, 'bb_mgr'):
			self.bb_mgr.move_duck(pos[0], pos[1])
			
		# Turn flips here — everything below sees the NEXT player's color.
		self.duck_pos, self.phase, self.turn = pos, 'move_piece', ('b' if self.turn == 'w' else 'w')

		# --- PARALLEL STATE SANITY CHECK ---
		if hasattr(self, 'bb_mgr'):
			if not self.bb_mgr.verify_sync(self.board, self.duck_pos):
				print("CRITICAL WARNING: The Bitboard engine is out of sync with the 2D board!")

		# After the flip, turn=='b' means WHITE just finished; turn=='w' means BLACK just finished.
		if self.turn == 'b': self.move_log.append(f"{self.turn_number}. {log_entry}")
		else:
			self.move_log.append(f"{self.turn_number}... {log_entry}")
			self.turn_number += 1
			
		if hasattr(self, 'play_sound') and getattr(self, 'game_mode', '') != 'replay':
			self.play_sound('notify')

		self.save_snapshot()
		self.check_game_end_conditions()
		
		is_ai_next = (self.game_mode == 'white_ai' and self.turn == 'b') or \
					 (self.game_mode == 'black_ai' and self.turn == 'w')
		if is_ai_next and not self.game_over:
			self.waiting_for_ai, self.ai_wait_start = True, int(time.monotonic() * 1000)
		else: self.waiting_for_ai = False

	def ai_turn(self):
		"""AI logic using either the RL model or basic AI."""
		if self.view_index != len(self.history) - 1 or getattr(self, 'game_over', False) or not getattr(self, 'waiting_for_ai', False): return
		if int(time.monotonic() * 1000) - getattr(self, 'ai_wait_start', 0) < AI_MOVE_DELAY: return

		# IF WE HAVE AN MCTS SEARCHER (strongest: policy priors + distilled value)
		if getattr(self, 'rl_searcher', None) is not None:
			if self.phase == 'move_piece':
				from DuckChess_Game.SBThree.mcts import headless_snapshot
				# MCTS evaluates piece + duck together in one search, so both actions are
				# returned now and the duck action is stashed for the move_duck phase.
				piece_a, duck_a = self.rl_searcher.choose_turn(headless_snapshot(self))
				self._pending_duck_action = duck_a
				if piece_a is None:
					self.game_over, self.winner = True, ('b' if self.turn == 'w' else 'w')
					self.waiting_for_ai = False
					return
				start, end = self._decode_move(piece_a)
				self.execute_move(start, end, animated=True)
			else:  # move_duck — play the duck MCTS chose alongside the piece move
				duck_a = getattr(self, '_pending_duck_action', None)
				if duck_a is not None:
					_, end = self._decode_move(duck_a)
					self.place_duck(end, animated=True)
				else:
					target = self.ai.get_duck_move(self.board, getattr(self, 'duck_pos', (-1, -1)), getattr(self, 'prev_duck_pos', (-1, -1)))
					if target: self.place_duck(target, animated=True)
			self.ai_wait_start = int(time.monotonic() * 1000)
			return

		# IF WE HAVE AN RL MODEL LOADED
		if hasattr(self, 'rl_model') and self.rl_model is not None:
			obs = self._get_obs()
			masks = self.action_masks()
			import torch as th
			
			# --- THE "HYBRID" APPROACH ---
			# Use random sampling for the first 5 turns to create variety,
			# then switch to strict deterministic (greedy) play for the rest of the game.
			current_turn = getattr(self, 'turn_number', 1)
			is_deterministic = current_turn > 5
			
			action, _ = self.rl_model.predict(obs, action_masks=masks, deterministic=is_deterministic)
			
			if self.phase == 'move_piece':
				start, end = self._decode_move(action)
				self.execute_move(start, end, animated=True)
			elif self.phase == 'move_duck':
				_, end = self._decode_move(action)
				self.place_duck(end, animated=True)

			self.ai_wait_start = int(time.monotonic() * 1000)
			return

		# FALLBACK TO BASIC AI (The old logic)
		if self.phase == 'move_piece':
			move = self.ai.get_piece_move(self.board, self.turn, self.get_piece_legal_moves)
			if move:
				self.execute_move(move[0], move[1], animated=True)
				self.ai_wait_start = int(time.monotonic() * 1000)
			else:
				self.game_over, self.winner = True, ('b' if self.turn == 'w' else 'w')
				self.waiting_for_ai = False
		elif self.phase == 'move_duck':
			target = self.ai.get_duck_move(self.board, getattr(self, 'duck_pos', (-1,-1)), getattr(self, 'prev_duck_pos', (-1,-1)))
			if target: self.place_duck(target, animated=True)