import pygame
import sys

class MenuInputMixin:
	"""Handles user input specifically for the main menu and rules screen."""

	def handle_menu_click(self, pos):
		"""Main Menu interactions."""
		if not hasattr(self, 'menu_rects'): return
		
		for key, rect in self.menu_rects.items():
			if rect.collidepoint(pos):
				if hasattr(self, 'play_sound'): self.play_sound('move')
				
				if key == 'white':
					self.game_mode, self.player_side, self.state = 'white_ai', 'w', 'game'
					self.reset_game_state()
				elif key == 'black':
					self.game_mode, self.player_side, self.state = 'black_ai', 'b', 'game'
					self.reset_game_state()
				elif key == 'pvp':
					self.game_mode, self.player_side, self.state = 'pvp', 'w', 'game'
					self.reset_game_state()
				elif key == 'edit':
					self.clear_board()
					self.init_board()
					self.state = 'edit'
				elif key == 'rules':
					self.state = 'rules'
				elif key == 'replay':
					import tkinter as tk
					from tkinter import filedialog
					root = tk.Tk()
					root.withdraw()
					file_path = filedialog.askopenfilename(
						title="Select Duck Chess Replay",
						filetypes=[("Replay Files", "*.pkl"), ("All Files", "*.*")]
					)
					root.destroy()
					if file_path:
						if hasattr(self, 'play_sound'): self.play_sound('notify')
						self.load_replay_file(file_path)
				elif key == 'quit':
					pygame.quit()
					sys.exit()

	def handle_rules_click(self, pos):
		"""Handles clicks on the Rules screen."""
		if hasattr(self, 'rules_back_btn') and self.rules_back_btn.collidepoint(pos):
			if hasattr(self, 'play_sound'): self.play_sound('move')
			self.state = 'menu'