import pygame
import os
from DuckChess_Game.UI.settings import *

class AssetManagerMixin:
	"""Centralized manager for loading external assets with bulletproof dynamic path finding."""

	def load_assets(self):
		"""Locates and loads all images and audio files safely by searching the project tree."""
		# Start searching from the root of your project
		base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
		
		try:
			if not pygame.mixer.get_init():
				pygame.mixer.init()
			self.sounds = {}
		except Exception as e:
			print(f"Sound init failed: {e}")
			self.sounds = {}

		# 1. Dynamically find the 'pieces' directory
		pieces_dir = None
		for root, dirs, files in os.walk(base_dir):
			# Skip virtual environments to keep search fast
			if '.venv' in root or 'venv' in root or '__pycache__' in root or '.git' in root:
				continue
			# If we see 'pawn-w.png' or 'king-b.png', we found the right folder!
			if 'pawn-w.png' in files or 'king-b.png' in files:
				pieces_dir = root
				break

		self.original_images = {}
		name_map = {'K': 'king', 'Q': 'queen', 'R': 'rook', 'B': 'bishop', 'N': 'knight', 'P': 'pawn'}
		
		if pieces_dir:
			print(f"SUCCESS: Found pieces folder at -> {pieces_dir}")
			for color in ['w', 'b']:
				for p_type, p_name in name_map.items():
					filename = f"{p_name}-{color}.png"
					path = os.path.join(pieces_dir, filename)
					if os.path.exists(path):
						try:
							self.original_images[f"{color}{p_type}"] = pygame.image.load(path).convert_alpha()
						except Exception as e:
							print(f"Error loading {path}: {e}")
		else:
			print(f"ERROR: Could not find the pieces images anywhere in {base_dir}!")

		# 2. Dynamically find the duck image
		duck_path = None
		for root, dirs, files in os.walk(base_dir):
			if '.venv' in root or 'venv' in root or '__pycache__' in root:
				continue
			if 'duck.png' in files:
				duck_path = os.path.join(root, 'duck.png')
				break
		
		if duck_path:
			try:
				self.original_images['duck'] = pygame.image.load(duck_path).convert_alpha()
			except Exception as e:
				print(f"Error loading duck: {e}")
		else:
			print("ERROR: Could not find duck.png!")

		# 3. Dynamically find sounds
		sounds_dir = None
		for root, dirs, files in os.walk(base_dir):
			if '.venv' in root or 'venv' in root or '__pycache__' in root:
				continue
			if 'move.wav' in files or 'capture.wav' in files or 'move-check.wav' in files:
				sounds_dir = root
				break

		# Added 'move_check' to the dictionary
		sound_files = {
			'move': 'move.wav', 'capture': 'capture.wav', 'castle': 'castle.wav',
			'promote': 'promote.wav', 'notify': 'notify.wav', 'game_over': 'game_over.wav',
			'move_check': 'move-check.wav'
		}
		
		if sounds_dir:
			for name, filename in sound_files.items():
				path = os.path.join(sounds_dir, filename)
				if os.path.exists(path):
					try:
						snd = pygame.mixer.Sound(path)
						snd.set_volume(SOUND_VOLUME)
						self.sounds[name] = snd
					except: pass

	def play_sound(self, sound_name):
		"""Plays a loaded sound effect safely."""
		if hasattr(self, 'sounds') and sound_name in self.sounds:
			try:
				self.sounds[sound_name].play()
			except:
				pass