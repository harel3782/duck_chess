"""
Pytest configuration for E2E tests with Playwright.
"""
import pytest
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="session")
def browser_context_args():
    """Configure browser context arguments."""
    return {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


@pytest.fixture(scope="session")
def browser():
    """Create a browser instance for the session."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def context(browser):
    """Create a new browser context for each test."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 720}
    )
    yield context
    context.close()


@pytest.fixture
def page(context):
    """Create a new page for each test."""
    page = context.new_page()
    yield page
    page.close()


# ─────────────────────────────────────────────────────────────────────────
# HOOKS
# ─────────────────────────────────────────────────────────────────────────

def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers", "e2e: mark test as an end-to-end test"
    )
