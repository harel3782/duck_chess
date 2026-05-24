import os
import pytest

# pygame must be initialised before any DuckChess_Game import because
# DuckChess_Game/UI/settings.py calls pygame.font.init() at module level.
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame
pygame.init()

from DuckChess_Game.Logic.logic import GameLogicMixin
from DuckChess_Game.Logic.bitboard_manager import BitboardManager
from DuckChess_Game.Logic.board_manager import BoardManager
from DuckChess_Game.UI.pieces import Piece
from DuckChess_Game.Logic.constants import PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING


class HeadlessEngine(GameLogicMixin):
    """Sound-free, animation-free engine for testing."""
    def __init__(self):
        self.game_mode = 'rl_training'
        self.reset_game_state()


@pytest.fixture
def engine():
    """Fresh HeadlessEngine at the standard starting position."""
    return HeadlessEngine()


@pytest.fixture
def fresh_bb():
    """Completely empty BitboardManager."""
    return BitboardManager()


@pytest.fixture
def starting_bb():
    """BitboardManager populated with the standard starting position (no duck)."""
    bb = BitboardManager()
    for piece, r, c in BoardManager().get_initial_setup():
        bb.add_piece(piece.color, piece.type, r, c)
    return bb


@pytest.fixture
def starting_board():
    """2D board list at the standard starting position."""
    bm = BoardManager()
    board = bm.create_empty_board()
    for piece, r, c in bm.get_initial_setup():
        board[r][c] = piece
    return board


@pytest.fixture
def make_piece():
    """Factory: make_piece('w', QUEEN) -> Piece."""
    return lambda color, piece_type: Piece(color, piece_type)
