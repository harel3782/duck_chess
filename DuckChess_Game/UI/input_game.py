import pygame
from DuckChess_Game.Logic.save_manager import SaveManager

class GameInputMixin:
	"""Handles user input during active gameplay with click-to-move support."""

	def handle_promotion_click(self, pos):
		"""Handles clicks within the horizontal pawn promotion menu."""
		for rect, p_type in getattr(self, 'get_promotion_rects', lambda: [])():
			if rect.collidepoint(pos):
				self.promote_pawn(p_type)
				break

	def handle_mouse_down(self, pos):
		"""Processes all primary left-clicks."""
		# 1. Navigation Arrows
		if self.nav_btns['start'].collidepoint(pos): self.view_index, self.is_user_scrolling = 0, False; return
		if self.nav_btns['prev'].collidepoint(pos): self.view_index, self.is_user_scrolling = max(0, self.view_index - 1), False; return
		if self.nav_btns['next'].collidepoint(pos): self.view_index, self.is_user_scrolling = min(len(self.history) - 1, self.view_index + 1), False; return
		if self.nav_btns['end'].collidepoint(pos): self.view_index, self.is_user_scrolling = len(self.history) - 1, False; return

		# 2. Bottom HUD Buttons
		if self.restart_btn_rect.collidepoint(pos): self.reset_game_state(); return
		if hasattr(self, 'eval_btn_rect') and self.eval_btn_rect.collidepoint(pos): self.show_eval = not getattr(self, 'show_eval', True); return
		if self.menu_btn_rect.collidepoint(pos): self.state = 'menu'; return
		if getattr(self, 'game_mode', '') == 'pvp' and hasattr(self, 'flip_btn_rect') and self.flip_btn_rect.collidepoint(pos):
			self.player_side = 'b' if self.player_side == 'w' else 'w'; return

		# 3. History Panel Interaction
		panel_rect = pygame.Rect(self.screen_w - self.panel_width, 0, self.panel_width, self.screen_h)
		if panel_rect.collidepoint(pos):
			self.history_dragging, self.last_mouse_y, self.is_user_scrolling = True, pos[1], True
			for idx, rect in getattr(self, 'move_click_rects', {}).items():
				if rect.collidepoint(pos):
					self.view_index, self.is_user_scrolling = idx + 1, False
					if hasattr(self, 'play_sound'): self.play_sound('move')
					return
			return 

		is_live = (self.view_index == len(self.history) - 1)

		# 4. Game Over Overlay Interaction
		if is_live and getattr(self, 'game_over', False):
			if hasattr(self, 'btn_rematch') and getattr(self, 'btn_rematch').collidepoint(pos):
				if hasattr(self, 'play_sound'): self.play_sound('move')
				self.reset_game_state()
				return
			if hasattr(self, 'btn_menu_go') and getattr(self, 'btn_menu_go').collidepoint(pos):
				if hasattr(self, 'play_sound'): self.play_sound('move')
				self.state = 'menu'
				return
			
			# Logic for the new Save Button
			if hasattr(self, 'btn_save') and getattr(self, 'btn_save').collidepoint(pos):
				if not getattr(self, 'game_saved', False):
					if hasattr(self, 'play_sound'): self.play_sound('notify')
					
					# Determine player identities based on game_mode
					w_player, b_player = "Human", "Human"
					if self.game_mode == 'white_ai':
						w_player, b_player = "AI (Stage 5)", "Human"
					elif self.game_mode == 'black_ai':
						w_player, b_player = "Human", "AI (Stage 5)"
					elif self.game_mode == 'rl_training':
						w_player, b_player = "AI (RL)", "AI (RL)"
						
					winner_str = "Draw"
					if self.winner == 'w': winner_str = "White"
					elif self.winner == 'b': winner_str = "Black"
					
					SaveManager.save_game(
						move_history=self.move_log,
						replay_actions=getattr(self, 'replay_actions', []), # PASSED TO SAVER
						game_mode=self.game_mode,
						white_player=w_player,
						black_player=b_player,
						winner=winner_str
					)
					self.game_saved = True
				return
				
			return # Block physical board clicks if game over overlay is up

		# 5. Board Interaction
		if not is_live or getattr(self, 'waiting_for_ai', False): return

		r, c = self.get_board_pos(pos[0], pos[1])
		if r == -1: return

		if self.phase == 'move_piece':
			piece = self.board[r][c]
			if piece and piece.color == self.turn:
				self.dragging, self.drag_piece, self.drag_start = True, piece, (r, c)
				px, py = self.get_screen_pos(r, c)
				self.drag_offset = (pos[0] - px, pos[1] - py)
				self.selected_square, self.valid_moves = (r, c), self.get_piece_legal_moves(r, c)
			elif getattr(self, 'selected_square', None) and (r, c) in getattr(self, 'valid_moves', []):
				self.execute_move(self.selected_square, (r, c))
				self.selected_square, self.valid_moves = None, []
			else:
				self.selected_square, self.valid_moves = None, []
				
		elif self.phase == 'move_duck':
			if (r, c) == self.duck_pos:
				self.dragging, self.drag_piece, self.drag_start = True, 'duck', (r, c)
				px, py = self.get_screen_pos(r, c)
				self.drag_offset = (pos[0] - px, pos[1] - py)
			elif not self.board[r][c] and (r, c) != getattr(self, 'prev_duck_pos', (-1,-1)):
				self.place_duck((r, c))

	def handle_mouse_up(self, pos):
		"""Handles releasing a piece. Fixed to preserve selection on simple click."""
		self.history_dragging = False
		if not getattr(self, 'dragging', False): return
		
		r, c = self.get_board_pos(pos[0], pos[1])
		if r != -1:
			if self.phase == 'move_piece' and self.drag_piece != 'duck':
				if (r, c) in getattr(self, 'valid_moves', []) and (r, c) != self.drag_start:
					self.execute_move(self.drag_start, (r, c), animated=False)
					self.selected_square, self.valid_moves = None, []
				elif (r, c) != self.drag_start:
					self.selected_square, self.valid_moves = None, []
					
			elif self.phase == 'move_duck' and self.drag_piece == 'duck':
				if (r, c) != self.drag_start and not self.board[r][c] and (r, c) != getattr(self, 'prev_duck_pos', (-1,-1)):
					self.place_duck((r, c), animated=False)

		self.dragging, self.drag_piece, self.drag_start = False, None, None

	def handle_mouse_motion(self, pos):
		"""Handles history panel scroll dragging."""
		if getattr(self, 'history_dragging', False):
			dy = pos[1] - getattr(self, 'last_mouse_y', pos[1])
			if abs(dy) >= 24:
				self.history_scroll_offset = getattr(self, 'history_scroll_offset', 0) - (dy // 24)
				self.last_mouse_y = pos[1]

	def handle_mouse_wheel(self, y):
		"""Handles mouse wheel scrolling on the history panel."""
		mx, my = pygame.mouse.get_pos()
		if pygame.Rect(self.screen_w - self.panel_width, 0, self.panel_width, self.screen_h).collidepoint((mx, my)):
			self.is_user_scrolling = True
			self.history_scroll_offset = getattr(self, 'history_scroll_offset', 0) - y

	def handle_keyboard(self, event):
		"""Handles keyboard inputs (Arrow keys for navigation)."""
		if event.key == pygame.K_LEFT: self.view_index, self.is_user_scrolling = max(0, self.view_index - 1), False
		elif event.key == pygame.K_RIGHT: self.view_index, self.is_user_scrolling = min(len(self.history) - 1, self.view_index + 1), False