import pygame
from DuckChess_Game.UI.settings import *

class MenuRenderingMixin:
	"""Handles rendering of main menus, universal panels, and promotion overlays."""

	def draw_menu_background(self):
		"""Draws the checkered background for the menu screens."""
		tile_size = 100
		cols, rows = self.screen_w // tile_size + 1, self.screen_h // tile_size + 1
		for r in range(rows):
			for c in range(cols):
				color = MENU_BG_DARK if (r + c) % 2 == 0 else MENU_BG_LIGHT
				pygame.draw.rect(self.screen, color, (c * tile_size, r * tile_size, tile_size, tile_size))

	def draw_glass_panel(self, rect):
		"""Draws a semi-transparent panel with a border."""
		s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
		s.fill((20, 25, 30, 230))
		self.screen.blit(s, rect.topleft)
		pygame.draw.rect(self.screen, BTN_BORDER, rect, width=1, border_radius=8)

	def draw_styled_button(self, rect, text, hover, font=None):
		"""Universal stylized button renderer."""
		if font is None: font = self.font_menu_sub
		color = BTN_HOVER if hover else BTN_NORMAL
		border_col = MENU_ACCENT if hover else BTN_BORDER

		shadow_rect = rect.copy()
		shadow_rect.y += 2
		pygame.draw.rect(self.screen, (0, 0, 0, 100), shadow_rect, border_radius=6)
		pygame.draw.rect(self.screen, color, rect, border_radius=6)
		pygame.draw.rect(self.screen, border_col, rect, width=1, border_radius=6)

		txt_col = MENU_ACCENT if hover else BTN_TEXT
		txt_surf = font.render(text, True, txt_col)
		self.screen.blit(txt_surf, txt_surf.get_rect(center=rect.center))

	def draw_menu(self):
		"""Renders the main menu layout and saves button rects for the input handler."""
		self.draw_menu_background()

		t_shadow = self.font_menu_title.render("DUCK CHESS", True, (0, 0, 0))
		self.screen.blit(t_shadow, t_shadow.get_rect(center=(self.screen_w // 2 + 3, self.screen_h * 0.2 + 3)))
		t_main = self.font_menu_title.render("DUCK CHESS", True, MENU_ACCENT)
		self.screen.blit(t_main, t_main.get_rect(center=(self.screen_w // 2, self.screen_h * 0.2)))

		panel = pygame.Rect((self.screen_w - 400) // 2, (self.screen_h - 400) // 2 + 40, 400, 400)
		self.draw_glass_panel(panel)

		opts = [
			("Play as White", 'white'), 
			("Play as Black", 'black'), 
			("2 Player (PvP)", 'pvp'), 
			("Edit Board", 'edit'), 
			("Load Replay", 'replay')
		]
		mouse = pygame.mouse.get_pos()

		# Initialize the dictionary so input_handler can use it
		if not hasattr(self, 'menu_rects'):
			self.menu_rects = {}

		for i, (txt, key) in enumerate(opts):
			r = pygame.Rect(0, 0, 300, 50)
			r.centerx, r.top = self.screen_w // 2, panel.top + 30 + i * 70
			self.menu_rects[key] = r  # Save rect for input_handler
			self.draw_styled_button(r, txt, r.collidepoint(mouse))

	def get_promotion_rects(self):
		"""Calculates coordinates for the pawn promotion menu."""
		if not getattr(self, 'promotion_coords', None): return []
		r, c = self.promotion_coords
		bx, by = self.get_screen_pos(r, c)
		opts = [QUEEN, ROOK, BISHOP, KNIGHT]
		start_y = max(self.board_y, min(by + (self.sq_size - self.sq_size * len(opts)) // 2, self.board_y + self.sq_size * 8 - self.sq_size * len(opts)))
		return [(pygame.Rect(bx, start_y + i * self.sq_size, self.sq_size, self.sq_size), p) for i, p in enumerate(opts)]

	def draw_promotion_ui(self):
		"""Draws the piece selection box for pawn promotion."""
		rects = self.get_promotion_rects()
		if not rects: return
		container = rects[0][0].unionall([r[0] for r in rects])
		pygame.draw.rect(self.screen, EVAL_WHITE, container)
		pygame.draw.rect(self.screen, BTN_BORDER, container, width=2)

		m = pygame.mouse.get_pos()
		for r, p in rects:
			if r.collidepoint(m): pygame.draw.rect(self.screen, HIGHLIGHT, r)
			k = f"{self.turn}{p}"
			if k in self.scaled_images: self.screen.blit(self.scaled_images[k], r)