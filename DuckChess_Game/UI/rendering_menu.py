import pygame
import os
from DuckChess_Game.UI.settings import *

class MenuRenderingMixin:
	"""Handles rendering of the polished, minimal main menu and adaptive rules screen."""

	def draw_menu_background(self):
		"""Draws a subtle, dark checkered background."""
		cols, rows = self.screen_w // MENU_TILE_SIZE + 1, self.screen_h // MENU_TILE_SIZE + 1
		for r in range(rows):
			for c in range(cols):
				color = MENU_BG_DARK if (r + c) % 2 == 0 else MENU_BG_LIGHT
				pygame.draw.rect(self.screen, color, (c * MENU_TILE_SIZE, r * MENU_TILE_SIZE, MENU_TILE_SIZE, MENU_TILE_SIZE))

	def draw_glass_panel(self, rect):
		"""Draws a refined frosted glass panel with a thin elegant border."""
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
		"""Renders the main menu."""
		self.draw_menu_background()

		# Main Container Panel
		panel_w, panel_h = 450, 560
		panel_y = (self.screen_h - panel_h) // 2 + 40
		panel = pygame.Rect((self.screen_w - panel_w) // 2, panel_y, panel_w, panel_h)
		self.draw_glass_panel(panel)

		# Centered Title
		title_y = panel.top - 80 
		t_main = FONT_MENU_TITLE.render("DUCK CHESS", True, MENU_ACCENT)
		title_rect = t_main.get_rect(center=(self.screen_w // 2, title_y))
		
		shadow_surf = FONT_MENU_TITLE.render("DUCK CHESS", True, (0, 0, 0, 120))
		self.screen.blit(shadow_surf, shadow_surf.get_rect(center=(title_rect.centerx + 3, title_rect.centery + 3)))
		self.screen.blit(t_main, title_rect)

		# Buttons inside the panel
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

	def draw_rules(self):
		"""Renders the rule explanation screen dynamically with word-wrap."""
		self.draw_menu_background()
		
		# 1. Load Rules dynamically from file
		rules_path = get_asset_path("rules.txt")
		current_mtime = 0
		if os.path.exists(rules_path):
			current_mtime = os.path.getmtime(rules_path)

		if not hasattr(self, '_rules_cache') or getattr(self, '_rules_mtime', 0) != current_mtime:
			self._rules_mtime = current_mtime
			if os.path.exists(rules_path):
				with open(rules_path, 'r', encoding='utf-8') as f:
					self._rules_cache = [line.strip() for line in f.readlines() if line.strip()]
			else:
				# Default rules
				self._rules_cache = [
					"1. The Ultimate Goal: The objective is to physically capture the opponent's King.",
					"2. No Checks or Checkmates: The concept of check does not exist. You can legally move your King into an attacked square or ignore an attack on your King.",
					"3. The Two-Step Turn: Every turn consists of two mandatory actions: first, make a standard chess move, and second, move the Duck.",
					"4. Mandatory Duck Relocation: The Duck must be moved every single turn. It cannot remain on its current square, and it must be placed on an empty square.",
					"5. The Indestructible Blocker: The Duck acts as a solid obstacle. Pieces cannot capture the Duck, move onto its square, or slide through it.",
					"6. Knights Leap: Because Knights jump over squares, they are the only pieces that can bypass the Duck's blocking effect.",
					"7. Castling Freedom: Since there is no check, you are allowed to castle even if your King is currently attacked.",
					"8. Fowling (Stalemate Win): If a player has absolutely no legal moves available, they are fowled and immediately win the game."
				]
				try:
					os.makedirs(os.path.dirname(rules_path), exist_ok=True)
					with open(rules_path, 'w', encoding='utf-8') as f:
						f.write("\n\n".join(self._rules_cache))
				except Exception as e:
					print(f"Failed to create rules.txt: {e}")

		# 2. Define Adaptive Boundaries
		panel_w = min(self.screen_w - 60, 950)
		text_max_width = panel_w - 100
		
		paragraph_spacing = 15
		line_height = 28
		rendered_paragraphs = []
		total_text_height = 0

		# 3. Dynamic Word-Wrap Logic
		for paragraph in self._rules_cache:
			words = paragraph.split(' ')
			lines = []
			current_line = []
			for word in words:
				test_line = ' '.join(current_line + [word]) if current_line else word
				if FONT_MENU_SUB.size(test_line)[0] <= text_max_width:
					current_line.append(word)
				else:
					if current_line:
						lines.append(' '.join(current_line))
					current_line = [word]
			if current_line:
				lines.append(' '.join(current_line))
			
			rendered_paragraphs.append(lines)
			total_text_height += len(lines) * line_height + paragraph_spacing

		# 4. Calculate heights and draw UI
		panel_h = min(self.screen_h - 40, 160 + total_text_height + 80)
		panel_y = (self.screen_h - panel_h) // 2
		panel = pygame.Rect((self.screen_w - panel_w) // 2, panel_y, panel_w, panel_h)

		self.draw_glass_panel(panel)
		
		title_surf = FONT_LARGE.render("How to Play Duck Chess", True, MENU_ACCENT)
		self.screen.blit(title_surf, title_surf.get_rect(center=(self.screen_w // 2, panel.top + 50)))

		# 5. Render wrapped text
		current_y = panel.top + 120
		for lines in rendered_paragraphs:
			for line in lines:
				if current_y + line_height > panel.bottom - 70:
					break # Prevent text from bleeding over the back button on very small screens
				txt_surf = FONT_MENU_SUB.render(line, True, TEXT_COLOR)
				self.screen.blit(txt_surf, (panel.left + 50, current_y))
				current_y += line_height
			current_y += paragraph_spacing

		# 6. Draw Back Button
		mouse = pygame.mouse.get_pos()
		self.rules_back_btn = pygame.Rect(0, 0, 200, 50)
		self.rules_back_btn.center = (self.screen_w // 2, panel.bottom - 45)
		self.draw_styled_button(self.rules_back_btn, "Back to Menu", self.rules_back_btn.collidepoint(mouse))

	def get_promotion_rects(self):
		"""Calculates coordinates for the pawn promotion menu."""
		if not getattr(self, 'promotion_coords', None): return []
		r, c = self.promotion_coords
		bx, by = self.get_screen_pos(r, c)
		opts = [QUEEN, ROOK, BISHOP, KNIGHT]
		sq = self.sq_size
		start_y = max(self.board_y, min(by + (sq - sq * len(opts)) // 2, self.board_y + sq * 8 - sq * len(opts)))
		return [(pygame.Rect(bx, start_y + i * sq, sq, sq), p) for i, p in enumerate(opts)]

	def draw_promotion_ui(self):
		"""Renders the promotion selection overlay."""
		rects = self.get_promotion_rects()
		if not rects: return
		container = rects[0][0].unionall([r[0] for r in rects])
		pygame.draw.rect(self.screen, (30, 33, 40), container, border_radius=4)
		pygame.draw.rect(self.screen, MENU_ACCENT, container, width=2, border_radius=4)

		m = pygame.mouse.get_pos()
		for r, p in rects:
			if r.collidepoint(m): pygame.draw.rect(self.screen, (60, 65, 75), r)
			k = f"{self.turn}{p}"
			if k in self.scaled_images: self.screen.blit(self.scaled_images[k], r)