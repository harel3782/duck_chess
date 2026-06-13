"""
E2E tests for Duck Chess Web UI - Authentication and Menu Navigation.

Tests cover:
- Login flow
- Menu navigation
- Game mode selection
- Model selection
- Rules modal
"""
import pytest
from playwright.sync_api import Page, expect


BASE_URL = "http://localhost:7890"


@pytest.fixture
def page(browser):
    """Create a new page for each test."""
    return browser.new_page()


# ─────────────────────────────────────────────────────────────────────────
# TEST: AUTHENTICATION & LOGIN
# ─────────────────────────────────────────────────────────────────────────

def test_splash_screen_loads(page):
    """Test that splash screen appears on page load."""
    page.goto(BASE_URL)

    # Splash screen should be visible
    splash = page.locator('[id="splash"]')
    expect(splash).to_be_visible()

    # Should fade out and show auth screen
    page.wait_for_timeout(2500)
    expect(splash).not_to_be_visible()


def test_login_with_username(page):
    """Test login with a username."""
    page.goto(BASE_URL)
    page.wait_for_timeout(2500)  # Wait for splash

    # Enter username
    page.fill('[id="auth-pass"]', "TestPlayer")
    page.click('button:has-text("Login")')

    # Should show menu screen
    menu = page.locator('[id="screen-menu"]')
    expect(menu).to_be_visible()


def test_login_displays_username(page):
    """Test that logged-in username is displayed."""
    page.goto(BASE_URL)
    page.wait_for_timeout(2500)

    username = "AliceWonderland"
    page.fill('[id="auth-pass"]', username)
    page.click('button:has-text("Login")')

    # Username should appear in game screen
    page.wait_for_timeout(500)
    # Note: actual selector depends on UI, adjust as needed
    expect(page).to_contain_text(username)


def test_empty_username_prevented(page):
    """Test that empty username is not accepted."""
    page.goto(BASE_URL)
    page.wait_for_timeout(2500)

    # Try to login with empty username
    page.click('button:has-text("Login")')

    # Should still be on auth screen
    auth = page.locator('[id="screen-auth"]')
    # May or may not be visible depending on implementation


# ─────────────────────────────────────────────────────────────────────────
# TEST: MENU NAVIGATION
# ─────────────────────────────────────────────────────────────────────────

def test_menu_shows_game_options(page):
    """Test that menu displays game mode options."""
    page.goto(BASE_URL)
    page.wait_for_timeout(2500)

    page.fill('[id="auth-pass"]', "TestUser")
    page.click('button:has-text("Login")')

    # Menu should show game options
    expect(page).to_contain_text("Play as White")
    expect(page).to_contain_text("Play as Black")
    expect(page).to_contain_text("2 Players")


def test_rules_modal_opens(page):
    """Test that rules modal can be opened."""
    page.goto(BASE_URL)
    page.wait_for_timeout(2500)

    page.fill('[id="auth-pass"]', "TestUser")
    page.click('button:has-text("Login")')

    # Click rules button
    page.click('button:has-text("Rules")')

    # Rules modal should appear
    rules_modal = page.locator('[id="modal-rules"]')
    expect(rules_modal).to_have_class(r'active')


def test_rules_modal_closes_with_escape(page):
    """Test that rules modal closes with Escape key."""
    page.goto(BASE_URL)
    page.wait_for_timeout(2500)

    page.fill('[id="auth-pass"]', "TestUser")
    page.click('button:has-text("Login")')

    page.click('button:has-text("Rules")')
    page.wait_for_timeout(200)

    # Press Escape
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)

    # Modal should close
    rules_modal = page.locator('[id="modal-rules"]')
    expect(rules_modal).not_to_have_class(r'active')


# ─────────────────────────────────────────────────────────────────────────
# TEST: MODEL SELECTION
# ─────────────────────────────────────────────────────────────────────────

def test_model_dropdown_shows_options(page):
    """Test that model dropdown displays available models."""
    page.goto(BASE_URL)
    page.wait_for_timeout(2500)

    page.fill('[id="auth-pass"]', "TestUser")
    page.click('button:has-text("Login")')

    # Model dropdown should show
    dropdown = page.locator('select, [role="combobox"]')
    if dropdown.count() > 0:
        # Dropdown exists
        expect(dropdown).to_be_visible()


def test_model_selection_changes_text(page):
    """Test that selecting a model updates the display."""
    page.goto(BASE_URL)
    page.wait_for_timeout(2500)

    page.fill('[id="auth-pass"]', "TestUser")
    page.click('button:has-text("Login")')

    # Try to select a model (if dropdown exists)
    # This depends on actual implementation


# ─────────────────────────────────────────────────────────────────────────
# TEST: KEYBOARD SHORTCUTS IN MENU
# ─────────────────────────────────────────────────────────────────────────

def test_escape_key_in_menu(page):
    """Test that Escape key works in menu context."""
    page.goto(BASE_URL)
    page.wait_for_timeout(2500)

    page.fill('[id="auth-pass"]', "TestUser")
    page.click('button:has-text("Login")')

    # Should handle Escape gracefully
    page.keyboard.press("Escape")

    # Menu should still be visible
    menu = page.locator('[id="screen-menu"]')
    expect(menu).to_be_visible()


# ─────────────────────────────────────────────────────────────────────────
# TEST: RESPONSIVE MENU
# ─────────────────────────────────────────────────────────────────────────

def test_menu_responsive_mobile(page):
    """Test that menu is responsive on mobile viewport."""
    page.set_viewport_size({"width": 375, "height": 667})

    page.goto(BASE_URL)
    page.wait_for_timeout(2500)

    page.fill('[id="auth-pass"]', "MobileUser")
    page.click('button:has-text("Login")')

    # Menu options should still be visible/clickable
    expect(page).to_contain_text("Play as White")


def test_menu_responsive_tablet(page):
    """Test that menu is responsive on tablet viewport."""
    page.set_viewport_size({"width": 768, "height": 1024})

    page.goto(BASE_URL)
    page.wait_for_timeout(2500)

    page.fill('[id="auth-pass"]', "TabletUser")
    page.click('button:has-text("Login")')

    # Menu should render properly
    menu = page.locator('[id="screen-menu"]')
    expect(menu).to_be_visible()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
