# VFS-Bot Test Suite

This directory contains the complete test suite for VFS-Bot, organized by test type and purpose.

## Directory Structure

```
tests/
├── README.md                    ← This file
├── conftest.py                  ← Global pytest configuration and fixtures
├── __init__.py                  ← Package marker
├── .env.test.example            ← Example environment variables for tests
│
├── unit/                        ← Unit tests (117 files)
│   ├── __init__.py
│   ├── test_alert_service.py
│   ├── test_auth.py
│   ├── test_bot.py
│   ├── test_captcha.py
│   ├── test_database.py
│   └── ... (all isolated component tests)
│
├── integration/                 ← Integration tests (9 files)
│   ├── __init__.py
│   ├── conftest.py              ← Integration-specific fixtures
│   ├── README.md                ← Detailed integration test docs
│   ├── test_api_chain.py        ← API endpoint chain tests
│   ├── test_api_flow.py
│   ├── test_bot_integration.py  ← Bot service integration
│   ├── test_database_integration.py
│   ├── test_middleware_chain.py
│   ├── test_payment_integration.py
│   ├── test_redis_rate_limiting.py
│   ├── test_user_appointment_flow.py
│   ├── test_webhook_flow.py
│   └── test_websocket.py        ← WebSocket endpoint tests
│
├── e2e/                         ← Python end-to-end tests
│   ├── __init__.py
│   ├── test_booking_flow.py
│   └── test_booking_workflow_e2e.py
│
└── load/                        ← Load and performance tests
    ├── __init__.py
    └── test_concurrent_load.py
```

## Frontend Tests

Frontend tests are located in a separate directory structure:

```
frontend/
├── e2e/                         ← Playwright browser tests
│   ├── login.spec.ts
│   ├── dashboard.spec.ts
│   └── users.spec.ts
│
└── src/__tests__/               ← Vitest unit tests
    ├── setup.ts
    ├── components/
    │   ├── Button.test.tsx
    │   └── Input.test.tsx
    ├── hooks/
    │   ├── useApi.test.tsx
    │   ├── useAsyncAction.test.ts
    │   └── useWebSocket.test.ts
    ├── pages/
    │   └── Login.test.tsx
    └── utils/
        ├── creditCard.test.ts
        ├── env.test.ts
        ├── styleUtils.test.ts
        └── validators.test.ts
```

## Test Types

### Unit Tests (`tests/unit/`)

**Purpose:** Test individual components in isolation with mocked dependencies.

**Characteristics:**
- Fast execution (milliseconds per test)
- No external dependencies (database, Redis, etc.)
- Use mocks and stubs extensively
- Run by default with `pytest`

**Examples:**
- `test_auth.py` - Authentication logic
- `test_encryption.py` - Encryption utilities
- `test_validators.py` - Input validation functions

### Integration Tests (`tests/integration/`)

**Purpose:** Test interactions between multiple components with real dependencies.

**Characteristics:**
- Require PostgreSQL database
- Some tests require Redis
- Test actual service interactions
- Slower than unit tests
- Marked with `@pytest.mark.integration`

**Examples:**
- `test_api_chain.py` - HTTP endpoint chains
- `test_database_integration.py` - Real database operations
- `test_websocket.py` - WebSocket authentication and messaging
- `test_redis_rate_limiting.py` - Redis-based rate limiting

### End-to-End Tests (`tests/e2e/`)

**Purpose:** Test complete user workflows from start to finish.

**Characteristics:**
- Test full application flows
- May require browser automation
- Slowest test type
- Marked with `@pytest.mark.e2e`

**Examples:**
- `test_booking_flow.py` - Complete booking workflow
- `test_booking_workflow_e2e.py` - Extended booking scenarios

### Load Tests (`tests/load/`)

**Purpose:** Test system behavior under concurrent load.

**Characteristics:**
- Test concurrent operations
- Validate thread safety
- Test connection pooling
- Measure performance

**Examples:**
- `test_concurrent_load.py` - Concurrent database operations

## Running Tests

### Backend (Python) Tests

#### Run all unit tests (default):
```bash
pytest
# or explicitly
pytest -v -m "not integration and not e2e"
```

#### Run specific test types:
```bash
# Unit tests only
pytest -v -m unit tests/unit/

# Integration tests only (requires PostgreSQL)
pytest -v -m integration tests/integration/

# End-to-end tests (requires browser/full stack)
pytest -v -m e2e tests/e2e/

# Load tests
pytest -v tests/load/
```

#### Run specific test files:
```bash
# Single file
pytest -v tests/unit/test_auth.py

# Specific test function
pytest -v tests/unit/test_auth.py::test_password_hashing

# Multiple files
pytest -v tests/unit/test_auth.py tests/unit/test_encryption.py
```

#### Run with coverage:
```bash
pytest --cov=src --cov-report=html --cov-report=term-missing
```

### Frontend Tests

#### Vitest unit tests:
```bash
cd frontend
npm test
# or
npm run test:unit
```

#### Playwright E2E tests:
```bash
cd frontend
npx playwright test
# or
npm run test:e2e
```

#### Run Playwright tests in UI mode:
```bash
cd frontend
npx playwright test --ui
```

## Test Markers

Tests are marked with pytest markers to enable selective execution:

- `@pytest.mark.unit` - Unit tests (isolated components)
- `@pytest.mark.integration` - Integration tests (require external services)
- `@pytest.mark.e2e` - End-to-end tests (full workflows)
- `@pytest.mark.slow` - Slow-running tests
- `@pytest.mark.security` - Security-related tests

### Using markers:
```bash
# Run only unit tests
pytest -v -m unit

# Run everything except integration and e2e
pytest -v -m "not integration and not e2e"

# Run security tests
pytest -v -m security

# Exclude slow tests
pytest -v -m "not slow"
```

## Environment Variables

### Backend Tests

Tests use environment variables defined in `tests/.env.test.example`. Copy this to `tests/.env.test` and customize:

```bash
cp tests/.env.test.example tests/.env.test
```

**Required variables:**
- `TEST_DATABASE_URL` - PostgreSQL connection string for tests
- `API_SECRET_KEY` - Secret key for JWT tokens
- `ENCRYPTION_KEY` - Encryption key for sensitive data

**Optional variables:**
- `REDIS_URL` - Redis connection (for rate limiting tests)
- `TEST_REDIS_URL` - Separate Redis instance for tests

### Frontend Tests

Frontend tests use environment variables from `frontend/.env.test`:

```bash
# API endpoints
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```

## Prerequisites

### For Unit Tests
```bash
pip install -e ".[dev]"
```

### For Integration Tests

**PostgreSQL 16+:**
```bash
# Using Docker
docker run -d -p 5432:5432 \
  -e POSTGRES_PASSWORD=test_pass \
  -e POSTGRES_DB=vfs_test \
  postgres:16

# Set environment variable
export TEST_DATABASE_URL="postgresql://postgres:test_pass@localhost:5432/vfs_test"
```

**Redis (optional, for rate limiting tests):**
```bash
# Using Docker
docker run -d -p 6379:6379 redis:7-alpine

# Set environment variable
export REDIS_URL="redis://localhost:6379/0"
```

### For E2E Tests

Install browser drivers:
```bash
# For Playwright (frontend)
cd frontend
npx playwright install

# For Selenium (if used in backend E2E)
pip install selenium
```

## Configuration Files

- **`pyproject.toml`** - Pytest configuration (`[tool.pytest.ini_options]` section)
  - Test discovery patterns
  - Coverage settings
  - Marker definitions
  - Warning filters

- **`tests/conftest.py`** - Global pytest fixtures
  - Environment setup
  - Database fixtures
  - Mock objects
  - Cleanup handlers

- **`tests/integration/conftest.py`** - Integration-specific fixtures
  - Real database connections
  - Repository instances
  - Test data setup

- **`frontend/vitest.config.ts`** - Vitest configuration
  - Test environment
  - Module resolution
  - Coverage settings

- **`frontend/playwright.config.ts`** - Playwright configuration
  - Browser settings
  - Test timeout
  - Screenshot/video capture

## CI/CD Integration

### GitHub Actions Workflows

Tests run automatically on pull requests and pushes:

#### `.github/workflows/ci.yml` - Main CI
```bash
pytest tests/ --cov=src --cov-report=xml
```

#### `.github/workflows/integration-tests.yml` - Integration & E2E
```bash
# Integration tests
pytest -v -m integration tests/integration/

# E2E tests
pytest -v -m e2e tests/e2e/
```

## Best Practices

### Writing Tests

1. **Use descriptive names:**
   ```python
   def test_user_login_with_invalid_credentials_returns_401():
       ...
   ```

2. **Follow AAA pattern (Arrange, Act, Assert):**
   ```python
   def test_example():
       # Arrange: Set up test data
       user = create_test_user()

       # Act: Execute the code being tested
       result = authenticate_user(user.username, "wrong_password")

       # Assert: Verify the outcome
       assert result is None
   ```

3. **Use fixtures for common setup:**
   ```python
   @pytest.fixture
   def test_user():
       return User(username="test", email="test@example.com")

   def test_user_creation(test_user):
       assert test_user.username == "test"
   ```

4. **Mark tests appropriately:**
   ```python
   @pytest.mark.integration
   @pytest.mark.asyncio
   async def test_database_connection():
       ...
   ```

5. **Clean up resources:**
   ```python
   @pytest.fixture
   async def database():
       db = await create_test_database()
       yield db
       await db.cleanup()
   ```

### Test Isolation

- Unit tests should NOT depend on external services
- Use mocks for external dependencies in unit tests
- Integration tests should use separate test databases
- Clean up test data after each test
- Don't rely on test execution order

### Performance

- Keep unit tests fast (< 100ms per test)
- Use fixtures to avoid repeated setup
- Mark slow tests with `@pytest.mark.slow`
- Run quick tests frequently during development
- Run full suite before committing

## Debugging Tests

### Run with verbose output:
```bash
pytest -vv tests/unit/test_auth.py
```

### Show print statements:
```bash
pytest -s tests/unit/test_auth.py
```

### Drop into debugger on failure:
```bash
pytest --pdb tests/unit/test_auth.py
```

### Run last failed tests:
```bash
pytest --lf
```

### Show fixture setup:
```bash
pytest --setup-show tests/unit/test_auth.py
```

## Coverage Reports

### Generate HTML coverage report:
```bash
pytest --cov=src --cov-report=html
# Open htmlcov/index.html in browser
```

### View coverage in terminal:
```bash
pytest --cov=src --cov-report=term-missing
```

### Coverage requirements:
- Minimum coverage: 80% (configured in `pyproject.toml`)
- Aim for 80%+ on new code
- Critical paths should have 100% coverage

## Troubleshooting

### Tests can't find modules
- Ensure you're in the project root directory
- Check that `PYTHONPATH` includes the project root
- The `conftest.py` adds the project to `sys.path` automatically

### Database connection errors
- Verify PostgreSQL is running
- Check `TEST_DATABASE_URL` environment variable
- Ensure test database exists and is accessible

### Slow test execution
- Run only unit tests: `pytest -m "not integration and not e2e"`
- Use parallel execution: `pytest -n auto` (requires pytest-xdist)
- Skip slow tests: `pytest -m "not slow"`

### Import errors after test reorganization
- No action needed - `conftest.py` handles path setup
- If you encounter issues, verify `conftest.py` exists and contains path setup

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [Vitest documentation](https://vitest.dev/)
- [Playwright documentation](https://playwright.dev/)
- [Integration Test README](integration/README.md) - Detailed integration test guide
