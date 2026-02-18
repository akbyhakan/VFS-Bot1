"""Tests for BookingOrchestrator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.booking.booking_orchestrator import BookingOrchestrator


@pytest.fixture
def mock_page():
    """Create a mock Playwright page object."""
    page = AsyncMock()
    page.url = "https://visa.vfsglobal.com/tur/en/deu/booking"
    page.locator = MagicMock()
    page.click = AsyncMock()
    return page


@pytest.fixture
def mock_config():
    """Create minimal configuration for orchestrator."""
    return {
        "vfs": {
            "base_url": "https://visa.vfsglobal.com",
            "country": "tur",
            "mission": "deu",
        }
    }


@pytest.fixture
def orchestrator(mock_config):
    """Create a BookingOrchestrator instance."""
    return BookingOrchestrator(config=mock_config)


# ──────────────────────────────────────────────────────────────
# Test _handle_booking_otp_if_present method
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_booking_otp_not_present(orchestrator, mock_page):
    """Test that method returns True when OTP button is not present."""
    # Mock OTP generate button as not visible
    mock_locator = AsyncMock()
    mock_locator.is_visible = AsyncMock(return_value=False)
    mock_page.locator.return_value.first = mock_locator

    result = await orchestrator._handle_booking_otp_if_present(mock_page)

    assert result is True
    mock_locator.is_visible.assert_called_once()


@pytest.mark.asyncio
async def test_handle_booking_otp_full_flow(orchestrator, mock_page):
    """Test full OTP flow: generate → input → verify → success → continue."""
    # Mock OTP generate button visible
    otp_generate_button = AsyncMock()
    otp_generate_button.is_visible = AsyncMock(return_value=True)
    otp_generate_button.click = AsyncMock()

    # Mock OTP input field
    otp_input = AsyncMock()
    otp_input.wait_for = AsyncMock()
    otp_input.fill = AsyncMock()

    # Mock verify button
    verify_button = AsyncMock()
    verify_button.click = AsyncMock()

    # Mock success message
    success_message = AsyncMock()
    success_message.wait_for = AsyncMock()

    # Mock continue button
    continue_button = AsyncMock()
    continue_button.click = AsyncMock()

    # Setup locator returns
    def locator_side_effect(selector):
        mock = AsyncMock()
        if "Tek Seferlik Şifre" in selector or "Generate One Time Password" in selector:
            mock.first = otp_generate_button
        elif 'input[placeholder="OTP"]' in selector:
            return otp_input
        elif "Doğrula" in selector or "Verify" in selector:
            mock.first = verify_button
        elif "OTP doğrulaması başarılı" in selector or "OTP verification successful" in selector:
            return success_message
        elif "Devam Et" in selector or "Continue" in selector:
            mock.first = continue_button
        return mock

    mock_page.locator.side_effect = locator_side_effect

    # Mock OTP service
    mock_otp_service = AsyncMock()
    mock_otp_service.wait_for_appointment_otp = AsyncMock(return_value="123456")

    with patch.object(orchestrator, "_get_otp_service", return_value=mock_otp_service):
        with patch.object(orchestrator, "wait_for_overlay", new=AsyncMock()):
            result = await orchestrator._handle_booking_otp_if_present(mock_page)

    assert result is True
    otp_generate_button.click.assert_called_once()
    otp_input.fill.assert_called_once_with("123456")
    verify_button.click.assert_called_once()
    continue_button.click.assert_called_once()


@pytest.mark.asyncio
async def test_handle_booking_otp_timeout(orchestrator, mock_page):
    """Test that method returns False when OTP service times out."""
    # Mock OTP generate button visible
    otp_generate_button = AsyncMock()
    otp_generate_button.is_visible = AsyncMock(return_value=True)
    otp_generate_button.click = AsyncMock()

    # Mock OTP input field
    otp_input = AsyncMock()
    otp_input.wait_for = AsyncMock()

    # Setup locator returns
    def locator_side_effect(selector):
        mock = AsyncMock()
        if "Tek Seferlik Şifre" in selector or "Generate One Time Password" in selector:
            mock.first = otp_generate_button
        elif 'input[placeholder="OTP"]' in selector:
            return otp_input
        return mock

    mock_page.locator.side_effect = locator_side_effect

    # Mock OTP service returning None (timeout)
    mock_otp_service = AsyncMock()
    mock_otp_service.wait_for_appointment_otp = AsyncMock(return_value=None)

    with patch.object(orchestrator, "_get_otp_service", return_value=mock_otp_service):
        result = await orchestrator._handle_booking_otp_if_present(mock_page)

    assert result is False


@pytest.mark.asyncio
async def test_run_booking_flow_includes_otp_step(orchestrator, mock_page):
    """Test that run_booking_flow calls _handle_booking_otp_if_present."""
    reservation = {
        "user_id": 1,
        "appointment_date": "2024-12-25",
        "applicants": [{"first_name": "John", "last_name": "Doe"}],
        "payment_card": {"number": "1234", "cvv": "123"},
    }

    # Mock all dependencies
    with patch.object(orchestrator.validator, "check_double_match", new=AsyncMock(return_value={"match": True})):
        with patch.object(orchestrator.form_filler, "fill_all_applicants", new=AsyncMock()):
            with patch.object(orchestrator, "_handle_booking_otp_if_present", new=AsyncMock(return_value=True)) as mock_otp:
                with patch.object(orchestrator.slot_selector, "select_appointment_slot", new=AsyncMock(return_value=True)):
                    with patch.object(orchestrator, "skip_services_page", new=AsyncMock()):
                        with patch.object(orchestrator, "handle_review_and_pay", new=AsyncMock()):
                            with patch.object(orchestrator, "wait_for_overlay", new=AsyncMock()):
                                mock_page.click = AsyncMock()
                                orchestrator.payment_service = AsyncMock()
                                orchestrator.payment_service.process_payment = AsyncMock(return_value=True)

                                result = await orchestrator.run_booking_flow(mock_page, reservation)

    # Verify OTP handling was called
    mock_otp.assert_called_once_with(mock_page)
    assert result is True


# ──────────────────────────────────────────────────────────────
# Test select_appointment_slot captcha handling
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_select_appointment_slot_captcha_not_handled(orchestrator, mock_page):
    """Test that select_appointment_slot returns False when captcha cannot be solved."""
    reservation = {"preferred_dates": ["23/01/2026"]}

    # Mock handle_captcha_if_present to return False (captcha failed)
    with patch.object(
        orchestrator.slot_selector,
        "handle_captcha_if_present",
        new=AsyncMock(return_value=False)
    ) as mock_captcha:
        with patch.object(orchestrator.slot_selector, "wait_for_overlay", new=AsyncMock()):
            result = await orchestrator.slot_selector.select_appointment_slot(
                mock_page, reservation
            )

    # Should return False when captcha handling fails
    assert result is False
    mock_captcha.assert_called_once_with(mock_page)


@pytest.mark.asyncio
async def test_select_appointment_slot_captcha_handled(orchestrator, mock_page):
    """Test that select_appointment_slot continues normally when captcha is handled."""
    reservation = {"preferred_dates": ["23/01/2026"]}

    # Mock date element with matching aria-label
    mock_date_elem = AsyncMock()
    mock_date_elem.get_attribute = AsyncMock(return_value="23 Ocak 2026")
    mock_date_elem.click = AsyncMock()

    # Mock page.locator to return the date element
    mock_locator = AsyncMock()
    mock_locator.all = AsyncMock(return_value=[mock_date_elem])
    mock_page.locator.return_value = mock_locator
    mock_page.click = AsyncMock()

    # Mock handle_captcha_if_present to return True (captcha handled or not present)
    with patch.object(
        orchestrator.slot_selector,
        "handle_captcha_if_present",
        new=AsyncMock(return_value=True)
    ) as mock_captcha:
        with patch.object(orchestrator.slot_selector, "wait_for_overlay", new=AsyncMock()):
            with patch.object(
                orchestrator.slot_selector,
                "select_preferred_time",
                new=AsyncMock(return_value=True)
            ):
                result = await orchestrator.slot_selector.select_appointment_slot(
                    mock_page, reservation
                )

    # Should return True when captcha is handled and slot is selected
    assert result is True
    mock_captcha.assert_called_once_with(mock_page)
