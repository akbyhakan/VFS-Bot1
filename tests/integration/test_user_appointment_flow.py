"""Integration tests for user and appointment service layer with real database."""

import asyncio
import logging
from typing import Any, Dict

import pytest

from src.models.database import Database
from src.repositories.appointment_repository import AppointmentRepository
from src.repositories.user_repository import UserRepository
from src.services.appointment_deduplication import AppointmentDeduplicationService

logger = logging.getLogger(__name__)


@pytest.mark.integration
class TestUserAppointmentFlow:
    """Integration tests for user and appointment workflows with real database."""

    @pytest.mark.asyncio
    async def test_create_user_add_details_book_appointment(
        self, test_db: Database, user_repo: UserRepository, appointment_repo: AppointmentRepository
    ):
        """
        Test complete user flow: Create user → Add personal details → Create appointment → Verify decrypted password.

        This validates:
        - User creation with encrypted password
        - Personal details cascade relationship
        - Password decryption works correctly
        - Appointment creation and retrieval
        """
        # Step 1: Create user
        user_data = {
            "email": "fullflow_test@example.com",
            "password": "MySecretPassword123!",
            "center_name": "Ankara",
            "visa_category": "Schengen",
            "visa_subcategory": "Business",
        }

        user_id = await user_repo.create(user_data)
        assert user_id is not None
        assert user_id > 0

        # Step 2: Add personal details
        personal_details = {
            "first_name": "Ahmet",
            "last_name": "Yilmaz",
            "passport_number": "TR1234567",
            "email": "fullflow_test@example.com",
            "mobile_code": "90",
            "mobile_number": "5551234567",
            "nationality": "Turkish",
        }

        await test_db.add_personal_details(user_id=user_id, details=personal_details)

        # Step 3: Verify user was created with encrypted password
        user_encrypted = await test_db.get_user(user_id)
        assert user_encrypted is not None
        assert user_encrypted["email"] == user_data["email"]
        # Password should be encrypted, not plaintext
        assert user_encrypted["password"] != user_data["password"]

        # Step 4: Verify decrypted password matches original
        user_decrypted = await test_db.get_user_with_decrypted_password(user_id)
        assert user_decrypted is not None
        assert user_decrypted["password"] == user_data["password"]

        # Step 5: Verify personal details
        details = await test_db.get_personal_details(user_id)
        assert details is not None
        assert details["first_name"] == personal_details["first_name"]
        assert details["passport_number"] == personal_details["passport_number"]

        # Step 6: Create appointment
        appointment_data = {
            "user_id": user_id,
            "centre": "Ankara",
            "category": "Schengen",
            "subcategory": "Business",
            "appointment_date": "2024-12-20",
            "appointment_time": "14:30",
            "reference_number": "REF-ANKARA-001",
        }

        appointment_id = await appointment_repo.create(appointment_data)
        assert appointment_id is not None
        assert appointment_id > 0

        # Step 7: Verify appointment
        appointments = await test_db.get_appointments(user_id)
        assert len(appointments) == 1
        assert appointments[0]["reference_number"] == appointment_data["reference_number"]
        assert appointments[0]["appointment_date"] == appointment_data["appointment_date"]

    @pytest.mark.asyncio
    async def test_duplicate_appointment_prevention(
        self, test_db: Database, user_repo: UserRepository, appointment_repo: AppointmentRepository
    ):
        """
        Test deduplication service prevents duplicate appointments.

        This validates:
        - is_duplicate correctly identifies duplicates
        - mark_booked prevents re-booking
        - Service state is properly maintained
        """
        # Create test user
        user_id = await user_repo.create(
            {
                "email": "dedup_test@example.com",
                "password": "TestPass123!",
                "center_name": "Istanbul",
                "visa_category": "Schengen",
                "visa_subcategory": "Tourism",
            }
        )

        # Initialize deduplication service
        from src.services.appointment_deduplication import get_deduplication_service

        dedup_service = await get_deduplication_service()

        appointment_key = {
            "centre": "Istanbul",
            "category": "Schengen",
            "subcategory": "Tourism",
            "date": "2024-12-25",
            "time": "10:00",
        }

        # Step 1: First check - should not be duplicate
        is_dup_1 = await dedup_service.is_duplicate(
            user_id=user_id,
            centre=appointment_key["centre"],
            category=appointment_key["category"],
            subcategory=appointment_key["subcategory"],
            appointment_date=appointment_key["date"],
            appointment_time=appointment_key["time"],
        )
        assert is_dup_1 is False, "First appointment check should not be duplicate"

        # Step 2: Mark as booked
        await dedup_service.mark_booked(
            user_id=user_id,
            centre=appointment_key["centre"],
            category=appointment_key["category"],
            subcategory=appointment_key["subcategory"],
            appointment_date=appointment_key["date"],
            appointment_time=appointment_key["time"],
        )

        # Step 3: Check again - should now be duplicate
        is_dup_2 = await dedup_service.is_duplicate(
            user_id=user_id,
            centre=appointment_key["centre"],
            category=appointment_key["category"],
            subcategory=appointment_key["subcategory"],
            appointment_date=appointment_key["date"],
            appointment_time=appointment_key["time"],
        )
        assert is_dup_2 is True, "Second check should identify as duplicate"

        # Step 4: Different appointment should not be duplicate
        is_dup_3 = await dedup_service.is_duplicate(
            user_id=user_id,
            centre=appointment_key["centre"],
            category=appointment_key["category"],
            subcategory=appointment_key["subcategory"],
            appointment_date="2024-12-26",  # Different date
            appointment_time=appointment_key["time"],
        )
        assert is_dup_3 is False, "Different appointment should not be duplicate"

    @pytest.mark.asyncio
    async def test_concurrent_user_creation(self, test_db: Database, user_repo: UserRepository):
        """
        Test concurrent user creation to detect race conditions.

        Creates 10 users simultaneously and verifies:
        - All users are created successfully
        - No database conflicts or race conditions
        - All emails are unique
        """

        async def create_user(index: int) -> int:
            """Create a single user."""
            user_data = {
                "email": f"concurrent_user_{index}@example.com",
                "password": f"Password{index}!",
                "center_name": "Istanbul",
                "visa_category": "Schengen",
                "visa_subcategory": "Tourism",
            }
            return await user_repo.create(user_data)

        # Create 10 users concurrently
        tasks = [create_user(i) for i in range(10)]
        user_ids = await asyncio.gather(*tasks)

        # Verify all users were created
        assert len(user_ids) == 10
        assert all(uid > 0 for uid in user_ids)

        # Verify all IDs are unique
        assert len(set(user_ids)) == 10, "All user IDs should be unique"

        # Verify we can retrieve all users
        for user_id in user_ids:
            user = await test_db.get_user(user_id)
            assert user is not None
            assert user["id"] == user_id

    @pytest.mark.asyncio
    async def test_user_cascade_delete(self, test_db: Database, user_repo: UserRepository):
        """
        Test cascade delete: deleting user also deletes personal_details.

        This validates:
        - Foreign key cascade behavior
        - Orphaned records are properly cleaned up
        """
        # Create user
        user_id = await user_repo.create(
            {
                "email": "cascade_test@example.com",
                "password": "TestPass123!",
                "center_name": "Istanbul",
                "visa_category": "Schengen",
                "visa_subcategory": "Tourism",
            }
        )

        # Add personal details
        await test_db.add_personal_details(
            user_id=user_id,
            details={
                "first_name": "Test",
                "last_name": "User",
                "passport_number": "ABC123",
                "email": "cascade_test@example.com",
                "mobile_code": "90",
                "mobile_number": "5551234567",
            },
        )

        # Verify personal details exist
        details_before = await test_db.get_personal_details(user_id)
        assert details_before is not None

        # Delete user
        deleted = await user_repo.delete(user_id)
        assert deleted is True

        # Verify user is deleted
        user_after = await test_db.get_user(user_id)
        assert user_after is None

        # Verify personal details are also deleted (cascade)
        details_after = await test_db.get_personal_details(user_id)
        assert details_after is None, "Personal details should be cascade deleted"
