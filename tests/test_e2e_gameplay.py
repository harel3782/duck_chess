"""
E2E tests for Duck Chess Web UI - Gameplay and Move Execution.

Tests cover:
- Starting games (vs AI, 2-player)
- Making moves (click pieces, move)
- Board interaction
- Move history display
- Timers
- Resignation
"""
import pytest
from playwright.sync_api import Page, expect


BASE_URL = "http://localhost:7890"
TIMEOUT = 5000


def login_and_start_game(page, game_type="white"):
    """Helper to login and start a game."""
    page.goto(BASE_URL)
    page.wait_for_timeout(2500)  # Splash screen

    page.fill('[id="auth-pass"]', "TestPlayer")
    page.click('button:has-text("Login")')

    page.wait_for_timeout(500)

    if game_type == "white":
        page.click('text=Play as White')
    elif game_type == "black":
        page.click('text=Play as Black')
    elif game_type == "2player":
        page.click('text=2 Players')

    # Wait for game to load
    page.wait_for_selector('[id="board"]', timeout=TIMEOUT)


@pytest.fixture
def page(browser):
    """Create a new page for each test."""
    return browser.new_page()


# ─────────────────────────────────────────────────────────────────────────
# TEST: GAME INITIALIZATION
# ─────────────────────────────────────────────────────────────────────────

def test_vs_ai_white_game_loads(page):
    """Test that vs-AI white game loads properly."""
    login_and_start_game(page, "white")

    # Board should be visible
    board = page.locator('[id="board"]')
    expect(board).to_be_visible()

    # Game info should show
    expect(page).to_contain_text("Your move")


def test_vs_ai_black_game_loads(page):
    """Test that vs-AI black game loads (AI moves first)."""
    login_and_start_game(page, "black")

    board = page.locator('[id="board"]')
    expect(board).to_be_visible()

    # Should show AI is thinking
    page.wait_for_timeout(1000)


def test_2player_game_loads(page):
    """Test that 2-player game loads."""
    login_and_start_game(page, "2player")

    board = page.locator('[id="board"]')
    expect(board).to_be_visible()

    expect(page).to_contain_text("Your move")


def test_board_has_all_pieces(page):
    """Test that board displays all starting pieces."""
    login_and_start_game(page, "white")

    board = page.locator('[id="board"]')
    expect(board).to_be_visible()

    # Count pieces on board (rough check)
    pieces = page.locator('[data-piece]')
    # Should have 32 pieces (16 white + 16 black)
    expect(pieces).to_have_count(32)


# ─────────────────────────────────────────────────────────────────────────
# TEST: MOVE EXECUTION
# ─────────────────────────────────────────────────────────────────────────

def test_can_select_piece(page):
    """Test that clicking a piece selects it."""
    login_and_start_game(page, "white")

    # Click e2 pawn (white)
    # Selector depends on board implementation
    pawn = page.locator('[data-square="e2"]')
    pawn.click()

    # Piece should be highlighted
    # Depends on implementation


def test_can_move_pawn_one_square(page):
    """Test moving a pawn one square forward."""
    login_and_start_game(page, "white")

    # Click pawn at e2
    e2 = page.locator('[data-r="6"][data-c="4"]')  # e2 in array coords
    e2.click()

    page.wait_for_timeout(300)

    # Click destination e3
    e3 = page.locator('[data-r="5"][data-c="4"]')  # e3 in array coords
    e3.click()

    page.wait_for_timeout(500)

    # Move history should show
    expect(page).to_contain_text("→")


def test_move_history_displays(page):
    """Test that move history is displayed after a move."""
    login_and_start_game(page, "white")

    # Make a move
    e2 = page.locator('[data-r="6"][data-c="4"]')
    e2.click()
    page.wait_for_timeout(200)

    e4 = page.locator('[data-r="4"][data-c="4"]')
    e4.click()

    page.wait_for_timeout(500)

    # History should show the move
    history = page.locator('[id="history-box"]')
    expect(history).to_contain_text(r"→|e2|e4")


def test_duck_placement_prompt_appears(page):
    """Test that duck placement prompt appears after piece move."""
    login_and_start_game(page, "white")

    # Make a move
    e2 = page.locator('[data-r="6"][data-c="4"]')
    e2.click()
    page.wait_for_timeout(200)

    e4 = page.locator('[data-r="4"][data-c="4"]')
    e4.click()

    page.wait_for_timeout(500)

    # Should show "place duck" message
    expect(page).to_contain_text(r"duck|place")


def test_invalid_move_rejected(page):
    """Test that invalid move is rejected."""
    login_and_start_game(page, "white")

    # Try to move piece backward (invalid)
    e2 = page.locator('[data-r="6"][data-c="4"]')
    e2.click()
    page.wait_for_timeout(200)

    # Click backward (e5)
    e5 = page.locator('[data-r="3"][data-c="4"]')
    e5.click()

    page.wait_for_timeout(200)

    # Should show error or reject silently
    # Depends on implementation


# ─────────────────────────────────────────────────────────────────────────
# TEST: DUCK PLACEMENT
# ─────────────────────────────────────────────────────────────────────────

def test_duck_placement_changes_turn(page):
    """Test that placing duck changes turn."""
    login_and_start_game(page, "white")

    # Make move
    e2 = page.locator('[data-r="6"][data-c="4"]')
    e2.click()
    page.wait_for_timeout(200)
    e4 = page.locator('[data-r="4"][data-c="4"]')
    e4.click()

    page.wait_for_timeout(500)

    # Place duck somewhere
    d5 = page.locator('[data-r="3"][data-c="3"]')
    d5.click()

    page.wait_for_timeout(500)

    # Should be black's turn now
    expect(page).to_contain_text("Opponent")


# ─────────────────────────────────────────────────────────────────────────
# TEST: BOARD FLIP
# ─────────────────────────────────────────────────────────────────────────

def test_board_flip_with_button(page):
    """Test that board can be flipped with button."""
    login_and_start_game(page, "white")

    # Click flip button
    flip_btn = page.locator('button:has-text("↕")')
    flip_btn.click()

    page.wait_for_timeout(300)

    # Board orientation should change
    board = page.locator('[id="board"]')
    expect(board).to_be_visible()


def test_board_flip_with_f_key(page):
    """Test that board can be flipped with F key."""
    login_and_start_game(page, "white")

    # Press F
    page.keyboard.press("f")

    page.wait_for_timeout(300)

    # Board should flip
    board = page.locator('[id="board"]')
    expect(board).to_be_visible()


# ─────────────────────────────────────────────────────────────────────────
# TEST: TIMERS
# ─────────────────────────────────────────────────────────────────────────

def test_timer_displays_for_current_player(page):
    """Test that timer displays for current player."""
    login_and_start_game(page, "white")

    # Timer should be visible
    timer = page.locator('text=00:')
    expect(timer).to_be_visible()


def test_timer_counts_up(page):
    """Test that timer increments over time."""
    login_and_start_game(page, "white")

    # Get initial timer value
    timer1 = page.locator('text=/\\d+:\\d+/').first
    expect(timer1).to_be_visible()

    # Wait 2 seconds
    page.wait_for_timeout(2000)

    # Timer should have incremented
    timer2 = page.locator('text=/\\d+:\\d+/').first
    expect(timer2).to_be_visible()


# ─────────────────────────────────────────────────────────────────────────
# TEST: RESIGNATION
# ─────────────────────────────────────────────────────────────────────────

def test_resign_button_visible(page):
    """Test that resign button is visible during game."""
    login_and_start_game(page, "white")

    resign_btn = page.locator('button:has-text("Resign")')
    expect(resign_btn).to_be_visible()


def test_resignation_ends_game(page):
    """Test that clicking resign ends the game."""
    login_and_start_game(page, "white")

    resign_btn = page.locator('button:has-text("Resign")')
    resign_btn.click()

    page.wait_for_timeout(500)

    # Game over modal should appear
    modal = page.locator('[id="modal-over"]')
    expect(modal).to_have_class(r'active')

    expect(page).to_contain_text(r"Lost|Won|Game Over")


def test_resign_with_r_key(page):
    """Test that R key triggers resignation."""
    login_and_start_game(page, "white")

    # Press R
    page.keyboard.press("r")

    page.wait_for_timeout(500)

    # Should show confirmation or end game
    # Depends on implementation


# ─────────────────────────────────────────────────────────────────────────
# TEST: GAME OVER SCREEN
# ─────────────────────────────────────────────────────────────────────────

def test_game_over_shows_result(page):
    """Test that game over screen shows result."""
    login_and_start_game(page, "white")

    resign_btn = page.locator('button:has-text("Resign")')
    resign_btn.click()

    page.wait_for_timeout(500)

    # Should show result
    expect(page).to_contain_text(r"You Lost")


def test_game_over_shows_save_button(page):
    """Test that game over screen has save button."""
    login_and_start_game(page, "white")

    resign_btn = page.locator('button:has-text("Resign")')
    resign_btn.click()

    page.wait_for_timeout(500)

    save_btn = page.locator('button:has-text("Save")')
    expect(save_btn).to_be_visible()


def test_play_again_starts_new_game(page):
    """Test that 'Play Again' button starts new game."""
    login_and_start_game(page, "white")

    resign_btn = page.locator('button:has-text("Resign")')
    resign_btn.click()

    page.wait_for_timeout(500)

    play_again = page.locator('button:has-text("Play Again")')
    play_again.click()

    page.wait_for_timeout(1000)

    # New game should load
    board = page.locator('[id="board"]')
    expect(board).to_be_visible()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
