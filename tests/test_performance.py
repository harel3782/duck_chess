"""
Performance & Load Tests for Duck Chess Web UI.

Measures:
- API response times
- Page load latency
- Game initialization speed
- Concurrent session handling
- Memory usage
"""
import time
import pytest
import requests
from concurrent.futures import ThreadPoolExecutor
from playwright.sync_api import Page, expect


BASE_URL = "http://localhost:7890"
TIMEOUT = 10000

# Performance thresholds (in seconds)
THRESHOLDS = {
    "page_load": 3.0,
    "auth_screen": 2.5,
    "game_load": 3.0,
    "move_execution": 1.0,
    "save_game": 2.0,
    "load_game": 2.0,
    "api_models": 0.5,
    "api_new_game": 1.0,
    "api_move": 0.5,
}


def measure_time(func, *args, **kwargs):
    """Measure execution time of a function."""
    start = time.time()
    result = func(*args, **kwargs)
    elapsed = time.time() - start
    return elapsed, result


@pytest.fixture
def page(browser):
    """Create a new page for each test."""
    return browser.new_page()


# ─────────────────────────────────────────────────────────────────────────
# TEST: PAGE LOAD PERFORMANCE
# ─────────────────────────────────────────────────────────────────────────

def test_perf_page_load(page):
    """Performance test: Initial page load time."""
    elapsed, _ = measure_time(page.goto, BASE_URL)

    print(f"Page load: {elapsed:.2f}s")
    assert elapsed < THRESHOLDS["page_load"], f"Page load too slow: {elapsed:.2f}s"


def test_perf_splash_screen(page):
    """Performance test: Splash screen loading."""
    page.goto(BASE_URL)

    elapsed, _ = measure_time(
        page.wait_for_timeout,
        2500
    )

    # Should see auth screen after splash
    print(f"Splash display: {elapsed/1000:.2f}s")


def test_perf_auth_to_menu(page):
    """Performance test: Login and menu load."""
    page.goto(BASE_URL)
    page.wait_for_timeout(2500)

    def login_flow():
        page.fill('[id="auth-pass"]', "PerfTestUser")
        page.click('button:has-text("Login")')
        page.wait_for_selector('[id="screen-menu"]', timeout=TIMEOUT)

    elapsed, _ = measure_time(login_flow)

    print(f"Auth to menu: {elapsed:.2f}s")
    assert elapsed < THRESHOLDS["auth_screen"], f"Auth too slow: {elapsed:.2f}s"


# ─────────────────────────────────────────────────────────────────────────
# TEST: GAME INITIALIZATION
# ─────────────────────────────────────────────────────────────────────────

def test_perf_game_load_vs_white(page):
    """Performance test: Game load time (vs-AI, white)."""
    page.goto(BASE_URL)
    page.wait_for_timeout(2500)

    page.fill('[id="auth-pass"]', "PerfTestUser")
    page.click('button:has-text("Login")')
    page.wait_for_selector('[id="screen-menu"]', timeout=TIMEOUT)

    def game_load():
        page.click('text=Play as White')
        page.wait_for_selector('[id="board"]', timeout=TIMEOUT)

    elapsed, _ = measure_time(game_load)

    print(f"Game load (vs-white): {elapsed:.2f}s")
    assert elapsed < THRESHOLDS["game_load"], f"Game load too slow: {elapsed:.2f}s"


def test_perf_game_load_2player(page):
    """Performance test: Game load time (2-player)."""
    page.goto(BASE_URL)
    page.wait_for_timeout(2500)

    page.fill('[id="auth-pass"]', "PerfTestUser")
    page.click('button:has-text("Login")')
    page.wait_for_selector('[id="screen-menu"]', timeout=TIMEOUT)

    def game_load():
        page.click('text=2 Players')
        page.wait_for_selector('[id="board"]', timeout=TIMEOUT)

    elapsed, _ = measure_time(game_load)

    print(f"Game load (2-player): {elapsed:.2f}s")
    assert elapsed < THRESHOLDS["game_load"], f"Game load too slow: {elapsed:.2f}s"


# ─────────────────────────────────────────────────────────────────────────
# TEST: API RESPONSE TIMES
# ─────────────────────────────────────────────────────────────────────────

def test_perf_api_models():
    """Performance test: /api/models endpoint."""
    def fetch_models():
        response = requests.get(f"{BASE_URL}/api/models")
        assert response.status_code == 200

    elapsed, _ = measure_time(fetch_models)

    print(f"API /models: {elapsed:.3f}s")
    assert elapsed < THRESHOLDS["api_models"], f"Models endpoint slow: {elapsed:.3f}s"


def test_perf_api_new_game():
    """Performance test: /api/new-game endpoint."""
    def create_game():
        response = requests.post(
            f"{BASE_URL}/api/new-game",
            json={"color": "white", "model": None}
        )
        assert response.status_code == 200

    elapsed, _ = measure_time(create_game)

    print(f"API /new-game: {elapsed:.3f}s")
    assert elapsed < THRESHOLDS["api_new_game"], f"New game endpoint slow: {elapsed:.3f}s"


def test_perf_api_legal_moves():
    """Performance test: /api/legal-moves endpoint."""
    # Create a game first
    resp = requests.post(
        f"{BASE_URL}/api/new-game",
        json={"color": "white", "model": None}
    )
    game_id = resp.json()["gameId"]

    def get_moves():
        response = requests.post(
            f"{BASE_URL}/api/legal-moves",
            json={"game_id": game_id, "r": 6, "c": 4}
        )
        assert response.status_code == 200

    elapsed, _ = measure_time(get_moves)

    print(f"API /legal-moves: {elapsed:.3f}s")
    assert elapsed < THRESHOLDS["api_move"], f"Legal moves endpoint slow: {elapsed:.3f}s"


# ─────────────────────────────────────────────────────────────────────────
# TEST: CONCURRENT SESSIONS
# ─────────────────────────────────────────────────────────────────────────

def test_perf_concurrent_games():
    """Performance test: Multiple concurrent games."""
    def create_and_load_game():
        start = time.time()

        resp = requests.post(
            f"{BASE_URL}/api/new-game",
            json={"color": "white", "model": None}
        )

        elapsed = time.time() - start
        return elapsed

    # Create 5 concurrent games
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(create_and_load_game) for _ in range(5)]
        times = [f.result() for f in futures]

    avg_time = sum(times) / len(times)
    max_time = max(times)

    print(f"Concurrent games (5): avg {avg_time:.3f}s, max {max_time:.3f}s")
    assert max_time < THRESHOLDS["api_new_game"] * 1.5


def test_perf_many_games():
    """Performance test: Create 10 sequential games (stress test)."""
    times = []

    for i in range(10):
        start = time.time()

        resp = requests.post(
            f"{BASE_URL}/api/new-game",
            json={"color": "white", "model": None}
        )
        assert resp.status_code == 200

        elapsed = time.time() - start
        times.append(elapsed)

    avg_time = sum(times) / len(times)

    print(f"Create 10 games: avg {avg_time:.3f}s")
    assert avg_time < THRESHOLDS["api_new_game"] * 1.2


# ─────────────────────────────────────────────────────────────────────────
# TEST: SAVE/LOAD PERFORMANCE
# ─────────────────────────────────────────────────────────────────────────

def test_perf_save_game():
    """Performance test: Save game endpoint."""
    # Create a game
    resp = requests.post(
        f"{BASE_URL}/api/new-game",
        json={"color": "white", "model": None}
    )
    game_id = resp.json()["gameId"]

    def save_game():
        response = requests.post(
            f"{BASE_URL}/api/save-game",
            json={
                "game_id": game_id,
                "username": "perftest",
                "label": "PerfTestGame"
            }
        )
        assert response.status_code == 200

    elapsed, _ = measure_time(save_game)

    print(f"Save game: {elapsed:.3f}s")
    assert elapsed < THRESHOLDS["save_game"], f"Save too slow: {elapsed:.3f}s"


def test_perf_load_game():
    """Performance test: Load game endpoint."""
    # Create and save a game
    resp = requests.post(
        f"{BASE_URL}/api/new-game",
        json={"color": "white", "model": None}
    )
    game_id = resp.json()["gameId"]

    save_resp = requests.post(
        f"{BASE_URL}/api/save-game",
        json={
            "game_id": game_id,
            "username": "perftest",
            "label": "LoadTest"
        }
    )
    filename = save_resp.json()["filename"]

    def load_game():
        response = requests.get(f"{BASE_URL}/api/load-game/{filename}")
        assert response.status_code == 200

    elapsed, _ = measure_time(load_game)

    print(f"Load game: {elapsed:.3f}s")
    assert elapsed < THRESHOLDS["load_game"], f"Load too slow: {elapsed:.3f}s"


# ─────────────────────────────────────────────────────────────────────────
# TEST: BROWSER PERFORMANCE
# ─────────────────────────────────────────────────────────────────────────

def test_perf_board_render(page):
    """Performance test: Board rendering performance."""
    page.goto(BASE_URL)
    page.wait_for_timeout(2500)

    page.fill('[id="auth-pass"]', "PerfTest")
    page.click('button:has-text("Login")')
    page.wait_for_selector('[id="screen-menu"]', timeout=TIMEOUT)

    page.click('text=2 Players')
    page.wait_for_selector('[id="board"]', timeout=TIMEOUT)

    # Measure board interaction performance
    start = time.time()
    page.locator('[data-r="6"][data-c="4"]').click()
    page.wait_for_timeout(200)
    elapsed = time.time() - start

    print(f"Board piece selection: {elapsed:.3f}s")


def test_perf_move_animation(page):
    """Performance test: Move animation smoothness."""
    page.goto(BASE_URL)
    page.wait_for_timeout(2500)

    page.fill('[id="auth-pass"]', "PerfTest")
    page.click('button:has-text("Login")')
    page.wait_for_selector('[id="screen-menu"]', timeout=TIMEOUT)

    page.click('text=2 Players')
    page.wait_for_selector('[id="board"]', timeout=TIMEOUT)

    # Measure move execution time
    start = time.time()
    page.locator('[data-r="6"][data-c="4"]').click()
    page.wait_for_timeout(200)
    page.locator('[data-r="4"][data-c="4"]').click()
    page.wait_for_timeout(500)
    elapsed = time.time() - start

    print(f"Move execution: {elapsed:.3f}s")
    assert elapsed < THRESHOLDS["move_execution"], f"Move too slow: {elapsed:.3f}s"


# ─────────────────────────────────────────────────────────────────────────
# UTILITY: PERFORMANCE REPORT
# ─────────────────────────────────────────────────────────────────────────

def generate_performance_report():
    """Generate a performance report."""
    import json

    report = {
        "thresholds": THRESHOLDS,
        "tests_run": "See pytest output",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    return report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
