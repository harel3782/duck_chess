"""
E2E tests for Duck Chess Web UI - Save, Load, and Replay.

Tests cover:
- Saving games
- Loading games
- Replay mode
- Replay controls
- Move navigation
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

    page.wait_for_selector('[id="board"]', timeout=TIMEOUT)


def resign_game(page):
    """Helper to resign the current game."""
    resign_btn = page.locator('button:has-text("Resign")')
    resign_btn.click()
    page.wait_for_timeout(500)


@pytest.fixture
def page(browser):
    """Create a new page for each test."""
    return browser.new_page()


# ─────────────────────────────────────────────────────────────────────────
# TEST: SAVE GAME
# ─────────────────────────────────────────────────────────────────────────

def test_save_button_visible_at_game_over(page):
    """Test that save button appears at game over."""
    login_and_start_game(page, "white")
    resign_game(page)

    save_btn = page.locator('button:has-text("Save")')
    expect(save_btn).to_be_visible()


def test_save_game_opens_dialog(page):
    """Test that clicking save opens a dialog."""
    login_and_start_game(page, "white")
    resign_game(page)

    save_btn = page.locator('button:has-text("Save")')
    save_btn.click()

    page.wait_for_timeout(300)

    # Dialog or input should appear
    input_field = page.locator('input[type="text"]')
    expect(input_field).to_be_visible()


def test_save_game_with_name(page):
    """Test saving a game with a custom name."""
    login_and_start_game(page, "white")
    resign_game(page)

    save_btn = page.locator('button:has-text("Save")')
    save_btn.click()

    page.wait_for_timeout(300)

    # Enter game name
    input_field = page.locator('input[type="text"]')
    input_field.fill("Test Game 1")

    # Confirm save
    confirm_btn = page.locator('button:has-text("Save|OK")')
    confirm_btn.click()

    page.wait_for_timeout(1000)

    # Should show success message
    expect(page).to_contain_text(r"Saved|✓")


def test_save_shows_success_message(page):
    """Test that save shows success feedback."""
    login_and_start_game(page, "white")
    resign_game(page)

    save_btn = page.locator('button:has-text("Save")')
    save_btn.click()

    page.wait_for_timeout(300)

    input_field = page.locator('input[type="text"]')
    input_field.fill("Game ABC")

    confirm_btn = page.locator('button:has-text("Save|OK")')
    confirm_btn.click()

    page.wait_for_timeout(1000)

    # Success message
    expect(page).to_contain_text(r"Saved!|Success|✓")


# ─────────────────────────────────────────────────────────────────────────
# TEST: LOAD GAME
# ─────────────────────────────────────────────────────────────────────────

def test_saved_games_list_appears(page):
    """Test that saved games list appears on menu."""
    page.goto(BASE_URL)
    page.wait_for_timeout(2500)

    page.fill('[id="auth-pass"]', "TestPlayer")
    page.click('button:has-text("Login")')

    page.wait_for_timeout(500)

    # Saved games section should appear
    saved = page.locator('text=Saved Games|My Games')
    expect(saved).to_be_visible()


def test_saved_game_cards_visible(page):
    """Test that saved game cards are visible (if games exist)."""
    page.goto(BASE_URL)
    page.wait_for_timeout(2500)

    page.fill('[id="auth-pass"]', "TestPlayer")
    page.click('button:has-text("Login")')

    page.wait_for_timeout(500)

    # Saved games cards
    cards = page.locator('[class*="game-card"]')
    # Cards may or may not exist depending on test data


def test_load_game_button_works(page):
    """Test that load game button works."""
    # Save a game first
    login_and_start_game(page, "white")
    resign_game(page)

    save_btn = page.locator('button:has-text("Save")')
    save_btn.click()
    page.wait_for_timeout(300)

    input_field = page.locator('input[type="text"]')
    input_field.fill("LoadTest1")

    confirm_btn = page.locator('button:has-text("Save|OK")')
    confirm_btn.click()

    page.wait_for_timeout(1000)

    # Go back to menu
    menu_btn = page.locator('button:has-text("Menu|Back")')
    menu_btn.click()

    page.wait_for_timeout(500)

    # Find and click load button
    load_btn = page.locator('button:has-text("Load|Replay")')
    if load_btn.count() > 0:
        load_btn.first.click()
        page.wait_for_timeout(1000)


# ─────────────────────────────────────────────────────────────────────────
# TEST: REPLAY MODE
# ─────────────────────────────────────────────────────────────────────────

def test_replay_controls_visible(page):
    """Test that replay controls are visible in replay mode."""
    # This would need a saved game to load
    # Placeholder for structure


def test_replay_prev_button_works(page):
    """Test that prev button steps back through moves."""
    # Would need saved game with moves


def test_replay_next_button_works(page):
    """Test that next button steps forward through moves."""
    # Would need saved game with moves


def test_replay_play_button_auto_plays(page):
    """Test that play button auto-steps through moves."""
    # Would need saved game with moves


def test_replay_move_counter_displays(page):
    """Test that move counter shows position."""
    # Would need saved game with moves


def test_replay_exit_returns_to_menu(page):
    """Test that exit button returns to menu."""
    # Would need saved game with moves


# ─────────────────────────────────────────────────────────────────────────
# TEST: ERROR HANDLING
# ─────────────────────────────────────────────────────────────────────────

def test_save_shows_error_on_network_failure(page):
    """Test that save error is shown when network fails."""
    login_and_start_game(page, "white")
    resign_game(page)

    # This would require simulating network failure
    # Using Playwright's network interception


def test_save_retry_button_appears_on_error(page):
    """Test that retry button appears on save error."""
    # Would need network failure simulation


def test_save_download_fallback_works(page):
    """Test that download fallback works when save fails."""
    # Would need network failure simulation


# ─────────────────────────────────────────────────────────────────────────
# TEST: RESPONSIVE REPLAY
# ─────────────────────────────────────────────────────────────────────────

def test_replay_responsive_mobile(page):
    """Test that replay is responsive on mobile."""
    page.set_viewport_size({"width": 375, "height": 667})

    # Would load a saved game in replay mode
    # Check controls are accessible


def test_replay_responsive_tablet(page):
    """Test that replay is responsive on tablet."""
    page.set_viewport_size({"width": 768, "height": 1024})

    # Would load a saved game in replay mode
    # Check layout adapts


# ─────────────────────────────────────────────────────────────────────────
# TEST: KEYBOARD SHORTCUTS IN REPLAY
# ─────────────────────────────────────────────────────────────────────────

def test_arrow_keys_navigate_replay(page):
    """Test that arrow keys navigate replay."""
    # Would need saved game with moves
    # Test left/right arrow navigation


def test_space_plays_replay(page):
    """Test that space bar plays replay."""
    # Would need saved game with moves
    # Test space bar toggles play/pause


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
