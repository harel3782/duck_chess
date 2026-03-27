import pygame
from DuckChess_Game.UI.settings import *

class MenuRenderingMixin:
	"""Handles rendering of the polished, minimal main menu."""

	def draw_menu_background(self):
		"""Draws a subtle, dark checkered background."""
		cols, rows = self.screen_w // MENU_TILE_SIZE + 1, self.screen_h // MENU_TILE_SIZE + 1
		for r in range(rows):
			for c in range(cols):
				color = MENU_BG_DARK if (r + c) % 2 == 0 else MENU_BG_LIGHT
				pygame.draw.rect(self.screen, color, (c * MENU_TILE_SIZE, r * MENU_TILE_SIZE, MENU_TILE_SIZE, MENU_TILE_SIZE))

	def draw_menu_glass_panel(self, rect):
		"""Draws a refined frosted glass panel specifically for menu screens."""
		glass = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
		glass.fill((30, 33, 38, 220)) 
		self.screen.blit(glass, rect.topleft)
		
		pygame.draw.rect(self.screen, (100, 110, 125), rect, width=1, border_radius=15)
		shadow_rect = rect.inflate(4, 4)
		pygame.draw.rect(self.screen, (0, 0, 0, 50), shadow_rect, width=1, border_radius=17)

	def draw_styled_button(self, rect, text, hover, font=None):
		"""Renders a clean, flat button with an accent hover state."""
		if font is None: font = FONT_MENU_SUB
		
		base_color = (60, 68, 80) if not hover else (80, 95, 115)
		pygame.draw.rect(self.screen, base_color, rect, border_radius=10)
		
		border_color = MENU_ACCENT if hover else (120, 135, 150)
		pygame.draw.rect(self.screen, border_color, rect, width=2, border_radius=10)

		txt_color = (255, 255, 255) if not hover else MENU_ACCENT
		txt_surf = font.render(text, True, txt_color)
		self.screen.blit(txt_surf, txt_surf.get_rect(center=rect.center))

	def draw_menu(self):
		"""Renders the main menu layout and buttons."""
		self.draw_menu_background()

		panel_w, panel_h = 450, 560
		panel_y = (self.screen_h - panel_h) // 2 + 40
		panel = pygame.Rect((self.screen_w - panel_w) // 2, panel_y, panel_w, panel_h)
		self.draw_menu_glass_panel(panel)

		title_y = panel.top - 80 
		t_main = FONT_MENU_TITLE.render("DUCK CHESS", True, MENU_ACCENT)
		title_rect = t_main.get_rect(center=(self.screen_w // 2, title_y))
		
		shadow_surf = FONT_MENU_TITLE.render("DUCK CHESS", True, (0, 0, 0, 120))
		self.screen.blit(shadow_surf, shadow_surf.get_rect(center=(title_rect.centerx + 3, title_rect.centery + 3)))
		self.screen.blit(t_main, title_rect)

		opts = [
			("Play as White", 'white'), 
			("Play as Black", 'black'), 
			("Two Player (PvP)", 'pvp'), 
			("Custom Board Editor", 'edit'), 
			("Load Game Replay", 'replay'),
			("How to Play", 'rules')
		]
		
		if not hasattr(self, 'menu_rects'): self.menu_rects = {}
		mouse = pygame.mouse.get_pos()

		for i, (txt, key) in enumerate(opts):
			r = pygame.Rect(0, 0, 360, 60)
			r.centerx, r.top = self.screen_w // 2, panel.top + 35 + i * 78
			self.menu_rects[key] = r
			self.draw_styled_button(r, txt, r.collidepoint(mouse))

		footer = FONT_UI.render("Master the Duck, Master the Game", True, (150, 160, 180))
		self.screen.blit(footer, footer.get_rect(center=(self.screen_w // 2, panel.bottom + 30)))