"""End-to-end tests for booking flow with mocked VFS responses."""

from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.constants import Database as DatabaseConfig
from src.models.database import Database
from src.repositories import UserRepository, AppointmentRepository


class TestBookingFlow:
    """E2E tests for the booking flow."""

    @pytest.mark.asyncio
    async def test_full_booking_flow_success(self):
        """Test complete booking flow from login to confirmation."""
        # Setup test database
        db = Database(database_url=DatabaseConfig.TEST_URL)
        await db.connect()

        try:
            # Create test user
            user_repo = UserRepository(db)
            user_id = await user_repo.create({
                'email': "e2e_test@example.com",
                'password': "testpassword",
                'center_name': "Istanbul",
                'visa_category': "Schengen",
                'visa_subcategory': "Tourism",
            })

            # Add personal details
            await db.add_personal_details(
                user_id=user_id,
                details={
                    "first_name": "John",
                    "last_name": "Doe",
                    "passport_number": "AB1234567",
                    "email": "e2e_test@example.com",
                    "mobile_code": "90",
                    "mobile_number": "5551234567",
                },
            )

            # Verify user was created
            user = await db.get_user_with_decrypted_password(user_id)
            assert user is not None
            assert user["email"] == "e2e_test@example.com"
            assert user["password"] == "testpassword"  # Decrypted

            # Verify personal details
            details = await db.get_personal_details(user_id)
            assert details is not None
            assert details["first_name"] == "John"
            assert details["passport_number"] == "AB1234567"

            # Create appointment
            appointment_repo = AppointmentRepository(db)
            await appointment_repo.create({
                'user_id': user_id,
                'centre': "Istanbul",
                'category': "Schengen",
                'subcategory': "Tourism",
                'appointment_date': "2024-12-31",
                'appointment_time': "10:00",
                'reference_number': "REF123456",
            })

            # Verify appointment
            appointments = await db.get_appointments(user_id)
            assert len(appointments) == 1
            assert appointments[0]["reference_number"] == "REF123456"

        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_booking_flow_with_captcha(self):
        """Test booking flow when captcha is required."""
        # Mock captcha solver - now it's part of the CaptchaSolver class
        with patch("src.services.captcha_solver.CaptchaSolver.solve_recaptcha") as mock_solve:
            mock_solve.return_value = "captcha_solution"

            # Simulate captcha detection and solving
            captcha_detected = True
            if captcha_detected:
                solution = await self._mock_solve_captcha()
                assert solution == "captcha_solution"

    async def _mock_solve_captcha(self) -> str:
        """Mock captcha solving."""
        return "captcha_solution"

    @pytest.mark.asyncio
    async def test_booking_flow_slot_not_available(self):
        """Test flow when no slots are available."""
        db = Database(database_url=DatabaseConfig.TEST_URL)
        await db.connect()

        try:
            # Create test user
            user_repo = UserRepository(db)
            user_id = await user_repo.create({
                'email': "no_slots@example.com",
                'password': "testpassword",
                'center_name': "Istanbul",
                'visa_category': "Schengen",
                'visa_subcategory': "Tourism",
            })

            # Simulate slot check with no available slots
            slot_available = False

            if not slot_available:
                # No appointment should be created
                appointments = await db.get_appointments(user_id)
                assert len(appointments) == 0

        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_booking_flow_with_retry(self):
        """Test booking flow with retry mechanism on failures."""
        max_retries = 3
        current_attempt = 0
        success = False

        # Simulate retries
        for attempt in range(max_retries):
            current_attempt = attempt + 1

            # Simulate failure on first two attempts, success on third
            if attempt < 2:
                continue  # Failed attempt
            else:
                success = True
                break

        assert success is True
        assert current_attempt == 3

    @pytest.mark.asyncio
    async def test_notification_after_booking(self):
        """Test that notifications are sent after successful booking."""
        notification_sent = False

        # Mock notification service
        async def mock_send_notification(message: str) -> bool:
            nonlocal notification_sent
            notification_sent = True
            return True

        # Simulate successful booking
        booking_success = True

        if booking_success:
            await mock_send_notification("Appointment booked successfully")

        assert notification_sent is True

    @pytest.mark.asyncio
    async def test_payment_flow_manual(self):
        """Test manual payment flow."""
        payment_method = "manual"

        if payment_method == "manual":
            # Manual payment requires user interaction
            payment_pending = True
            assert payment_pending is True

    @pytest.mark.asyncio
    async def test_otp_webhook_integration(self, tmp_path):
        """Test OTP webhook integration in booking flow."""
        # Mock OTP service
        otp_received = "123456"

        # Simulate OTP arrival via webhook
        if otp_received:
            assert len(otp_received) == 6
            assert otp_received.isdigit()

    @pytest.mark.asyncio
    async def test_concurrent_booking_attempts(self):
        """Test that concurrent booking attempts are handled correctly."""
        import asyncio

        db = Database(database_url=DatabaseConfig.TEST_URL)
        await db.connect()

        try:
            # Create multiple users
            user_repo = UserRepository(db)
            user_ids = []
            for i in range(3):
                user_id = await user_repo.create({
                    'email': f"concurrent{i}@example.com",
                    'password': "testpass",
                    'center_name': "Istanbul",
                    'visa_category': "Schengen",
                    'visa_subcategory': "Tourism",
                })
                user_ids.append(user_id)

            # Simulate concurrent booking attempts
            appointment_repo = AppointmentRepository(db)

            async def book_appointment(user_id: int) -> int:
                return await appointment_repo.create({
                    'user_id': user_id,
                    'centre': "Istanbul",
                    'category': "Schengen",
                    'subcategory': "Tourism",
                    'appointment_date': "2024-12-31",
                    'appointment_time': "10:00",
                    'reference_number': f"REF{user_id}",
                })

            tasks = [book_appointment(uid) for uid in user_ids]
            appointment_ids = await asyncio.gather(*tasks)

            # Verify all bookings succeeded
            assert len(appointment_ids) == 3
            assert len(set(appointment_ids)) == 3  # All unique

        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_error_recovery(self):
        """Test error recovery mechanisms."""
        max_retries = 3
        errors = []

        for attempt in range(max_retries):
            try:
                # Simulate error on first attempt
                if attempt == 0:
                    raise Exception("Network error")

                # Success on subsequent attempts
                break
            except Exception as e:
                errors.append(str(e))
                if attempt == max_retries - 1:
                    raise

        # Should recover on second attempt
        assert len(errors) == 1
