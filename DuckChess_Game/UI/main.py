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
		self.state = 'menu'

		self.init_ai()

		self.sq_size = 0
		self.board_x = 0
		self.board_y = 0
		self.ui_height = 60
		self.panel_width = 300
		self.eval_bar_width = 30
		self.eval_bar_x = 0
		self.side_margin = 20

		self.nav_btns = {k: pygame.Rect(0, 0, 0, 0) for k in ['start', 'prev', 'next', 'end']}
		self.menu_btn_rect = pygame.Rect(0, 0, 0, 0)
		self.flip_btn_rect = pygame.Rect(0, 0, 0, 0)
		self.restart_btn_rect = pygame.Rect(0, 0, 0, 0)
		self.show_eval = False
		self.eval_btn_rect = pygame.Rect(0, 0, 0, 0)

		self.editor_play_btn = pygame.Rect(0, 0, 0, 0)
		self.editor_clear_btn = pygame.Rect(0, 0, 0, 0)
		self.editor_menu_btn = pygame.Rect(0, 0, 0, 0)
		self.editor_turn_btn = pygame.Rect(0, 0, 0, 0)

		self.original_images = {}
		self.scaled_images = {}
		self.sounds = {}
		self.load_assets()

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

	def resize_layout(self, w, h):
		self.screen_w = w
		self.screen_h = h
		
		h = max(h, self.ui_height + 300)
		w = max(w, self.panel_width + self.eval_bar_width + 100)

		total_board_h = h - self.ui_height - self.side_margin * 2
		available_board_w = w - self.panel_width - self.eval_bar_width - self.side_margin * 4
		
		self.sq_size = min(total_board_h, available_board_w) // 8
		if self.sq_size <= 0: self.sq_size = 1

		board_w = self.sq_size * 8
		
		available_w = w - self.panel_width - self.eval_bar_width
		self.board_x = self.eval_bar_width + self.side_margin + (available_w - board_w) // 2
		self.board_y = self.side_margin
		
		self.eval_bar_x = self.side_margin + 5

		self.font_large = pygame.font.SysFont("Segoe UI Symbol", int(self.sq_size * 0.8), bold=True)
		self.font_ui = pygame.font.SysFont("Verdana", 14)
		self.font_history = pygame.font.SysFont("Consolas", 14)
		self.font_nav = pygame.font.SysFont("Arial", 20, bold=True)
		self.font_menu_title = pygame.font.SysFont("Verdana", 60, bold=True)
		self.font_menu_sub = pygame.font.SysFont("Verdana", 16, bold=True)
		self.font_eval = pygame.font.SysFont("Arial", 16, bold=True)
		self.font_status = pygame.font.SysFont("Verdana", 18, bold=True)

		self.scaled_images = {}
		for key, img in self.original_images.items():
			sz = int(self.sq_size * 0.8) if key == 'duck' else self.sq_size
			self.scaled_images[key] = pygame.transform.smoothscale(img, (sz, sz))

		px, by = w - self.panel_width, h - 60
		bw, bh = self.panel_width // 4 - 8, 35

		self.nav_btns['start'] = pygame.Rect(px + 10, by, bw, bh)
		self.nav_btns['prev'] = pygame.Rect(px + 10 + bw + 5, by, bw, bh)
		self.nav_btns['next'] = pygame.Rect(px + 10 + (bw + 5) * 2, by, bw, bh)
		self.nav_btns['end'] = pygame.Rect(px + 10 + (bw + 5) * 3, by, bw, bh)

	async def run(self):
		while True:
			for event in pygame.event.get():
				if event.type == pygame.QUIT:
					pygame.quit()
					sys.exit()

				if event.type == pygame.VIDEORESIZE:
					self.resize_layout(event.w, event.h)

				if self.state == 'menu':
					if event.type == pygame.MOUSEBUTTONDOWN:
						self.handle_menu_click(event.pos)

				elif self.state == 'load_replay':
					if event.type == pygame.MOUSEBUTTONDOWN:
						self.handle_load_replay_click(event.pos)

				elif self.state == 'edit':
					self.handle_editor_input(event)

				elif self.state == 'game':
					if event.type == pygame.MOUSEBUTTONDOWN:
						# Handling Promotion clicks
						if self.promotion_pending:
							for rect, p_type in self.get_promotion_rects():
								if rect.collidepoint(event.pos):
									self.promote_pawn(p_type)
									break
						else:
							self.handle_mouse_down(event.pos)

					elif event.type == pygame.MOUSEBUTTONUP:
						self.handle_mouse_up(event.pos)

					elif event.type == pygame.KEYDOWN:
						self.handle_keyboard(event)

			if self.state == 'menu':
				self.draw_menu()
			elif self.state == 'load_replay':
				self.draw_load_replay()
			elif self.state == 'edit':
				self.draw_editor()
			else:
				if hasattr(self, 'ai_turn'): self.ai_turn()
				self.draw_game()

			pygame.display.flip()
			self.clock.tick(FPS)
			await asyncio.sleep(0)
			for event in pygame.event.get():
				if event.type == pygame.QUIT:
					pygame.quit()
					sys.exit()

				if event.type == pygame.VIDEORESIZE:
					self.resize_layout(event.w, event.h)

				if self.state == 'menu':
					if event.type == pygame.MOUSEBUTTONDOWN:
						self.handle_menu_click(event.pos)

				elif self.state == 'load_replay':
					if event.type == pygame.MOUSEBUTTONDOWN:
						self.handle_load_replay_click(event.pos)

				elif self.state == 'edit':
					self.handle_editor_input(event)

				elif self.state == 'game':
					if event.type == pygame.MOUSEBUTTONDOWN:
						self.handle_mouse_down(event.pos)

					elif event.type == pygame.MOUSEBUTTONUP:
						self.handle_mouse_up(event.pos)

					elif event.type == pygame.KEYDOWN:
						self.handle_keyboard(event)

			if self.state == 'menu':
				self.draw_menu()
			elif self.state == 'load_replay':
				self.draw_load_replay()
			elif self.state == 'edit':
				self.draw_editor()
			else:
				if hasattr(self, 'ai_turn'): self.ai_turn()
				self.draw_game()

			pygame.display.flip()
			self.clock.tick(FPS)
			await asyncio.sleep(0)

			
	def load_replay_file(self, filepath):
		"""Loads a .pkl replay file and reconstructs history."""
		try:
			import pickle
			with open(filepath, 'rb') as f:
				game_data = pickle.load(f)
		except Exception as e:
			print(f"Failed to load replay: {e}")
			return

		actions = game_data.get('action_history', [])
		if not actions:
			print("No action history found.")
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
			self.save_snapshot()

		self.view_index = len(self.history) - 1

if __name__ == "__main__":
	asyncio.run(DuckChess().run())