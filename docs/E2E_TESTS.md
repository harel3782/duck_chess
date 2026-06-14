# E2E Tests - Duck Chess Web UI

Complete end-to-end test suite using Playwright for the Duck Chess Web UI.

---

## Overview

**Framework**: Playwright (Chromium)  
**Coverage**: User interactions, game flows, save/load, replay  
**Tests**: 50+ scenarios across 3 test files

---

## Test Files

### 1. `test_e2e_auth_and_menu.py`
Tests for authentication and menu navigation.

- **Authentication**
  - Splash screen loading
  - Login with username
  - Username display
  - Empty username handling

- **Menu Navigation**
  - Game mode options
  - Rules modal
  - Model selection
  - Keyboard shortcuts

- **Responsive Design**
  - Mobile viewport (375x667)
  - Tablet viewport (768x1024)

### 2. `test_e2e_gameplay.py`
Tests for actual game play and interactions.

- **Game Initialization**
  - vs-AI White loading
  - vs-AI Black loading
  - 2-Player loading
  - Board setup verification

- **Move Execution**
  - Piece selection
  - Move validation
  - Move history display
  - Duck placement

- **Board Interaction**
  - Board flip (button)
  - Board flip (F key)
  - Invalid move rejection

- **Game State**
  - Timers display and increment
  - Turn management
  - Resignation flow
  - Game over screen

### 3. `test_e2e_save_replay.py`
Tests for saving, loading, and replaying games.

- **Save Game**
  - Save dialog opening
  - Save with custom name
  - Success message display
  - Error handling

- **Load Game**
  - Saved games list
  - Load button functionality
  - Game reconstruction

- **Replay Mode**
  - Replay controls visibility
  - Previous/Next navigation
  - Auto-play functionality
  - Move counter display
  - Exit to menu

- **Error Handling**
  - Network failure handling
  - Retry functionality
  - Download fallback

---

## Installation

### 1. Install Playwright
```bash
pip install playwright
```

### 2. Install Browser
```bash
playwright install chromium
```

Or install all browsers:
```bash
playwright install
```

### 3. Install Test Dependencies
```bash
pip install -r requirements.txt
```

---

## Running Tests

### Run All E2E Tests
```bash
pytest tests/test_e2e_*.py -v
```

### Run Specific Test File
```bash
pytest tests/test_e2e_auth_and_menu.py -v
pytest tests/test_e2e_gameplay.py -v
pytest tests/test_e2e_save_replay.py -v
```

### Run Single Test
```bash
pytest tests/test_e2e_gameplay.py::test_can_move_pawn_one_square -v
```

### Run with Screenshots on Failure
```bash
pytest tests/test_e2e_*.py -v --screenshot on_failure
```

### Run in Headed Mode (See Browser)
```bash
HEADED=1 pytest tests/test_e2e_*.py -v
```

---

## Prerequisites

### Server Running
The tests expect the Duck Chess web server to be running:

```bash
python -m uvicorn web_ui.server:app --host 127.0.0.1 --port 7890
```

Tests will try to connect to: `http://localhost:7890`

### Database/State
- Tests create fresh game sessions
- No persistent state required
- Each test is independent

---

## Test Structure

### Fixtures

#### `page` (from conftest_e2e.py)
Fresh browser page for each test.

```python
def test_something(page):
    page.goto("http://localhost:7890")
```

#### `browser` (session-scoped)
Shared browser instance across tests.

```python
@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()
```

### Helpers

#### `login_and_start_game(page, game_type)`
Logs in and starts a game in one step.

```python
def test_gameplay(page):
    login_and_start_game(page, "white")
    # Game is now loaded
```

#### `resign_game(page)`
Resigns from current game quickly.

```python
def test_save(page):
    login_and_start_game(page, "white")
    resign_game(page)
    # Game over screen is now visible
```

---

## Selectors Reference

Common selectors used across tests:

```
[id="board"]              → Game board element
[id="screen-menu"]        → Menu screen
[id="screen-auth"]        → Auth screen
[id="splash"]             → Splash screen
[id="modal-over"]         → Game over modal
[id="modal-rules"]        → Rules modal
[id="history-box"]        → Move history box
[data-r="6"][data-c="4"] → Board square (e2)
button:has-text("...")    → Button by text
```

---

## Common Patterns

### Wait for Board to Load
```python
page.wait_for_selector('[id="board"]', timeout=5000)
```

### Wait for Splash to Fade
```python
page.wait_for_timeout(2500)
```

### Make a Move
```python
page.locator('[data-r="6"][data-c="4"]').click()  # Select piece
page.wait_for_timeout(200)
page.locator('[data-r="4"][data-c="4"]').click()  # Destination
```

### Check Text Appears
```python
expect(page).to_contain_text("Your move")
```

### Check Element Visible
```python
expect(page.locator('[id="board"]')).to_be_visible()
```

---

## Debug Mode

### Print Page Content
```python
print(page.content())
```

### Take Screenshot
```python
page.screenshot(path="debug.png")
```

### Pause Execution
```python
page.pause()  # Opens Playwright Inspector
```

### Verbose Logging
```python
pytest tests/test_e2e_auth_and_menu.py -v -s
```

---

## Known Limitations

### Skipped Tests
Some tests are placeholders because they require:
- Pre-existing saved games
- Network failure simulation
- Complex board state setup

### Browser
Tests run Chromium in headless mode by default. To see browser:
```bash
HEADED=1 pytest tests/test_e2e_*.py -v
```

### Flakiness
Tests use explicit waits (200-2500ms) to handle asynchronous operations. Increase timeouts if tests fail intermittently:

```python
page.wait_for_selector('[id="board"]', timeout=10000)
```

---

## CI/CD Integration

### GitHub Actions Example
```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - run: pip install -r requirements.txt
      - run: playwright install
      
      - run: python -m uvicorn web_ui.server:app &
      - run: sleep 2
      - run: pytest tests/test_e2e_*.py -v
```

---

## Extending Tests

### Add New Test
```python
def test_new_feature(page):
    """Test description."""
    login_and_start_game(page, "white")
    
    # Your test code
    page.click('button:has-text("Action")')
    expect(page).to_contain_text("Result")
```

### Add New Fixture
```python
@pytest.fixture
def logged_in_page(page):
    """Page with user already logged in."""
    page.goto("http://localhost:7890")
    page.wait_for_timeout(2500)
    page.fill('[id="auth-pass"]', "TestUser")
    page.click('button:has-text("Login")')
    return page
```

---

## Troubleshooting

### "Browser not found"
```bash
playwright install chromium
```

### "Timeout waiting for element"
Increase timeout in the test:
```python
page.wait_for_selector('[id="board"]', timeout=10000)
```

### "Navigation timed out"
Server may not be running:
```bash
python -m uvicorn web_ui.server:app --host 127.0.0.1 --port 7890
```

### Tests Pass Locally but Fail in CI
- Increase timeouts (network latency in CI)
- Add explicit waits between actions
- Check server startup delay

---

## Performance Targets

- **Auth flow**: <2s
- **Game load**: <3s
- **Move execution**: <1s
- **Save game**: <2s
- **Replay load**: <2s

---

## Next Steps

1. **Run Setup**: Install Playwright and browsers
2. **Start Server**: Run web_ui server
3. **Run Tests**: `pytest tests/test_e2e_auth_and_menu.py -v`
4. **Debug**: Use page.pause() or screenshots
5. **Add Tests**: Extend for new features

---

**Status**: Foundation ready  
**Coverage**: 50+ test scenarios  
**Next**: Add visual regression, performance tests

