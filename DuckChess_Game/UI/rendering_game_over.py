import pygame
from DuckChess_Game.UI.settings import *

class GameOverRenderingMixin:
	"""Handles the beautiful, modern Game Over modal overlay."""

	def draw_game_over_ui(self):
		"""Renders a frosted glass modal with the match results and action buttons."""
		is_live = getattr(self, 'view_index', -1) == len(getattr(self, 'history', [])) - 1
		if not getattr(self, 'game_over', False) or not is_live: 
			return

		box_w, box_h = 420, 240
		start_x = self.board_x + (self.sq_size * 8 - box_w) // 2
		start_y = self.board_y + (self.sq_size * 8 - box_h) // 2
		container = pygame.Rect(start_x, start_y, box_w, box_h)

		# 1. Soft Drop Shadow
		shadow = container.copy()
		shadow.y += 8
		pygame.draw.rect(self.screen, (0, 0, 0, 160), shadow, border_radius=20)

		# 2. Frosted Glass Panel
		glass = pygame.Surface((container.width, container.height), pygame.SRCALPHA)
		glass.fill((35, 40, 48, 240))
		self.screen.blit(glass, container.topleft)
		
		# 3. Premium Border
		pygame.draw.rect(self.screen, MENU_ACCENT, container, width=2, border_radius=20)
		inner_border = container.inflate(-4, -4)
		pygame.draw.rect(self.screen, (80, 90, 105, 100), inner_border, width=1, border_radius=18)

		# 4. Winner Text Setup
		if self.winner == 'w':
			title, color = "WHITE WINS!", (250, 250, 250)
		elif self.winner == 'b':
			title, color = "BLACK WINS!", (25, 25, 25)
		else:
			title, color = "DRAW!", (180, 180, 180)

		# 5. Render Text with High-Contrast Outlines
		t_surf = FONT_LARGE.render(title, True, color)
		if self.winner == 'b':
			# Add white outline for black text to pop on dark glass
			ol = FONT_LARGE.render(title, True, (255, 255, 255))
			self.screen.blit(ol, ol.get_rect(center=(container.centerx + 1, container.top + 71)))
			self.screen.blit(ol, ol.get_rect(center=(container.centerx - 1, container.top + 69)))
		
		self.screen.blit(t_surf, t_surf.get_rect(center=(container.centerx, container.top + 70)))

		sub_text = "King Captured or Fowled!" if self.winner != 'draw' else "50-Move Rule"
		sub_surf = FONT_MENU_SUB.render(sub_text, True, (200, 200, 200))
		self.screen.blit(sub_surf, sub_surf.get_rect(center=(container.centerx, container.top + 120)))

		# 6. Render Action Buttons
		mouse = pygame.mouse.get_pos()
		self.btn_rematch = pygame.Rect(container.left + 45, container.bottom - 75, 150, 40)
		self.btn_menu_go = pygame.Rect(container.right - 195, container.bottom - 75, 150, 40)

		if hasattr(self, 'draw_hud_button'):
			self.draw_hud_button(self.btn_rematch, "Rematch", self.btn_rematch.collidepoint(mouse))
			self.draw_hud_button(self.btn_menu_go, "Main Menu", self.btn_menu_go.collidepoint(mouse))