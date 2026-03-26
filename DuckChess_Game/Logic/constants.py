# --- Piece Constants ---
KING, QUEEN, ROOK, BISHOP, KNIGHT, PAWN = 'K', 'Q', 'R', 'B', 'N', 'P'

# --- Evaluation Values ---
PIECE_VALUES = {
	PAWN: 1,
	KNIGHT: 3,
	BISHOP: 3,
	ROOK: 5,
	QUEEN: 9,
	KING: 0
}

# --- Piece Visuals ---
UNICODE_PIECES = {
	'w': {KING: '♔', QUEEN: '♕', ROOK: '♖', BISHOP: '♗', KNIGHT: '♘', PAWN: '♙'},
	'b': {KING: '♚', QUEEN: '♛', ROOK: '♜', BISHOP: '♝', KNIGHT: '♞', PAWN: '♟'}
}

STARTING_DUCK_POS = (-1, -1)