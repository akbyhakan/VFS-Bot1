"""Unit tests for AccountPool service."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.session.account_pool import AccountPool, PooledAccount


@pytest.fixture
def mock_db():
    """Create mock database."""
    db = MagicMock()
    return db


@pytest.fixture
def mock_account_pool_repo():
    """Create mock AccountPoolRepository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def account_pool(mock_db, mock_account_pool_repo):
    """Create AccountPool instance with mocked dependencies."""
    with patch("src.services.session.account_pool.AccountPoolRepository", return_value=mock_account_pool_repo):
        pool = AccountPool(
            db=mock_db,
            cooldown_seconds=60,
            quarantine_seconds=300,
            max_failures=3,
        )
        pool.repo = mock_account_pool_repo
        return pool


@pytest.fixture
def sample_account_dict():
    """Create sample account dictionary."""
    now = datetime.now(timezone.utc)
    return {
        "id": 1,
        "email": "test@example.com",
        "password": "decrypted_password",
        "phone": "+1234567890",
        "status": "available",
        "last_used_at": now - timedelta(hours=1),
        "cooldown_until": None,
        "quarantine_until": None,
        "consecutive_failures": 0,
        "total_uses": 5,
        "is_active": True,
        "created_at": now - timedelta(days=1),
        "updated_at": now,
    }


@pytest.mark.asyncio
async def test_load_accounts(account_pool, mock_account_pool_repo, sample_account_dict):
    """Test loading accounts from database."""
    mock_account_pool_repo.get_available_accounts.return_value = [sample_account_dict]

    count = await account_pool.load_accounts()

    assert count == 1
    mock_account_pool_repo.get_available_accounts.assert_called_once()


@pytest.mark.asyncio
async def test_acquire_account_success(account_pool, mock_account_pool_repo, sample_account_dict):
    """Test successfully acquiring an account."""
    mock_account_pool_repo.get_available_accounts.return_value = [sample_account_dict]
    mock_account_pool_repo.mark_account_in_use.return_value = True

    account = await account_pool.acquire_account()

    assert account is not None
    assert account.id == 1
    assert account.email == "test@example.com"
    mock_account_pool_repo.mark_account_in_use.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_acquire_account_no_available(account_pool, mock_account_pool_repo):
    """Test acquiring when no accounts available."""
    mock_account_pool_repo.get_available_accounts.return_value = []

    account = await account_pool.acquire_account()

    assert account is None


@pytest.mark.asyncio
async def test_acquire_account_lru_ordering(account_pool, mock_account_pool_repo):
    """Test that LRU account is selected (least recently used first)."""
    now = datetime.now(timezone.utc)
    
    # Create accounts with different last_used_at times
    account1 = {
        "id": 1,
        "email": "old@example.com",
        "password": "pass1",
        "phone": "+1111111111",
        "status": "available",
        "last_used_at": now - timedelta(hours=5),  # Oldest
        "cooldown_until": None,
        "quarantine_until": None,
        "consecutive_failures": 0,
        "total_uses": 10,
        "is_active": True,
        "created_at": now - timedelta(days=1),
        "updated_at": now,
    }
    
    account2 = {
        "id": 2,
        "email": "recent@example.com",
        "password": "pass2",
        "phone": "+2222222222",
        "status": "available",
        "last_used_at": now - timedelta(hours=1),  # Recent
        "cooldown_until": None,
        "quarantine_until": None,
        "consecutive_failures": 0,
        "total_uses": 2,
        "is_active": True,
        "created_at": now - timedelta(days=1),
        "updated_at": now,
    }

    # Repository should return accounts in LRU order (oldest first)
    mock_account_pool_repo.get_available_accounts.return_value = [account1, account2]
    mock_account_pool_repo.mark_account_in_use.return_value = True

    account = await account_pool.acquire_account()

    # Should select the least recently used (account1)
    assert account.id == 1
    assert account.email == "old@example.com"


@pytest.mark.asyncio
async def test_release_account_success(account_pool, mock_account_pool_repo):
    """Test releasing account with success result."""
    mock_account_pool_repo.release_account.return_value = True

    result = await account_pool.release_account(1, "success")

    assert result is True
    mock_account_pool_repo.release_account.assert_called_once()
    # Verify cooldown was set
    call_args = mock_account_pool_repo.release_account.call_args
    assert call_args[1]["result_status"] == "success"
    assert call_args[1]["cooldown_until"] is not None


@pytest.mark.asyncio
async def test_release_account_no_slot(account_pool, mock_account_pool_repo):
    """Test releasing account with no_slot result."""
    mock_account_pool_repo.release_account.return_value = True

    result = await account_pool.release_account(1, "no_slot")

    assert result is True
    # Should go to cooldown
    call_args = mock_account_pool_repo.release_account.call_args
    assert call_args[1]["result_status"] == "no_slot"
    assert call_args[1]["cooldown_until"] is not None


@pytest.mark.asyncio
async def test_release_account_login_fail_below_max(account_pool, mock_account_pool_repo):
    """Test releasing account with login failure below max failures."""
    # Simulate account with 1 consecutive failure (below max of 3)
    mock_account_pool_repo.get_account_by_id.return_value = {
        "consecutive_failures": 1,
    }
    mock_account_pool_repo.release_account.return_value = True

    result = await account_pool.release_account(1, "login_fail", "Login error")

    assert result is True
    # Should NOT quarantine (only 2 failures total)
    call_args = mock_account_pool_repo.release_account.call_args
    assert call_args[1]["result_status"] == "login_fail"
    assert "quarantine_until" not in call_args[1] or call_args[1]["quarantine_until"] is None


@pytest.mark.asyncio
async def test_release_account_login_fail_quarantine(account_pool, mock_account_pool_repo):
    """Test releasing account with login failure reaching max failures."""
    # Simulate account with 2 consecutive failures (will hit max of 3)
    mock_account_pool_repo.get_account_by_id.return_value = {
        "consecutive_failures": 2,
    }
    mock_account_pool_repo.release_account.return_value = True

    result = await account_pool.release_account(1, "login_fail", "Login error")

    assert result is True
    # Should quarantine (3 failures total)
    call_args = mock_account_pool_repo.release_account.call_args
    assert call_args[1]["result_status"] == "login_fail"
    assert call_args[1]["quarantine_until"] is not None


@pytest.mark.asyncio
async def test_release_account_banned(account_pool, mock_account_pool_repo):
    """Test releasing account with banned result."""
    mock_account_pool_repo.release_account.return_value = True

    result = await account_pool.release_account(1, "banned")

    assert result is True
    # Should quarantine with extended period (2x normal)
    call_args = mock_account_pool_repo.release_account.call_args
    assert call_args[1]["result_status"] == "banned"
    assert call_args[1]["quarantine_until"] is not None


@pytest.mark.asyncio
async def test_get_wait_time_no_cooldowns(account_pool, mock_account_pool_repo):
    """Test get_wait_time when no accounts in cooldown."""
    mock_account_pool_repo.get_next_available_cooldown_time.return_value = None

    wait_time = await account_pool.get_wait_time()

    assert wait_time == 0.0


@pytest.mark.asyncio
async def test_get_wait_time_with_cooldown(account_pool, mock_account_pool_repo):
    """Test get_wait_time with accounts in cooldown."""
    # Cooldown expires in 30 seconds
    future_time = datetime.now(timezone.utc) + timedelta(seconds=30)
    mock_account_pool_repo.get_next_available_cooldown_time.return_value = future_time

    wait_time = await account_pool.get_wait_time()

    # Should be approximately 30 seconds (allow small timing variance)
    assert 29 <= wait_time <= 31


@pytest.mark.asyncio
async def test_get_pool_status(account_pool, mock_account_pool_repo):
    """Test getting pool status."""
    mock_account_pool_repo.get_pool_stats.return_value = {
        "total_active": 10,
        "available": 5,
        "in_use": 2,
        "in_cooldown": 2,
        "quarantined": 1,
        "avg_uses": 15.5,
        "max_uses": 50,
    }
    mock_account_pool_repo.get_next_available_cooldown_time.return_value = None

    status = await account_pool.get_pool_status()

    assert status["total_active"] == 10
    assert status["available"] == 5
    assert status["in_cooldown"] == 2
    assert status["quarantined"] == 1
    assert status["wait_time_seconds"] == 0.0
    assert status["config"]["cooldown_seconds"] == 60
    assert status["config"]["max_failures"] == 3


@pytest.mark.asyncio
async def test_acquire_release_thread_safety(account_pool, mock_account_pool_repo, sample_account_dict):
    """Test thread safety of acquire and release operations."""
    # Simulate concurrent acquire/release
    mock_account_pool_repo.get_available_accounts.return_value = [sample_account_dict]
    mock_account_pool_repo.mark_account_in_use.return_value = True
    mock_account_pool_repo.release_account.return_value = True

    # Create multiple concurrent acquire tasks
    async def acquire_and_release():
        account = await account_pool.acquire_account()
        if account:
            await account_pool.release_account(account.id, "success")

    # Run 5 concurrent operations
    tasks = [acquire_and_release() for _ in range(5)]
    await asyncio.gather(*tasks)

    # Verify all operations completed without errors
    # Lock should have prevented race conditions
    assert mock_account_pool_repo.mark_account_in_use.call_count == 5
