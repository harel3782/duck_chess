import pygame

# --- Modernized Color Palette: Deep Ocean & Neon ---
# Technical Settings
FPS = 60
DEFAULT_WIDTH = 1100
DEFAULT_HEIGHT = 800
ANIMATION_SPEED = 150
ANIMATION_FPS = 60
SOUND_VOLUME = 0.6

# Background & Main Panels
COLOR_BG = (10, 15, 25)
COLOR_PANEL_BG = (20, 30, 45)
COLOR_TEXT = (230, 235, 245)

# Board Colors
COLOR_SQ_LIGHT = (165, 185, 200)
COLOR_SQ_DARK = (45, 65, 85)

# --- Legacy Variables Mapped to New Theme ---
# (Required for rendering_ui.py and other UI components)
MENU_BG_DARK = (10, 15, 25)
MENU_BG_LIGHT = (20, 30, 45)
MENU_ACCENT = (0, 255, 255)
BTN_NORMAL = (45, 65, 85)
BTN_HOVER = (65, 85, 105)
BTN_BORDER = (0, 215, 215)
BTN_TEXT = (230, 235, 245)
EVAL_WHITE = (230, 235, 245)
EVAL_BLACK = (45, 65, 85)
TEXT_COLOR = COLOR_TEXT
WHITE_COLOR = COLOR_SQ_LIGHT
BLACK_SQ_COLOR = COLOR_SQ_DARK
HIGHLIGHT = (0, 255, 255, 120)
LAST_MOVE_COLOR = (0, 255, 255, 80)
VALID_MOVE = (0, 255, 255, 60)

# Neon Accent Colors (Semi-translucent)
COLOR_ACCENT_WHITE = (0, 215, 215, 100)
COLOR_ACCENT_BLACK = (200, 30, 200, 100)
COLOR_HIGHLIGHT = (0, 255, 255, 120)
COLOR_VALID_MOVE = (0, 255, 255, 60)
COLOR_CAPTURE_MOVE = (255, 50, 50, 140)
COLOR_LAST_MOVE = (0, 255, 255, 80)
COLOR_DUCK_VALID = (255, 165, 0, 100)
COLOR_DUCK_ACCENT = (255, 140, 0)

# Pieces
KING, QUEEN, ROOK, BISHOP, KNIGHT, PAWN = 'K', 'Q', 'R', 'B', 'N', 'P'
PIECE_VALUES = {PAWN: 1, KNIGHT: 3, BISHOP: 3, ROOK: 5, QUEEN: 9, KING: 0}

# Unicode Fallback
UNICODE_PIECES = {
	'w': {'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙'},
	'b': {'K': '♚', 'Q': '♛', 'R': '♜', 'B': '♝', 'N': '♞', 'P': '♟'}
}