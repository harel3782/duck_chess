import pygame
import sys
from DuckChess_Game.UI.input_menu import MenuInputMixin
from DuckChess_Game.UI.input_game import GameInputMixin
from DuckChess_Game.UI.input_editor import EditorInputMixin

class InputHandlerMixin(MenuInputMixin, GameInputMixin, EditorInputMixin):
	"""Aggregates all user input modules and provides the main event loop interface."""

	def process_events(self, events):
		"""The single entry point for all pygame events."""
		for event in events:
			if event.type == pygame.QUIT:
				pygame.quit()
				sys.exit()

			if event.type == pygame.VIDEORESIZE:
				self.resize_layout(event.w, event.h)

			if self.state == 'menu':
				if event.type == pygame.MOUSEBUTTONDOWN:
					self.handle_menu_click(event.pos)
					
			elif self.state == 'edit':
				self.handle_editor_input(event)
				
			elif self.state == 'game':
				if event.type == pygame.MOUSEBUTTONDOWN:
					if getattr(self, 'promotion_pending', False):
						self.handle_promotion_click(event.pos)
					else:
						self.handle_mouse_down(event.pos)
				elif event.type == pygame.MOUSEBUTTONUP:
					self.handle_mouse_up(event.pos)
				elif event.type == pygame.MOUSEMOTION:
					self.handle_mouse_motion(event.pos)
				elif event.type == pygame.MOUSEWHEEL:
					self.handle_mouse_wheel(event.y)
				elif event.type == pygame.KEYDOWN:
					self.handle_keyboard(event)