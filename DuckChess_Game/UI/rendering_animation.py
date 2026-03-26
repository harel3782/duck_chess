import pygame
import math
from DuckChess_Game.UI.settings import *

class AnimationRenderingMixin:
	"""Handles smooth visual transitions and piece movements."""

	def animate_move_visual(self, start, end, piece, is_duck=False):
		"""Draws the sliding animation between squares [cite: 173-176]."""
		if self.view_index != len(self.history) - 1: return

		x1, y1 = self.get_screen_pos(start[0], start[1])
		x2, y2 = self.get_screen_pos(end[0], end[1])

		key = 'duck' if is_duck else f"{piece.color}{piece.type}"
		img = self.scaled_images.get(key)
		if not img and not is_duck: return

		start_time = pygame.time.get_ticks()
		clock = pygame.time.Clock()

		while True:
			elapsed = pygame.time.get_ticks() - start_time
			if elapsed >= ANIMATION_SPEED: break

			progress = 1 - math.pow(1 - (elapsed / ANIMATION_SPEED), 3) # Ease-out curve
			current_x = x1 + (x2 - x1) * progress
			current_y = y1 + (y2 - y1) * progress

			self.draw_game(hidden_square=start)
			if img: self.screen.blit(img, (current_x, current_y))
			
			pygame.display.flip()
			clock.tick(ANIMATION_FPS)