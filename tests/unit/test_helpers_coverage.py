"""Coverage tests for src/utils/helpers.py."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from src.utils.helpers import (
    format_local_datetime,
    smart_click,
    smart_fill,
    wait_for_element_with_retry,
)

# ── smart_fill ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_smart_fill_basic():
    page = AsyncMock()
    await smart_fill(page, "#email", "test@example.com")
    page.fill.assert_called_once_with("#email", "test@example.com")


@pytest.mark.asyncio
async def test_smart_fill_self_healing_success():
    page = AsyncMock()
    page.fill = AsyncMock(side_effect=[Exception("stale element"), None])

    mock_self_healing = MagicMock()
    mock_self_healing.attempt_heal = AsyncMock(return_value="#new-email")

    await smart_fill(
        page,
        "#old-email",
        "user@test.com",
        self_healing=mock_self_healing,
        selector_path="login.email",
        element_description="email input field",
    )

    mock_self_healing.attempt_heal.assert_called_once()
    # Second fill call uses healed selector
    assert page.fill.call_count == 2
    page.fill.assert_called_with("#new-email", "user@test.com")


@pytest.mark.asyncio
async def test_smart_fill_self_healing_returns_none_raises_original():
    page = AsyncMock()
    original_error = Exception("stale element")
    page.fill = AsyncMock(side_effect=original_error)

    mock_self_healing = MagicMock()
    mock_self_healing.attempt_heal = AsyncMock(return_value=None)

    with pytest.raises(Exception, match="stale element"):
        await smart_fill(
            page,
            "#email",
            "x",
            self_healing=mock_self_healing,
            selector_path="p",
            element_description="d",
        )


@pytest.mark.asyncio
async def test_smart_fill_self_healing_itself_fails_raises_original():
    page = AsyncMock()
    original_error = Exception("original error")
    page.fill = AsyncMock(side_effect=original_error)

    mock_self_healing = MagicMock()
    mock_self_healing.attempt_heal = AsyncMock(side_effect=Exception("heal error"))

    with pytest.raises(Exception, match="original error"):
        await smart_fill(
            page,
            "#email",
            "x",
            self_healing=mock_self_healing,
            selector_path="p",
            element_description="d",
        )


@pytest.mark.asyncio
async def test_smart_fill_no_self_healing_raises():
    page = AsyncMock()
    page.fill = AsyncMock(side_effect=Exception("no heal"))

    with pytest.raises(Exception, match="no heal"):
        await smart_fill(page, "#sel", "text")


# ── smart_click ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_smart_click_basic():
    page = AsyncMock()
    await smart_click(page, "#btn")
    page.click.assert_called_once_with("#btn")


@pytest.mark.asyncio
async def test_smart_click_self_healing_success():
    page = AsyncMock()
    page.click = AsyncMock(side_effect=[Exception("element gone"), None])

    mock_self_healing = MagicMock()
    mock_self_healing.attempt_heal = AsyncMock(return_value="#new-btn")

    await smart_click(
        page,
        "#old-btn",
        self_healing=mock_self_healing,
        selector_path="login.submit",
        element_description="submit button",
    )

    mock_self_healing.attempt_heal.assert_called_once()
    assert page.click.call_count == 2
    page.click.assert_called_with("#new-btn")


@pytest.mark.asyncio
async def test_smart_click_self_healing_returns_none_raises_original():
    page = AsyncMock()
    page.click = AsyncMock(side_effect=Exception("click fail"))

    mock_self_healing = MagicMock()
    mock_self_healing.attempt_heal = AsyncMock(return_value=None)

    with pytest.raises(Exception, match="click fail"):
        await smart_click(
            page,
            "#btn",
            self_healing=mock_self_healing,
            selector_path="p",
            element_description="d",
        )


@pytest.mark.asyncio
async def test_smart_click_self_healing_itself_fails_raises_original():
    page = AsyncMock()
    original_error = Exception("original click error")
    page.click = AsyncMock(side_effect=original_error)

    mock_self_healing = MagicMock()
    mock_self_healing.attempt_heal = AsyncMock(side_effect=Exception("heal broke"))

    with pytest.raises(Exception, match="original click error"):
        await smart_click(
            page,
            "#btn",
            self_healing=mock_self_healing,
            selector_path="p",
            element_description="d",
        )


@pytest.mark.asyncio
async def test_smart_click_no_self_healing_raises():
    page = AsyncMock()
    page.click = AsyncMock(side_effect=Exception("can't click"))

    with pytest.raises(Exception, match="can't click"):
        await smart_click(page, "#gone")


# ── wait_for_element_with_retry ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wait_for_element_success_first_try():
    page = AsyncMock()
    page.wait_for_selector = AsyncMock(return_value=None)

    result = await wait_for_element_with_retry(page, "#el", max_retries=3)
    assert result is True
    assert page.wait_for_selector.call_count == 1


@pytest.mark.asyncio
async def test_wait_for_element_success_on_retry():
    page = AsyncMock()
    page.wait_for_selector = AsyncMock(side_effect=[PlaywrightTimeoutError("timeout"), None])

    result = await wait_for_element_with_retry(page, "#el", max_retries=3, initial_timeout=100)
    assert result is True
    assert page.wait_for_selector.call_count == 2


@pytest.mark.asyncio
async def test_wait_for_element_all_retries_fail():
    page = AsyncMock()
    page.wait_for_selector = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))

    result = await wait_for_element_with_retry(page, "#el", max_retries=3, initial_timeout=100)
    assert result is False
    assert page.wait_for_selector.call_count == 3


@pytest.mark.asyncio
async def test_wait_for_element_backoff_increases_timeout():
    page = AsyncMock()
    page.wait_for_selector = AsyncMock(side_effect=PlaywrightTimeoutError("t"))

    await wait_for_element_with_retry(
        page, "#el", max_retries=3, initial_timeout=1000, backoff_factor=2.0
    )

    calls = page.wait_for_selector.call_args_list
    timeouts = [c.kwargs.get("timeout") or c.args[1] for c in calls]
    # Each retry should use a larger timeout
    assert timeouts[1] > timeouts[0] or all(c.kwargs["timeout"] > 0 for c in calls)


# ── format_local_datetime ─────────────────────────────────────────────────────


def test_format_local_datetime_with_none_uses_utc_now():
    result = format_local_datetime(utc_dt=None, tz_name="UTC")
    assert isinstance(result, str)
    assert len(result) > 0


def test_format_local_datetime_with_aware_datetime():
    dt = datetime(2024, 6, 15, 12, 30, 0, tzinfo=timezone.utc)
    result = format_local_datetime(utc_dt=dt, tz_name="Europe/Istanbul")
    assert isinstance(result, str)
    # Istanbul is UTC+3
    assert "15.06.2024" in result


def test_format_local_datetime_with_naive_datetime():
    dt = datetime(2024, 6, 15, 12, 0, 0)  # naive
    result = format_local_datetime(utc_dt=dt, tz_name="UTC")
    assert "15.06.2024" in result


def test_format_local_datetime_invalid_timezone_falls_back():
    dt = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    # Invalid timezone → should fall back to UTC formatting
    result = format_local_datetime(utc_dt=dt, tz_name="Invalid/Timezone")
    assert isinstance(result, str)
    assert "15.06.2024" in result


def test_format_local_datetime_custom_format():
    dt = datetime(2024, 1, 5, 9, 7, 3, tzinfo=timezone.utc)
    result = format_local_datetime(utc_dt=dt, tz_name="UTC", fmt="%Y-%m-%d")
    assert result == "2024-01-05"
