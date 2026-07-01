# Piece type constants double as FEN letters ('K','Q','R','B','N','P'),
# so they can be written directly into FEN strings without a lookup table.
KING, QUEEN, ROOK, BISHOP, KNIGHT, PAWN = 'K', 'Q', 'R', 'B', 'N', 'P'

# Standard material values (integers) used for eval and captured-piece display.
# KING = 0 because the king is never traded; king-capture is a game-ending event,
# not a material exchange to be scored.
PIECE_VALUES = {
	PAWN: 1,
	KNIGHT: 3,
	BISHOP: 3,
	ROOK: 5,
	QUEEN: 9,
	KING: 0
}

UNICODE_PIECES = {
	'w': {KING: '♔', QUEEN: '♕', ROOK: '♖', BISHOP: '♗', KNIGHT: '♘', PAWN: '♙'},
	'b': {KING: '♚', QUEEN: '♛', ROOK: '♜', BISHOP: '♝', KNIGHT: '♞', PAWN: '♟'}
}

# Time (ms) the AI waits before each action, used to pace AI turns in an
# interactive front-end so moves don't appear instantaneous.
AI_MOVE_DELAY = 1200

# Sentinel meaning "duck not yet on the board". Stored as a tuple so it is
# comparable with (r, c) tuples, but (-1,-1) is truthy — always check with
# `duck_pos != (-1,-1)`, never with plain `if duck_pos:`.
STARTING_DUCK_POS = (-1, -1)