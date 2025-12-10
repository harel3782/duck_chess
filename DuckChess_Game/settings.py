# --- Defaults ---
DEFAULT_WIDTH = 1050
DEFAULT_HEIGHT = 650
FPS = 60

# --- COLORS ---
WHITE_COLOR = (235, 236, 208)
BLACK_SQ_COLOR = (119, 149, 86)
HIGHLIGHT = (186, 202, 68)
LAST_MOVE_COLOR = (245, 235, 110, 160)
VALID_MOVE = (100, 200, 100, 150)
TEXT_COLOR = (20, 20, 20)
BG_COLOR = (40, 44, 52)
BOARD_BG_COLOR = (240, 240, 240)
PANEL_BG_COLOR = (50, 53, 60)
BUTTON_COLOR = (70, 130, 180)
BUTTON_HOVER = (100, 149, 237)
MENU_BG = (40, 44, 52)
ACTIVE_MOVE_BG = (80, 85, 95)
PROMOTION_BG = (255, 255, 255, 255)
EVAL_WHITE = (240, 240, 240)
EVAL_BLACK = (50, 50, 50)

# Unicode Fallback
UNICODE_PIECES = {
    'w': {'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙'},
    'b': {'K': '♚', 'Q': '♛', 'R': '♜', 'B': '♝', 'N': '♞', 'P': '♟'}
}

# Piece Constants
KING, QUEEN, ROOK, BISHOP, KNIGHT, PAWN = 'K', 'Q', 'R', 'B', 'N', 'P'

# Piece values
PIECE_VALUES = {
    PAWN: 1,
    KNIGHT: 3,
    BISHOP: 3,
    ROOK: 5,
    QUEEN: 9,
    KING: 0
}

# --- MENU AESTHETICS ---
# Dark modern theme
MENU_BG_DARK = (30, 33, 40)
MENU_BG_LIGHT = (40, 44, 52)
MENU_ACCENT = (255, 215, 0)  # Gold for the Duck
MENU_TEXT_SHADOW = (0, 0, 0, 100)

# Button Styles
BTN_NORMAL = (70, 80, 90)
BTN_HOVER = (90, 100, 110)
BTN_BORDER = (100, 110, 120)
BTN_TEXT = (240, 240, 240)

# --- ANIMATION & SOUND ---
ANIMATION_SPEED = 150  # Duration in milliseconds (Lower = Faster)
ANIMATION_FPS = 60

# Default Volume (0.0 to 1.0)
SOUND_VOLUME = 0.6