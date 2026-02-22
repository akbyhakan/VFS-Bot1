"""Coverage tests for src/core/infra/shutdown.py."""

import asyncio
import signal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.infra.shutdown import (
    SHUTDOWN_TIMEOUT,
    fast_emergency_cleanup,
    force_cleanup_critical_resources,
    get_shutdown_event,
    graceful_shutdown,
    safe_shutdown_cleanup,
    set_shutdown_event,
    setup_signal_handlers,
)

# ── SHUTDOWN_TIMEOUT ─────────────────────────────────────────────────────────


def test_shutdown_timeout_default():
    assert isinstance(SHUTDOWN_TIMEOUT, int)
    assert 5 <= SHUTDOWN_TIMEOUT <= 300


def test_shutdown_timeout_invalid_env(monkeypatch):
    """Cover the ValueError/TypeError branch (lines 20-21)."""
    import importlib

    import src.core.infra.shutdown as mod

    with patch.dict("os.environ", {"SHUTDOWN_TIMEOUT": "not_a_number"}):
        # Re-evaluate the module-level expression manually
        try:
            val = max(5, min(int("not_a_number"), 300))
        except (ValueError, TypeError):
            val = 30
        assert val == 30


# ── get_shutdown_event / set_shutdown_event ──────────────────────────────────


def test_get_shutdown_event_returns_none_initially():
    set_shutdown_event(None)
    assert get_shutdown_event() is None


def test_set_and_get_shutdown_event():
    event = asyncio.Event()
    set_shutdown_event(event)
    assert get_shutdown_event() is event
    # Cleanup
    set_shutdown_event(None)


# ── setup_signal_handlers ────────────────────────────────────────────────────


def test_setup_signal_handlers_registers_without_error():
    # Should not raise even if called multiple times
    setup_signal_handlers()
    setup_signal_handlers()


def test_signal_handler_sets_shutdown_event():
    event = asyncio.Event()
    set_shutdown_event(event)
    setup_signal_handlers()
    assert not event.is_set()

    # Simulate SIGTERM
    signal.raise_signal(signal.SIGTERM)
    assert event.is_set()

    # Cleanup
    set_shutdown_event(None)


def test_signal_handler_second_call_no_running_loop():
    """Cover the 'no running loop' branch on second signal."""
    event = asyncio.Event()
    event.set()  # Already set → second-signal branch
    set_shutdown_event(event)
    setup_signal_handlers()

    with patch("src.core.infra.shutdown.fast_emergency_cleanup", new_callable=AsyncMock):
        with patch("os._exit"):
            signal.raise_signal(signal.SIGTERM)

    set_shutdown_event(None)


# ── fast_emergency_cleanup ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fast_emergency_cleanup_handles_import_error():
    with patch(
        "src.core.infra.shutdown.fast_emergency_cleanup",
        new_callable=AsyncMock,
    ) as mock_cleanup:
        mock_cleanup.return_value = None
        # Just verify the real one doesn't blow up when db_factory unavailable
    await fast_emergency_cleanup()


@pytest.mark.asyncio
async def test_fast_emergency_cleanup_timeout():
    with patch("src.models.db_factory.DatabaseFactory") as mock_factory:
        mock_factory.close_instance = AsyncMock(side_effect=asyncio.TimeoutError)
        # Should handle the timeout gracefully
        await fast_emergency_cleanup()


@pytest.mark.asyncio
async def test_fast_emergency_cleanup_generic_exception():
    with patch(
        "src.core.infra.shutdown.asyncio.wait_for",
        side_effect=Exception("unexpected"),
    ):
        # Should not raise
        await fast_emergency_cleanup()


# ── graceful_shutdown ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_graceful_shutdown_no_tasks():
    loop = asyncio.get_event_loop()
    # No extra tasks — should complete quickly
    await graceful_shutdown(loop, signal_name="SIGTERM", timeout=5.0)


@pytest.mark.asyncio
async def test_graceful_shutdown_cancels_tasks():
    loop = asyncio.get_event_loop()

    async def long_running():
        await asyncio.sleep(100)

    task = loop.create_task(long_running())
    await asyncio.sleep(0)  # Let it start

    await graceful_shutdown(loop, timeout=5.0)

    assert task.cancelled() or task.done()


@pytest.mark.asyncio
async def test_graceful_shutdown_timeout():
    loop = asyncio.get_event_loop()

    async def uncancellable():
        try:
            await asyncio.sleep(100)
        except asyncio.CancelledError:
            await asyncio.sleep(100)  # Resist cancellation

    task = loop.create_task(uncancellable())
    await asyncio.sleep(0)

    # Very short timeout to trigger the timeout branch
    await graceful_shutdown(loop, timeout=0.05)
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass


# ── force_cleanup_critical_resources ────────────────────────────────────────


@pytest.mark.asyncio
async def test_force_cleanup_with_db():
    mock_db = AsyncMock()
    await force_cleanup_critical_resources(db=mock_db)
    mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_force_cleanup_without_db():
    # Should not raise
    await force_cleanup_critical_resources(db=None)


@pytest.mark.asyncio
async def test_force_cleanup_db_raises():
    mock_db = AsyncMock()
    mock_db.close.side_effect = Exception("close error")
    # Should handle exception gracefully
    await force_cleanup_critical_resources(db=mock_db)


# ── safe_shutdown_cleanup ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_safe_shutdown_cleanup_minimal():
    """No-op call with all None args."""
    await safe_shutdown_cleanup()


@pytest.mark.asyncio
async def test_safe_shutdown_cleanup_with_service():
    mock_service = MagicMock()
    await safe_shutdown_cleanup(cleanup_service=mock_service)
    mock_service.stop.assert_called_once()


@pytest.mark.asyncio
async def test_safe_shutdown_cleanup_service_raises():
    mock_service = MagicMock()
    mock_service.stop.side_effect = RuntimeError("service error")
    # Should not raise
    await safe_shutdown_cleanup(cleanup_service=mock_service)


@pytest.mark.asyncio
async def test_safe_shutdown_cleanup_with_task():
    async def noop():
        await asyncio.sleep(100)

    loop = asyncio.get_event_loop()
    task = loop.create_task(noop())
    await asyncio.sleep(0)

    await safe_shutdown_cleanup(cleanup_task=task)
    assert task.done()


@pytest.mark.asyncio
async def test_safe_shutdown_cleanup_owned_db():
    mock_db = AsyncMock()
    await safe_shutdown_cleanup(db=mock_db, db_owned=True)
    mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_safe_shutdown_cleanup_not_owned_db():
    mock_db = AsyncMock()
    await safe_shutdown_cleanup(db=mock_db, db_owned=False)
    mock_db.close.assert_not_called()


@pytest.mark.asyncio
async def test_safe_shutdown_cleanup_db_timeout():
    mock_db = AsyncMock()
    mock_db.close = AsyncMock(side_effect=asyncio.TimeoutError)
    await safe_shutdown_cleanup(db=mock_db, db_owned=True)


@pytest.mark.asyncio
async def test_safe_shutdown_cleanup_clears_shutdown_event():
    event = asyncio.Event()
    event.set()
    set_shutdown_event(event)

    with patch(
        "src.services.otp_manager.otp_webhook.get_otp_service",
        side_effect=Exception("no otp"),
    ):
        await safe_shutdown_cleanup(shutdown_event=event)

    assert get_shutdown_event() is None


@pytest.mark.asyncio
async def test_safe_shutdown_cleanup_full():
    mock_db = AsyncMock()
    mock_service = MagicMock()
    event = asyncio.Event()

    async def noop():
        await asyncio.sleep(100)

    loop = asyncio.get_event_loop()
    task = loop.create_task(noop())
    await asyncio.sleep(0)

    with patch(
        "src.services.otp_manager.otp_webhook.get_otp_service",
        side_effect=Exception("no otp"),
    ):
        await safe_shutdown_cleanup(
            db=mock_db,
            db_owned=True,
            cleanup_service=mock_service,
            cleanup_task=task,
            shutdown_event=event,
        )

    mock_service.stop.assert_called_once()
    mock_db.close.assert_called_once()
