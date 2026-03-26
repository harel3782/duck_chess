import pygame
import sys
import copy
import asyncio
from DuckChess_Game.UI.settings import *
from DuckChess_Game.Logic.logic import GameLogicMixin
from DuckChess_Game.UI.rendering import RenderingMixin
from DuckChess_Game.UI.input_handler import InputHandlerMixin

class DuckChess(GameLogicMixin, RenderingMixin, InputHandlerMixin):
	"""The main application class, orchestrating Logic, Rendering, and Input handling."""
	
	def __init__(self):
		pygame.init()
		self.screen = pygame.display.set_mode((DEFAULT_WIDTH, DEFAULT_HEIGHT), pygame.RESIZABLE)
		pygame.display.set_caption("Duck Chess")
		self.clock = pygame.time.Clock()

		self.game_mode = None
		self.player_side = 'w'
		self.state = 'menu'

		self.init_ai()

		# Layout configuration
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

		self.dragging = False
		self.drag_piece = None
		self.drag_start = None
		self.drag_offset = (0, 0)

		self.promotion_pending = False
		self.promotion_coords = None

		self.target_eval_score = 0
		self.current_eval_score = 0.0

		self.resize_layout(DEFAULT_WIDTH, DEFAULT_HEIGHT)
		self.reset_game_state()

	def save_snapshot(self):
		"""Saves a single point in history [cite: 76-77]."""
		self.history.append({
			'board': copy.deepcopy(self.board),
			'duck_pos': self.duck_pos,
			'prev_duck': self.prev_duck_pos,
			'last_move': self.last_move_arrow,
			'captured': copy.deepcopy(getattr(self, 'captured', {'w': [], 'b': []})),
			'log': list(self.move_log)
		})
		self.view_index = len(self.history) - 1

	def reset_game_state(self):
		"""Completely resets the game environment [cite: 77-81]."""
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

	async def run(self):
		"""The core application loop [cite: 110-117]."""
		while True:
			# Delegate input handling to InputHandlerMixin
			self.process_events(pygame.event.get())

			# Delegate drawing to RenderingMixin and Logic
			if self.state == 'menu':
				self.draw_menu()
			elif self.state == 'edit':
				self.draw_editor()
			else:
				self.ai_turn()
				self.draw_game()

			pygame.display.flip()
			self.clock.tick(FPS)
			await asyncio.sleep(0)

if __name__ == "__main__":
	asyncio.run(DuckChess().run())