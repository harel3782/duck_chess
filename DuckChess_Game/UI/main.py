import pygame
import sys
import copy
import asyncio
from DuckChess_Game.UI.settings import *
from DuckChess_Game.Logic.logic import GameLogicMixin
from DuckChess_Game.Logic.rl_mixin import RLMixin
from DuckChess_Game.UI.rendering import RenderingMixin
from DuckChess_Game.UI.input_handler import InputHandlerMixin
from DuckChess_Game.UI.pieces import Piece

class DuckChess(GameLogicMixin, RLMixin, RenderingMixin, InputHandlerMixin):
	def __init__(self):
		pygame.init()
		self.screen = pygame.display.set_mode((DEFAULT_WIDTH, DEFAULT_HEIGHT), pygame.RESIZABLE)
		pygame.display.set_caption("Duck Chess")
		self.clock = pygame.time.Clock()

		self.game_mode = None
		self.player_side = 'w'
		self.state = 'menu'  # Start in Menu

		# Initialize AI
		self.init_ai()

		# Layout
		self.sq_size = 0
		self.board_x = 0
		self.board_y = 0
		self.ui_height = 60
		self.panel_width = 300
		self.eval_bar_width = 36
		self.side_margin = 20

		# Buttons
		self.nav_btns = {k: pygame.Rect(0, 0, 0, 0) for k in ['start', 'prev', 'next', 'end']}
		self.menu_btn_rect = pygame.Rect(0, 0, 0, 0)
		self.flip_btn_rect = pygame.Rect(0, 0, 0, 0)
		self.restart_btn_rect = pygame.Rect(0, 0, 0, 0)
		self.show_eval = True
		self.eval_btn_rect = pygame.Rect(0, 0, 0, 0)

		# Editor Buttons
		self.editor_play_btn = pygame.Rect(0, 0, 0, 0)
		self.editor_clear_btn = pygame.Rect(0, 0, 0, 0)
		self.editor_menu_btn = pygame.Rect(0, 0, 0, 0)
		self.editor_turn_btn = pygame.Rect(0, 0, 0, 0)

		# Assets
		self.original_images = {}
		self.scaled_images = {}
		self.sounds = {}
		self.load_assets()

		# State Variables
		self.move_log = []
		self.current_move_str = ""
		self.turn_number = 1
		self.history = []
		self.view_index = -1

		# Drag & Drop State
		self.dragging = False
		self.drag_piece = None
		self.drag_start = None
		self.drag_offset = (0, 0)

		# Promotion
		self.promotion_pending = False
		self.promotion_coords = None

		self.target_eval_score = 0
		self.current_eval_score = 0.0

		self.resize_layout(DEFAULT_WIDTH, DEFAULT_HEIGHT)
		self.reset_game_state()

	def save_snapshot(self):
		"""Saves the current board state for the history viewer."""
		self.history.append({
			'board': copy.deepcopy(self.board),
			'duck_pos': self.duck_pos,
			'prev_duck': self.prev_duck_pos,
			'last_move': self.last_move_arrow,
			'captured': copy.deepcopy(self.captured),
			'log': list(self.move_log)
		})
		self.view_index = len(self.history) - 1

	def reset_game_state(self):
		"""Resets all variables to start a fresh game."""
		self.duck_pos = (-1, -1)
		self.prev_duck_pos = (-1, -1)
		self.turn = 'w'
		self.phase = 'move_piece'
		self.selected_square = None
		self.valid_moves = []
		self.game_over = False
		self.winner = None
		self.en_passant_target = None
		self.half_move_clock = 0
		self.rep_history = {}

		self.move_log = []
		self.last_move_arrow = None
		self.turn_number = 1
		self.current_move_str = ""
		self.history = []
		self.view_index = -1

		self.captured = {'w': [], 'b': []}
		self.promotion_pending = False
		self.target_eval_score = 0
		self.current_eval_score = 0.0

		self.board = [[None] * 8 for _ in range(8)]
		self.init_board()

		if self.game_mode == 'black_ai':
			self.waiting_for_ai = True
			self.ai_wait_start = pygame.time.get_ticks()
		else:
			self.waiting_for_ai = False

		self.save_snapshot()

	# --- ASYNC MAIN LOOP ---
	async def run(self):
		while True:
			# 1. EVENT HANDLING
			for event in pygame.event.get():
				if event.type == pygame.QUIT:
					pygame.quit()
					sys.exit()

				if event.type == pygame.VIDEORESIZE:
					self.resize_layout(event.w, event.h)

				if self.state == 'menu':
					pass

				elif self.state == 'edit':
					self.handle_editor_input(event)

				elif self.state == 'game':
					if event.type == pygame.MOUSEBUTTONDOWN:
						if self.promotion_pending:
							for rect, p_type in self.get_promotion_rects():
								if rect.collidepoint(event.pos):
									self.promote_pawn(p_type)
						else:
							self.handle_mouse_down(event.pos)

					elif event.type == pygame.MOUSEBUTTONUP:
						self.handle_mouse_up(event.pos)

					elif event.type == pygame.KEYDOWN:
						self.handle_keyboard(event)

			# 2. DRAWING & LOGIC
			if self.state == 'menu':
				self.draw_menu()

			elif self.state == 'edit':
				self.draw_editor()

			else:  # Game Mode
				self.ai_turn()
				self.draw_game()

			# 3. REFRESH
			pygame.display.flip()
			self.clock.tick(FPS)
			await asyncio.sleep(0)

if __name__ == "__main__":
	asyncio.run(DuckChess().run())