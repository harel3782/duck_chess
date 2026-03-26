import pygame
import os
from DuckChess_Game.UI.settings import *

class AssetManagerMixin:
	"""Centralized manager for loading external assets (images, sounds) and audio playback."""

	def load_assets(self):
		"""Locates and loads all images and audio files safely."""
		current_file_dir = os.path.dirname(os.path.abspath(__file__))
		potential_paths = [
			os.path.normpath(os.path.join(current_file_dir, "..", "assets")),
			os.path.normpath(os.path.join(current_file_dir, "assets")),
			os.path.normpath(os.path.join(current_file_dir, "..", "..", "assets")),
			os.path.abspath("assets")
		]

		assets_dir = None
		for path in potential_paths:
			if os.path.exists(path):
				assets_dir = path
				break

		if not assets_dir:
			assets_dir = os.path.normpath(os.path.join(current_file_dir, "..", "assets"))

		pieces_dir = os.path.join(assets_dir, "pieces")
		sounds_dir = os.path.join(assets_dir, "sounds")

		# --- Initialize Sound System ---
		try:
			if not pygame.mixer.get_init():
				pygame.mixer.init()
			self.sounds = {}
		except Exception as e:
			print(f"Sound init failed: {e}")
			self.sounds = {}

		# --- Load Sounds ---
		sound_files = {
			'move': 'move.wav', 'capture': 'capture.wav', 'castle': 'castle.wav',
			'promote': 'promote.wav', 'notify': 'notify.wav', 'game_over': 'game_over.wav'
		}
		if os.path.exists(sounds_dir):
			for name, filename in sound_files.items():
				path = os.path.join(sounds_dir, filename)
				if os.path.exists(path):
					try:
						snd = pygame.mixer.Sound(path)
						snd.set_volume(SOUND_VOLUME)
						self.sounds[name] = snd
					except Exception as e:
						print(f"Failed to load sound {filename}: {e}")

		# --- Load Images ---
		self.original_images = {}
		name_map = {'K': 'king', 'Q': 'queen', 'R': 'rook', 'B': 'bishop', 'N': 'knight', 'P': 'pawn'}
		
		if os.path.exists(pieces_dir):
			for color in ['w', 'b']:
				for p_type, p_name in name_map.items():
					path = os.path.join(pieces_dir, f"{p_name}-{color}.png")
					if os.path.exists(path):
						try:
							self.original_images[f"{color}{p_type}"] = pygame.image.load(path).convert_alpha()
						except: pass
			
			duck_paths = [os.path.join(assets_dir, "duck.png"), os.path.join(pieces_dir, "duck.png")]
			for path in duck_paths:
				if os.path.exists(path):
					try:
						self.original_images['duck'] = pygame.image.load(path).convert_alpha()
						break
					except: pass

	def play_sound(self, sound_name):
		"""Plays a loaded sound effect safely."""
		if hasattr(self, 'sounds') and sound_name in self.sounds:
			try:
				self.sounds[sound_name].play()
			except:
				pass