import pygame
import os
from DuckChess_Game.UI.settings import *

class RulesRenderingMixin:
	"""Handles rendering of the adaptive rules explanation screen."""

	def draw_rules(self):
		"""Renders the rule explanation screen dynamically with word-wrap."""
		self.draw_menu_background()
		
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

		panel_w = min(self.screen_w - 60, 950)
		text_max_width = panel_w - 100
		
		paragraph_spacing = 15
		line_height = 28
		rendered_paragraphs = []
		total_text_height = 0

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

		panel_h = min(self.screen_h - 40, 160 + total_text_height + 80)
		panel_y = (self.screen_h - panel_h) // 2
		panel = pygame.Rect((self.screen_w - panel_w) // 2, panel_y, panel_w, panel_h)

		self.draw_menu_glass_panel(panel)
		
		title_surf = FONT_LARGE.render("How to Play Duck Chess", True, MENU_ACCENT)
		self.screen.blit(title_surf, title_surf.get_rect(center=(self.screen_w // 2, panel.top + 50)))

		current_y = panel.top + 120
		for lines in rendered_paragraphs:
			for line in lines:
				if current_y + line_height > panel.bottom - 70:
					break 
				txt_surf = FONT_MENU_SUB.render(line, True, TEXT_COLOR)
				self.screen.blit(txt_surf, (panel.left + 50, current_y))
				current_y += line_height
			current_y += paragraph_spacing

		mouse = pygame.mouse.get_pos()
		self.rules_back_btn = pygame.Rect(0, 0, 200, 50)
		self.rules_back_btn.center = (self.screen_w // 2, panel.bottom - 45)
		self.draw_styled_button(self.rules_back_btn, "Back to Menu", self.rules_back_btn.collidepoint(mouse))