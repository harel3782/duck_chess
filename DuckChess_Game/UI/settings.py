import pygame
import os

# --- Visual Assets ---
def get_asset_path(filename):
	"""Resolves absolute paths for external assets."""
	current_file_dir = os.path.dirname(os.path.abspath(__file__))
	assets_dir = os.path.normpath(os.path.join(current_file_dir, "..", "assets"))
	return os.path.join(assets_dir, filename)

# --- Premium Walnut & Brass Palette ---
BG_COLOR = (18, 20, 24)
PANEL_BG = (42, 46, 54, 245)
MENU_ACCENT = (218, 165, 32)     # Antique Gold

# Board Colors (Maple & Walnut)
WHITE_COLOR = (240, 225, 195)
BLACK_SQ_COLOR = (110, 75, 55)
BOARD_FRAME = (70, 45, 30)
HIGHLIGHT = (186, 202, 68, 140)
LAST_MOVE_COLOR = (218, 165, 32, 100)

# Valid Move Indicators (Chess.com Orange Style)
VALID_MOVE_ORANGE = (255, 150, 0, 170)  # Solid orange dot
VALID_CAPTURE_RED = (200, 60, 60, 180)

# Buttons & UI Elements
BTN_NORMAL = (50, 55, 65)
BTN_HOVER = (70, 75, 85)
BTN_BORDER = (180, 150, 100)
BTN_TEXT = (255, 245, 220)
BRASS_TEXT = (255, 235, 180)
BRASS_BORDER = (190, 160, 110)
TEXT_COLOR = (245, 245, 245)

# Evaluation Bar
EVAL_WHITE = (235, 235, 235)
EVAL_BLACK = (40, 40, 40)

# --- Fonts ---
pygame.font.init()
def get_font(size, bold=True): return pygame.font.SysFont("Verdana", size, bold=bold)

FONT_LARGE = get_font(40)
FONT_UI = get_font(14, False)
FONT_HISTORY = pygame.font.SysFont("Consolas", 14)
FONT_NAV = get_font(22, bold=True)
FONT_MENU_TITLE = pygame.font.SysFont("Georgia", 95, bold=True)
FONT_MENU_SUB = get_font(18)
FONT_EVAL = get_font(16)
FONT_STATUS = get_font(20, bold=True)

# --- Layout & Menu Constants ---
DEFAULT_WIDTH, DEFAULT_HEIGHT = 1050, 700
FPS, DUCK_SCALE_FACTOR = 60, 0.8
PANEL_WIDTH, SIDE_MARGIN, EVAL_BAR_WIDTH = 300, 20, 36
MENU_TILE_SIZE = 120
MENU_BG_DARK = (20, 22, 26)
MENU_BG_LIGHT = (25, 27, 32)

# --- AI & Animation Settings ---
AI_MOVE_DELAY = 1200             # Time AI waits before each action (ms)
ANIMATION_SPEED = 180  
ANIMATION_FPS = 60
SOUND_VOLUME = 0.5