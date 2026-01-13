"""Extended tests for src/models/database.py - aiming for 85% coverage."""

import pytest
from pathlib import Path

from src.models.database import Database


@pytest.mark.asyncio
class TestGetAppointments:
    """Tests for appointment retrieval."""

    async def test_get_appointments_empty(self, tmp_path):
        """Test getting appointments when database is empty."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        await db.connect()

        # Add a user first
        await db.add_user(
            email="test@example.com",
            password="password123",
            centre="Istanbul",
            category="Schengen Visa",
            subcategory="Tourism",
        )

        appointments = await db.get_appointments(user_id=1)

        assert appointments == []

        await db.close()

    async def test_multiple_appointments(self, tmp_path):
        """Test getting multiple appointments for a user."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        await db.connect()

        # Add a user
        user_id = await db.add_user(
            email="test@example.com",
            password="password123",
            centre="Istanbul",
            category="Schengen Visa",
            subcategory="Tourism",
        )

        # Add multiple appointments
        await db.add_appointment(
            user_id=user_id,
            centre="Istanbul",
            date="2024-01-15",
            time="10:00",
            reference="REF001",
        )
        await db.add_appointment(
            user_id=user_id,
            centre="Istanbul",
            date="2024-01-16",
            time="11:00",
            reference="REF002",
        )

        appointments = await db.get_appointments(user_id=user_id)

        assert len(appointments) == 2

        await db.close()

    async def test_get_all_appointments(self, tmp_path):
        """Test getting all appointments."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        await db.connect()

        # Add users
        user1_id = await db.add_user(
            email="user1@example.com",
            password="password123",
            centre="Istanbul",
            category="Schengen Visa",
            subcategory="Tourism",
        )
        user2_id = await db.add_user(
            email="user2@example.com",
            password="password123",
            centre="Ankara",
            category="Schengen Visa",
            subcategory="Business",
        )

        # Add appointments for both users
        await db.add_appointment(
            user_id=user1_id,
            centre="Istanbul",
            date="2024-01-15",
            time="10:00",
            reference="REF001",
        )
        await db.add_appointment(
            user_id=user2_id,
            centre="Ankara",
            date="2024-01-16",
            time="11:00",
            reference="REF002",
        )

        all_appointments = await db.get_all_appointments()

        assert len(all_appointments) >= 2

        await db.close()


@pytest.mark.asyncio
class TestGetLogs:
    """Tests for log retrieval."""

    async def test_get_logs_limit(self, tmp_path):
        """Test getting logs with limit."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        await db.connect()

        # Add some logs
        for i in range(10):
            await db.add_log(
                user_id=1, action=f"Action {i}", status="success", details=f"Details {i}"
            )

        logs = await db.get_logs(limit=5)

        assert len(logs) == 5

        await db.close()


@pytest.mark.asyncio
class TestConnectionPoolContextManager:
    """Tests for connection pool context manager."""

    async def test_connection_pool_context_manager(self, tmp_path):
        """Test using connection pool context manager."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path), pool_size=3)
        await db.connect()

        async with db.get_connection() as conn:
            assert conn is not None
            # Connection should be usable
            cursor = await conn.execute("SELECT 1")
            result = await cursor.fetchone()
            assert result is not None

        await db.close()

    async def test_multiple_concurrent_connections(self, tmp_path):
        """Test multiple concurrent connections from pool."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path), pool_size=3)
        await db.connect()

        # Get multiple connections concurrently
        async def use_connection(db, delay):
            async with db.get_connection() as conn:
                await conn.execute("SELECT 1")

        import asyncio

        await asyncio.gather(
            use_connection(db, 0.01), use_connection(db, 0.01), use_connection(db, 0.01)
        )

        await db.close()


@pytest.mark.asyncio
class TestUserDuplicateEmail:
    """Tests for duplicate email handling."""

    async def test_user_duplicate_email(self, tmp_path):
        """Test adding user with duplicate email."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        await db.connect()

        # Add first user
        await db.add_user(
            email="duplicate@example.com",
            password="password123",
            centre="Istanbul",
            category="Schengen Visa",
            subcategory="Tourism",
        )

        # Try to add user with same email
        with pytest.raises(Exception):
            await db.add_user(
                email="duplicate@example.com",
                password="password456",
                centre="Ankara",
                category="Schengen Visa",
                subcategory="Business",
            )

        await db.close()


@pytest.mark.asyncio
class TestUpdateUser:
    """Tests for updating user information."""

    async def test_update_user_basic(self, tmp_path):
        """Test updating user basic info."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        await db.connect()

        # Add user
        user_id = await db.add_user(
            email="test@example.com",
            password="password123",
            centre="Istanbul",
            category="Schengen Visa",
            subcategory="Tourism",
        )

        # Update user
        await db.update_user(user_id=user_id, centre="Ankara", category="Work Visa")

        # Get user and verify
        user = await db.get_user(user_id)
        assert user is not None
        assert user["centre"] == "Ankara"
        assert user["category"] == "Work Visa"

        await db.close()


@pytest.mark.asyncio
class TestGetActiveUsers:
    """Tests for getting active users."""

    async def test_get_active_users_only(self, tmp_path):
        """Test that only active users are returned."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        await db.connect()

        # Add active user
        active_user_id = await db.add_user(
            email="active@example.com",
            password="password123",
            centre="Istanbul",
            category="Schengen Visa",
            subcategory="Tourism",
        )

        # Add inactive user
        inactive_user_id = await db.add_user(
            email="inactive@example.com",
            password="password123",
            centre="Ankara",
            category="Schengen Visa",
            subcategory="Business",
        )

        # Deactivate second user
        await db.update_user(user_id=inactive_user_id, active=False)

        # Get active users
        active_users = await db.get_active_users()

        assert len(active_users) >= 1
        # Verify inactive user is not in the list
        active_emails = [user["email"] for user in active_users]
        assert "active@example.com" in active_emails
        assert "inactive@example.com" not in active_emails

        await db.close()


@pytest.mark.asyncio
class TestGetPersonalDetails:
    """Tests for getting personal details."""

    async def test_get_personal_details_exists(self, tmp_path):
        """Test getting personal details when they exist."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        await db.connect()

        # Add user
        user_id = await db.add_user(
            email="test@example.com",
            password="password123",
            centre="Istanbul",
            category="Schengen Visa",
            subcategory="Tourism",
        )

        # Add personal details
        await db.add_personal_details(
            user_id=user_id,
            first_name="John",
            last_name="Doe",
            passport_number="AB123456",
            nationality="TR",
            birth_date="1990-01-01",
        )

        # Get personal details
        details = await db.get_personal_details(user_id)

        assert details is not None
        assert details["first_name"] == "John"
        assert details["last_name"] == "Doe"

        await db.close()

    async def test_get_personal_details_not_exists(self, tmp_path):
        """Test getting personal details when they don't exist."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        await db.connect()

        # Add user without personal details
        user_id = await db.add_user(
            email="test@example.com",
            password="password123",
            centre="Istanbul",
            category="Schengen Visa",
            subcategory="Tourism",
        )

        # Get personal details
        details = await db.get_personal_details(user_id)

        assert details is None

        await db.close()


@pytest.mark.asyncio
class TestDeleteUser:
    """Tests for deleting users."""

    async def test_delete_user(self, tmp_path):
        """Test deleting a user."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        await db.connect()

        # Add user
        user_id = await db.add_user(
            email="test@example.com",
            password="password123",
            centre="Istanbul",
            category="Schengen Visa",
            subcategory="Tourism",
        )

        # Delete user
        await db.delete_user(user_id)

        # Verify user is deleted
        user = await db.get_user(user_id)
        assert user is None

        await db.close()
