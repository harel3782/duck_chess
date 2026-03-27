import pygame
from DuckChess_Game.UI.settings import *
from DuckChess_Game.Logic.constants import *

class PromotionRenderingMixin:
	"""Handles the pawn promotion UI overlay."""

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