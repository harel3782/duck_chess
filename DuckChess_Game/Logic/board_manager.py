from DuckChess_Game.Logic.pieces import Piece
from DuckChess_Game.Logic.constants import *

class BoardManager:
	"""Manages the raw board state and piece placement."""

	def create_empty_board(self):
		"""Returns an empty 8x8 grid."""
		return [[None] * 8 for _ in range(8)]

	def get_initial_setup(self):
		"""Returns the standard starting position as a list of (Piece, r, c) triples.

		Row 0 = rank 8 (black's back rank); row 7 = rank 1 (white's back rank).
		Black pawns are at row 1 (rank 7); white pawns at row 6 (rank 2).
		The duck is NOT included — it starts at (-1,-1) and is placed after
		the first piece move of the game.
		"""
		setup = [
			(ROOK, 0, 0), (KNIGHT, 0, 1), (BISHOP, 0, 2), (QUEEN, 0, 3), (KING, 0, 4), (BISHOP, 0, 5), (KNIGHT, 0, 6), (ROOK, 0, 7),
			(ROOK, 7, 0), (KNIGHT, 7, 1), (BISHOP, 7, 2), (QUEEN, 7, 3), (KING, 7, 4), (BISHOP, 7, 5), (KNIGHT, 7, 6), (ROOK, 7, 7)
		]
		pieces = []
		for t, r, c in setup:
			pieces.append((Piece('b' if r == 0 else 'w', t), r, c))

		for c in range(8):
			pieces.append((Piece('b', PAWN), 1, c))
			pieces.append((Piece('w', PAWN), 6, c))
		return pieces