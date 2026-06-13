# Complete Testing Guide - Duck Chess

Comprehensive testing setup covering unit, integration, E2E, visual regression, and performance tests.

---

## 📊 Test Suite Overview

| Test Type | Files | Tests | Speed | CI/CD |
|-----------|-------|-------|-------|-------|
| **Unit/Integration** | 3 | 111 | Fast (5s) | ✅ Required |
| **E2E** | 3 | 50+ | Medium (30s) | ✅ Optional |
| **Visual Regression** | 1 | 20+ | Medium (30s) | ✅ Optional |
| **Performance** | 1 | 15+ | Medium (20s) | ✅ Optional |
| **Code Quality** | - | - | Fast (10s) | ✅ Optional |

**Total**: 200+ tests | ~100 seconds | Fully automated

---

## 🚀 Quick Start

### 1. Install All Dependencies

```bash
pip install -r requirements.txt
pip install playwright
playwright install chromium
```

### 2. Start Web Server

```bash
python -m uvicorn web_ui.server:app --host 127.0.0.1 --port 7890
```

### 3. Run All Tests

```bash
# All tests
pytest tests/ -v

# Only unit/integration (no server needed)
pytest tests/test_web_ui_*.py tests/test_logic_*.py -v

# Only E2E (requires server)
pytest tests/test_e2e_*.py -v

# Only visual regression
pytest tests/test_visual_regression.py -v

# Only performance
pytest tests/test_performance.py -v
```

---

## 📋 Test Breakdown

### Backend Unit & Integration Tests

**No server required** — Fast, runs in CI pipeline.

```bash
pytest tests/test_web_ui_server.py -v              # 35 tests (~2s)
pytest tests/test_web_ui_integration.py -v         # 21 tests (~2s)
pytest tests/test_logic_comprehensive.py -v        # 55 tests (~1s)
```

**Coverage**: API endpoints, game flows, logic engine

### E2E Browser Tests

**Requires server running** — Tests actual user interactions.

```bash
pytest tests/test_e2e_auth_and_menu.py -v          # 12 tests (~10s)
pytest tests/test_e2e_gameplay.py -v               # 22 tests (~15s)
pytest tests/test_e2e_save_replay.py -v            # 16 tests (~10s)
```

**Coverage**: Login flow, gameplay, save/load, replay

### Visual Regression Tests

**Requires server running** — Captures and compares screenshots.

```bash
pytest tests/test_visual_regression.py -v          # 20+ tests (~30s)
```

**Coverage**: UI appearance on desktop, tablet, mobile

### Performance Tests

**Requires server running** — Measures latency and throughput.

```bash
pytest tests/test_performance.py -v                # 15+ tests (~20s)
```

**Coverage**: Page load, API response times, concurrent sessions

---

## 📈 Running Tests Locally

### Option 1: All Tests (Complete Suite)

```bash
# Terminal 1: Start server
python -m uvicorn web_ui.server:app --host 127.0.0.1 --port 7890

# Terminal 2: Run all tests
pytest tests/ -v --tb=short
```

**Time**: ~2 minutes  
**Coverage**: Everything

### Option 2: Fast Feedback Loop (Unit Only)

```bash
# No server needed
pytest tests/test_web_ui_server.py tests/test_web_ui_integration.py tests/test_logic_comprehensive.py -v
```

**Time**: ~10 seconds  
**Coverage**: Core functionality

### Option 3: E2E Only (With Server)

```bash
# Terminal 1: Start server
python -m uvicorn web_ui.server:app --host 127.0.0.1 --port 7890

# Terminal 2: Run E2E tests
pytest tests/test_e2e_*.py -v
```

**Time**: ~40 seconds  
**Coverage**: User flows

### Option 4: Watch Mode (Auto-rerun on Changes)

```bash
# Install pytest-watch
pip install pytest-watch

# Run unit tests in watch mode
ptw tests/test_web_ui_*.py tests/test_logic_*.py -- -v
```

---

## 🔄 CI/CD Pipeline

Tests automatically run on every push via GitHub Actions (`.github/workflows/tests.yml`).

### Pipeline Stages

1. **Backend Tests** (Always Required)
   - Python 3.11 & 3.12
   - Unit + integration tests
   - Must pass to merge

2. **Code Quality** (Optional)
   - Black, isort, Flake8
   - Linting checks
   - Warnings only (not blocking)

3. **E2E Tests** (Optional)
   - Browser-based tests
   - May be flaky
   - Informational

4. **Visual Regression** (Optional)
   - Screenshot comparisons
   - Baseline establishment
   - Informational

5. **Performance Tests** (Optional)
   - Latency benchmarks
   - Throughput checks
   - Informational

6. **Coverage Report** (Always Runs)
   - Generated on every run
   - Uploaded to Codecov
   - Historical tracking

### View Pipeline

```bash
# Run locally exactly as CI does
act -j backend-tests

# View GitHub Actions runs
gh workflow list
gh run list
```

---

## 📊 Test Coverage

### Current Coverage

```
web_ui/server.py:        ~90% (API endpoints)
DuckChess_Game/Logic:    ~85% (Game engine)
web_ui/index.html:       Browser tests (E2E)
```

### Generate Coverage Report

```bash
pytest tests/test_web_ui_*.py tests/test_logic_*.py \
  --cov=web_ui \
  --cov=DuckChess_Game.Logic \
  --cov-report=html \
  --cov-report=term

# Open coverage report
open htmlcov/index.html
```

---

## 🎯 Performance Targets

Tests verify these latency thresholds:

| Operation | Target | Test |
|-----------|--------|------|
| Page load | <3.0s | `test_perf_page_load` |
| Auth flow | <2.5s | `test_perf_auth_to_menu` |
| Game init | <3.0s | `test_perf_game_load_*` |
| Move exec | <1.0s | `test_perf_move_animation` |
| Save game | <2.0s | `test_perf_save_game` |
| Load game | <2.0s | `test_perf_load_game` |
| API models | <0.5s | `test_perf_api_models` |
| API move | <0.5s | `test_perf_api_legal_moves` |

View current performance:
```bash
pytest tests/test_performance.py -v -s
```

---

## 🐛 Debugging Failed Tests

### View Detailed Output

```bash
# Verbose output with full tracebacks
pytest tests/test_e2e_auth_and_menu.py -v -s

# Show local variables on failure
pytest tests/test_e2e_auth_and_menu.py -v --tb=long

# Stop on first failure
pytest tests/test_e2e_auth_and_menu.py -x
```

### E2E Debugging

```bash
# See browser (headless=false)
HEADED=1 pytest tests/test_e2e_auth_and_menu.py -v

# Take screenshots on failure
pytest tests/test_e2e_auth_and_menu.py -v --screenshot on_failure

# Pause execution to inspect
# Add page.pause() in your test
```

### Performance Debugging

```bash
# Run with timing info
pytest tests/test_performance.py -v -s

# Profile specific endpoint
python -c "
import time, requests
start = time.time()
r = requests.get('http://localhost:7890/api/models')
print(f'Response time: {time.time()-start:.3f}s')
print(f'Status: {r.status_code}')
"
```

---

## 📝 Writing New Tests

### Add Unit Test

```python
# tests/test_new_feature.py
def test_new_api_endpoint():
    """Test new endpoint."""
    response = requests.post("http://localhost:7890/api/new-endpoint", json={...})
    assert response.status_code == 200
    assert response.json()["expected_field"] == "value"
```

### Add E2E Test

```python
# tests/test_e2e_new_feature.py
def test_new_ui_feature(page):
    """Test new UI feature."""
    page.goto("http://localhost:7890")
    page.wait_for_timeout(2500)
    
    page.fill('[id="auth-pass"]', "TestUser")
    page.click('button:has-text("Login")')
    
    # Your test...
    element = page.locator('[id="new-feature"]')
    expect(element).to_be_visible()
```

### Add Performance Test

```python
# tests/test_performance.py
def test_perf_new_operation():
    """Performance test for new operation."""
    def operation():
        response = requests.get("http://localhost:7890/api/new-endpoint")
        assert response.status_code == 200
    
    elapsed, _ = measure_time(operation)
    assert elapsed < 1.0  # threshold
```

---

## 🚨 Common Issues

### "Browser not found"
```bash
playwright install chromium
```

### "Connection refused" (Port 7890)
```bash
# Ensure server is running
python -m uvicorn web_ui.server:app --host 127.0.0.1 --port 7890
```

### "Timeout waiting for element"
- Server may be slow
- Selector may be wrong
- Increase timeout: `page.wait_for_selector(..., timeout=10000)`

### "Performance threshold exceeded"
- System under load
- Run isolated test: `pytest tests/test_performance.py::test_perf_page_load -v`
- Verify server has resources

### Tests pass locally but fail in CI
- Increase timeouts for CI environment
- Check if all dependencies are installed
- Verify Python version matches

---

## 📦 Test Dependencies

All included in `requirements.txt`:

```
pytest==7.4.3              # Test runner
pytest-cov==4.1.0         # Coverage reporting
httpx==0.27.0             # HTTP client
pytest-asyncio==0.24.0    # Async support
playwright==1.40.0        # Browser automation
requests==2.31.0          # HTTP library
```

Install with:
```bash
pip install -r requirements.txt
pip install playwright
playwright install chromium
```

---

## 🎓 Best Practices

1. **Run unit tests first** (fast feedback)
2. **E2E tests for critical paths** (not 100% coverage)
3. **Performance tests for regressions** (catch slowdowns early)
4. **Visual tests for UI changes** (prevent accidental regressions)
5. **CI/CD for automation** (catch issues before merge)

---

## 📚 Documentation

- **E2E Tests**: [`docs/E2E_TESTS.md`](E2E_TESTS.md)
- **Backend Tests**: [`docs/WEB_UI_TEST_SUMMARY.md`](WEB_UI_TEST_SUMMARY.md)
- **Logic Tests**: See test file docstrings
- **CI/CD**: [`.github/workflows/tests.yml`](../.github/workflows/tests.yml)

---

## 🎯 Next Steps

1. ✅ Install all dependencies
2. ✅ Start web server
3. ✅ Run unit tests: `pytest tests/test_web_ui_server.py -v`
4. ✅ Run E2E tests: `pytest tests/test_e2e_auth_and_menu.py -v`
5. ✅ Run performance tests: `pytest tests/test_performance.py -v`
6. ✅ View coverage: `open htmlcov/index.html`
7. ✅ Check CI: `gh workflow view tests.yml`

---

**Status**: Complete testing infrastructure ✅  
**Coverage**: 200+ tests across all layers  
**Automation**: Fully integrated with CI/CD  
**Ready for production** 🚀
