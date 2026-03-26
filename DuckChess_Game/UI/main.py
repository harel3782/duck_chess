import pygame
import sys
import asyncio
from DuckChess_Game.UI.settings import *
from DuckChess_Game.Logic.logic import GameLogicMixin
from DuckChess_Game.UI.rendering import RenderingMixin
from DuckChess_Game.UI.input_handler import InputHandlerMixin
from DuckChess_Game.UI.asset_manager import AssetManagerMixin  # <--- הייבוא החדש

class DuckChess(GameLogicMixin, RenderingMixin, InputHandlerMixin, AssetManagerMixin):
	"""The main application class, orchestrating Logic, Rendering, Input, and Assets."""
	
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
		self.show_eval = False
		self.eval_btn_rect = pygame.Rect(0, 0, 0, 0)
		self.editor_play_btn = pygame.Rect(0, 0, 0, 0)
		self.editor_clear_btn = pygame.Rect(0, 0, 0, 0)
		self.editor_menu_btn = pygame.Rect(0, 0, 0, 0)
		self.editor_turn_btn = pygame.Rect(0, 0, 0, 0)

		# Assets Handled via AssetManagerMixin
		self.load_assets()

		# Drag & Drop State
		self.dragging = False
		self.drag_piece = None
		self.drag_start = None
		self.drag_offset = (0, 0)

		self.resize_layout(DEFAULT_WIDTH, DEFAULT_HEIGHT)
		
		# Initializes State Manager
		self.reset_game_state()

	async def run(self):
		"""The core application loop."""
		while True:
			self.process_events(pygame.event.get())

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