"""Coverage tests for src/utils/audit_logger.py."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.utils.audit_logger as audit_logger_module
from src.utils.audit_logger import (
    AuditAction,
    AuditEntry,
    AuditLogger,
    audit,
    get_audit_logger,
)


@pytest.fixture(autouse=True)
def reset_global_logger(monkeypatch):
    monkeypatch.setattr(audit_logger_module, "_audit_logger", None)
    yield
    monkeypatch.setattr(audit_logger_module, "_audit_logger", None)


# ── AuditAction enum values ──────────────────────────────────────────────────


def test_audit_action_enum_values():
    assert AuditAction.LOGIN_FAILURE.value == "login_failure"
    assert AuditAction.LOGOUT.value == "logout"
    assert AuditAction.DATA_EXPORTED.value == "data_exported"
    assert AuditAction.DATA_DELETED.value == "data_deleted"
    assert AuditAction.PERMISSION_CHANGED.value == "permission_changed"


# ── AuditLogger.__init__ ─────────────────────────────────────────────────────


def test_init_with_log_file_creates_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "nested" / "dir" / "audit.jsonl"
        logger = AuditLogger(log_file=str(log_path))
        assert logger.log_file is not None
        assert log_path.parent.exists()


def test_init_without_log_file():
    logger = AuditLogger()
    assert logger.log_file is None
    assert logger.db is None


# ── AuditLogger.log ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_log_writes_to_file():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = f.name

    logger = AuditLogger(log_file=path)
    await logger.log(AuditAction.LOGIN_SUCCESS, username="alice")

    with open(path) as f:
        lines = f.readlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["action"] == "login_success"
    assert entry["username"] == "alice"


@pytest.mark.asyncio
async def test_log_persists_to_db():
    mock_conn = AsyncMock()
    mock_db = MagicMock()
    mock_db.get_connection = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=False),
        )
    )

    logger = AuditLogger(db=mock_db)
    await logger.log(AuditAction.USER_CREATED, username="bob")

    mock_conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_log_buffer_overflow_warning():
    logger = AuditLogger()  # no db → buffer mode
    # Fill buffer beyond 100
    for i in range(105):
        await logger.log(AuditAction.BOT_STARTED, username=f"user{i}")

    # Buffer should have been trimmed (well below 105)
    assert len(logger._buffer) < 100


@pytest.mark.asyncio
async def test_log_without_db_appends_to_buffer():
    logger = AuditLogger()
    await logger.log(AuditAction.LOGOUT, username="charlie")
    assert len(logger._buffer) == 1


# ── _write_to_file ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_write_to_file_normal():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = f.name

    logger = AuditLogger(log_file=path)
    entry = AuditEntry(
        action="test_action",
        user_id=1,
        username="test",
        ip_address=None,
        user_agent=None,
        details={},
        timestamp="2024-01-01T00:00:00+00:00",
    )
    await logger._write_to_file(entry)

    with open(path) as f:
        content = f.read()
    assert "test_action" in content


@pytest.mark.asyncio
async def test_write_to_file_exception_handled(tmp_path):
    logger = AuditLogger(log_file=str(tmp_path / "audit.jsonl"))
    entry = AuditEntry(
        action="x",
        user_id=None,
        username=None,
        ip_address=None,
        user_agent=None,
        details={},
        timestamp="2024-01-01T00:00:00+00:00",
    )
    # Make open raise
    with patch("builtins.open", side_effect=OSError("disk full")):
        # Should not raise
        await logger._write_to_file(entry)


# ── _persist ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_persist_normal():
    mock_conn = AsyncMock()
    mock_db = MagicMock()
    mock_db.get_connection = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=False),
        )
    )

    logger = AuditLogger(db=mock_db)
    entry = AuditEntry(
        action="test",
        user_id=1,
        username="u",
        ip_address="1.2.3.4",
        user_agent="ua",
        details={"k": "v"},
        timestamp="2024-01-01T00:00:00+00:00",
    )
    await logger._persist(entry)
    mock_conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_persist_exception_appends_to_buffer():
    mock_db = MagicMock()
    mock_db.get_connection = MagicMock(side_effect=RuntimeError("db down"))

    logger = AuditLogger(db=mock_db)
    entry = AuditEntry(
        action="fail",
        user_id=None,
        username=None,
        ip_address=None,
        user_agent=None,
        details={},
        timestamp="2024-01-01T00:00:00+00:00",
    )
    await logger._persist(entry)
    assert len(logger._buffer) == 1


# ── get_recent ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_recent_without_db_returns_buffer():
    logger = AuditLogger()
    await logger.log(AuditAction.API_KEY_GENERATED, username="dave")
    results = await logger.get_recent(limit=10)
    assert len(results) == 1
    assert results[0]["action"] == "api_key_generated"


@pytest.mark.asyncio
async def test_get_recent_with_db():
    mock_conn = AsyncMock()
    mock_row = {"action": "login_success", "username": "eve"}
    mock_conn.fetch = AsyncMock(return_value=[mock_row])
    mock_db = MagicMock()
    mock_db.get_connection = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=False),
        )
    )

    logger = AuditLogger(db=mock_db)
    results = await logger.get_recent(limit=5)
    assert results == [dict(mock_row)]
    mock_conn.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_get_recent_with_db_filters():
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_db = MagicMock()
    mock_db.get_connection = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=False),
        )
    )

    logger = AuditLogger(db=mock_db)
    results = await logger.get_recent(limit=5, action=AuditAction.LOGIN_SUCCESS, user_id=42)
    assert results == []


@pytest.mark.asyncio
async def test_get_recent_with_db_exception_returns_empty():
    mock_db = MagicMock()
    mock_db.get_connection = MagicMock(side_effect=RuntimeError("db error"))

    logger = AuditLogger(db=mock_db)
    results = await logger.get_recent()
    assert results == []


# ── audit decorator ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_decorator_success():
    @audit(AuditAction.LOGIN_SUCCESS, resource_type="session")
    async def do_login(**kwargs):
        return {"id": 99}

    result = await do_login(username="frank", user_id=1, ip_address="127.0.0.1")
    assert result == {"id": 99}

    al = get_audit_logger()
    assert len(al._buffer) >= 1
    last = al._buffer[-1]
    assert last.action == "login_success"
    assert last.success is True
    assert last.resource_id == "99"


@pytest.mark.asyncio
async def test_audit_decorator_failure():
    @audit(AuditAction.LOGIN_FAILURE, resource_type="session")
    async def fail_login(**kwargs):
        raise ValueError("bad creds")

    with pytest.raises(ValueError):
        await fail_login(username="ghost", user_id=2)

    al = get_audit_logger()
    last = al._buffer[-1]
    assert last.action == "login_failure"
    assert last.success is False


def test_audit_decorator_sync_function():
    @audit(AuditAction.CONFIG_CHANGED)
    def sync_change():
        return "ok"

    # Should just call through without async audit
    result = sync_change()
    assert result == "ok"


# ── get_audit_logger ─────────────────────────────────────────────────────────


def test_get_audit_logger_creates_new():
    al = get_audit_logger()
    assert isinstance(al, AuditLogger)


def test_get_audit_logger_updates_db():
    al1 = get_audit_logger()
    assert al1.db is None

    mock_db = MagicMock()
    al2 = get_audit_logger(db=mock_db)
    assert al2 is al1
    assert al2.db is mock_db


def test_get_audit_logger_updates_log_file(tmp_path):
    al1 = get_audit_logger()
    assert al1.log_file is None

    log_path = str(tmp_path / "audit.jsonl")
    al2 = get_audit_logger(log_file=log_path)
    assert al2 is al1
    assert al2.log_file == Path(log_path)
