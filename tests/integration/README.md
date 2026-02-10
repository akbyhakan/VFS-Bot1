# Integration Tests

This directory contains integration tests that require real external services (PostgreSQL, Redis) to run.

## Overview

Integration tests are different from unit tests in that they:
- **Use real databases** instead of mocks
- **Test actual service interactions** instead of isolated components
- **Validate end-to-end flows** with real data persistence
- **Require external dependencies** to be running

## Test Layers

### Layer 1: Shared Fixtures (`conftest.py`)
Provides reusable fixtures for all integration tests:
- `test_db`: Real PostgreSQL connection with automatic cleanup
- `user_repo`: Real UserRepository instance
- `appointment_repo`: Real AppointmentRepository instance
- `test_user`: Pre-created test user for convenience
- Auto-skip mechanism when database is unavailable

### Layer 2: Service Layer Tests (`test_user_appointment_flow.py`)
Tests service-level operations with real database:
- ✅ Full user creation flow with encryption
- ✅ Duplicate appointment prevention
- ✅ Concurrent user creation (race condition testing)
- ✅ Cascade delete operations

### Layer 3: API Endpoint Chain Tests (`test_api_chain.py`)
Tests FastAPI endpoint chains with TestClient:
- ✅ Health endpoint chain (`/health` → `/health/ready` → `/health/live`)
- ✅ Login rate limiting enforcement
- ✅ Bot lifecycle operations
- ✅ User CRUD operations

### Layer 4: Redis Rate Limiting Tests (`test_redis_rate_limiting.py`)
Tests Redis-based rate limiting with Lua script atomicity:
- ✅ Atomic rate limiting (5 OK → 6th blocked)
- ✅ Rate limit window expiry
- ✅ Independent identifier limits
- ✅ Concurrent attempt handling (no race conditions)

## Running Integration Tests

### Prerequisites

1. **PostgreSQL** (version 15+)
   ```bash
   docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=test_pass postgres:15
   ```

2. **Redis** (version 7+, optional)
   ```bash
   docker run -d -p 6379:6379 redis:7-alpine
   ```

3. **Environment Variables**
   ```bash
   export TEST_DATABASE_URL="postgresql://user:pass@localhost:5432/vfs_bot_test"
   export REDIS_URL="redis://localhost:6379"
   export ENV=testing
   ```

### Run Integration Tests Only

```bash
# Run all integration tests
pytest -v -m integration

# Run specific integration test file
pytest -v tests/integration/test_user_appointment_flow.py

# Run integration tests with coverage
pytest -v -m integration --cov=src --cov-report=html
```

### Run E2E Tests Only

```bash
# Run all E2E tests
pytest -v -m e2e

# Run specific E2E test
pytest -v tests/e2e/test_booking_workflow_e2e.py
```

### Run All Tests (Unit + Integration + E2E)

```bash
# Run everything
pytest -v

# Skip integration tests (default)
pytest -v -m "not integration and not e2e"
```

## Auto-Skip Behavior

Integration tests automatically skip if:
- `TEST_DATABASE_URL` or `DATABASE_URL` is not set
- PostgreSQL is not running or unreachable
- Connection timeout occurs

Redis tests skip if:
- `REDIS_URL` is not set
- Redis is not running or unreachable

This prevents test failures in CI/CD environments without proper infrastructure.

## CI/CD Integration

The `.github/workflows/integration-tests.yml` workflow:
- Runs on push to `main` and `develop` branches
- Spins up PostgreSQL and Redis services
- Runs database migrations
- Executes integration and E2E tests
- Uploads coverage reports

## Test Database Cleanup

Each test automatically cleans up after itself by:
1. Truncating all test tables after each test
2. Resetting auto-increment IDs
3. Preserving database schema
4. Closing connections properly

Tables cleaned:
- `users`
- `personal_details`
- `appointments`
- `appointment_history`
- `audit_logs`

## Writing New Integration Tests

### Example Integration Test

```python
import pytest
from src.models.database import Database
from src.repositories.user_repository import UserRepository

@pytest.mark.integration
class TestMyFeature:
    @pytest.mark.asyncio
    async def test_my_feature(
        self,
        test_db: Database,
        user_repo: UserRepository
    ):
        # Create test data
        user_id = await user_repo.create({
            "email": "test@example.com",
            "password": "SecurePass123!",
            "center_name": "Istanbul",
        })
        
        # Test your feature
        result = await some_feature(user_id)
        
        # Assert expectations
        assert result is not None
        # Cleanup is automatic!
```

### Best Practices

1. **Always use `@pytest.mark.integration`** for integration tests
2. **Use fixtures** from `conftest.py` instead of creating connections manually
3. **Don't rely on test execution order** - each test should be independent
4. **Clean up is automatic** - don't manually truncate tables
5. **Use descriptive test names** that explain what is being tested
6. **Test both success and failure paths**

## Troubleshooting

### Tests are skipped
- Check that `TEST_DATABASE_URL` is set
- Verify PostgreSQL is running: `pg_isready -h localhost -p 5432`
- Check Redis: `redis-cli ping`

### Connection timeout
- Increase connection timeout in fixtures
- Verify network connectivity to database
- Check firewall rules

### Tests fail randomly
- May indicate race conditions in code
- Use `test_concurrent_user_creation` as template for concurrency testing
- Check for shared state between tests

### Cleanup fails
- Check PostgreSQL permissions
- Verify foreign key constraints are properly configured
- Review migration files

## Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `TEST_DATABASE_URL` | Yes | PostgreSQL connection URL | `postgresql://user:pass@localhost:5432/vfs_bot_test` |
| `REDIS_URL` | Optional | Redis connection URL | `redis://localhost:6379` |
| `ENV` | Yes | Environment name | `testing` |
| `ENCRYPTION_KEY` | Yes | Encryption key for passwords | Auto-generated if not set |
| `API_SECRET_KEY` | Yes | JWT secret key | Auto-generated if not set |

## Further Reading

- [Pytest Documentation](https://docs.pytest.org/)
- [PostgreSQL Docker](https://hub.docker.com/_/postgres)
- [Redis Docker](https://hub.docker.com/_/redis)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
