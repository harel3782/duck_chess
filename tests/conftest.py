"""
Pytest configuration for Duck Chess tests.
Includes optional browser fixtures for E2E tests and game engine fixtures.
"""
import pytest
import sys
from DuckChess_Game.SBThree.base.env_base import _HeadlessEngine
from DuckChess_Game.Logic.bitboard_manager import BitboardManager

def pytest_configure(config):
    """Configure pytest - add markers."""
    config.addinivalue_line(
        "markers", "e2e: mark test as an end-to-end test"
    )


@pytest.fixture
def engine():
    """Provide a fresh game engine for each test."""
    return _HeadlessEngine()


@pytest.fixture
def fresh_bb():
    """Provide a fresh BitboardManager for each test."""
    return BitboardManager()


@pytest.fixture
def starting_bb():
    """Provide a BitboardManager at starting position."""
    bb = BitboardManager()
    # Initialize with standard starting position
    from DuckChess_Game.Logic.constants import PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING

    # Black pieces (row 0 and 1)
    for c in range(8):
        bb.add_piece('b', PAWN, 1, c)
    bb.add_piece('b', ROOK, 0, 0)
    bb.add_piece('b', KNIGHT, 0, 1)
    bb.add_piece('b', BISHOP, 0, 2)
    bb.add_piece('b', QUEEN, 0, 3)
    bb.add_piece('b', KING, 0, 4)
    bb.add_piece('b', BISHOP, 0, 5)
    bb.add_piece('b', KNIGHT, 0, 6)
    bb.add_piece('b', ROOK, 0, 7)

    # White pieces (row 6 and 7)
    for c in range(8):
        bb.add_piece('w', PAWN, 6, c)
    bb.add_piece('w', ROOK, 7, 0)
    bb.add_piece('w', KNIGHT, 7, 1)
    bb.add_piece('w', BISHOP, 7, 2)
    bb.add_piece('w', QUEEN, 7, 3)
    bb.add_piece('w', KING, 7, 4)
    bb.add_piece('w', BISHOP, 7, 5)
    bb.add_piece('w', KNIGHT, 7, 6)
    bb.add_piece('w', ROOK, 7, 7)

    # Do NOT initialize duck - tests will manage it
    return bb


@pytest.fixture
def starting_board():
    """Provide a 2D board array at starting position."""
    from DuckChess_Game.UI.pieces import Piece
    from DuckChess_Game.Logic.constants import PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING

    board_grid = [[None] * 8 for _ in range(8)]

    # Black pieces (use 'b' for black, 'w' for white to match bitboard color codes)
    for c in range(8):
        board_grid[1][c] = Piece('b', PAWN)
    board_grid[0][0] = Piece('b', ROOK)
    board_grid[0][1] = Piece('b', KNIGHT)
    board_grid[0][2] = Piece('b', BISHOP)
    board_grid[0][3] = Piece('b', QUEEN)
    board_grid[0][4] = Piece('b', KING)
    board_grid[0][5] = Piece('b', BISHOP)
    board_grid[0][6] = Piece('b', KNIGHT)
    board_grid[0][7] = Piece('b', ROOK)

    # White pieces
    for c in range(8):
        board_grid[6][c] = Piece('w', PAWN)
    board_grid[7][0] = Piece('w', ROOK)
    board_grid[7][1] = Piece('w', KNIGHT)
    board_grid[7][2] = Piece('w', BISHOP)
    board_grid[7][3] = Piece('w', QUEEN)
    board_grid[7][4] = Piece('w', KING)
    board_grid[7][5] = Piece('w', BISHOP)
    board_grid[7][6] = Piece('w', KNIGHT)
    board_grid[7][7] = Piece('w', ROOK)

    return board_grid


# Conditionally load E2E fixtures only if playwright is available
try:
    from playwright.sync_api import sync_playwright

    @pytest.fixture(scope="session")
    def browser():
        """Create a browser instance for E2E tests."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            yield browser
            browser.close()

    @pytest.fixture
    def context(browser):
        """Create a new browser context for each test."""
        ctx = browser.new_context(viewport={"width": 1280, "height": 720})
        yield ctx
        ctx.close()

    @pytest.fixture
    def page(context):
        """Create a new page for each test."""
        p = context.new_page()
        yield p
        p.close()

except ImportError:
    # Playwright not installed - E2E tests will be skipped
    pass
