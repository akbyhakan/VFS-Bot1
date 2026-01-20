"""Tests for database batch query functionality."""

import pytest
import tempfile
import os
from pathlib import Path
from src.models.database import Database


@pytest.fixture
async def temp_db():
    """Create a temporary database for testing."""
    # Use a temporary file for the database
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_file.close()
    db_path = temp_file.name
    
    db = Database(db_path)
    await db.connect()
    
    yield db
    
    await db.close()
    
    # Clean up
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.mark.asyncio
async def test_get_personal_details_batch_empty(temp_db):
    """Test batch query with empty list."""
    result = await temp_db.get_personal_details_batch([])
    assert result == {}


@pytest.mark.asyncio
async def test_get_personal_details_batch_single(temp_db):
    """Test batch query with single user."""
    # Create a user
    user_id = await temp_db.add_user(
        email="test@example.com",
        password="testpass123",
        centre="Istanbul",
        category="Tourist",
        subcategory="Single Entry"
    )
    
    # Add personal details
    details = {
        "first_name": "John",
        "last_name": "Doe",
        "passport_number": "A12345678",
        "email": "test@example.com",
    }
    await temp_db.add_personal_details(user_id, details)
    
    # Batch query
    result = await temp_db.get_personal_details_batch([user_id])
    
    assert len(result) == 1
    assert user_id in result
    assert result[user_id]["first_name"] == "John"
    assert result[user_id]["last_name"] == "Doe"


@pytest.mark.asyncio
async def test_get_personal_details_batch_multiple(temp_db):
    """Test batch query with multiple users."""
    # Create multiple users
    user1_id = await temp_db.add_user(
        email="user1@example.com",
        password="pass1",
        centre="Istanbul",
        category="Tourist",
        subcategory="Single Entry"
    )
    
    user2_id = await temp_db.add_user(
        email="user2@example.com",
        password="pass2",
        centre="Ankara",
        category="Business",
        subcategory="Multiple Entry"
    )
    
    user3_id = await temp_db.add_user(
        email="user3@example.com",
        password="pass3",
        centre="Izmir",
        category="Student",
        subcategory="Single Entry"
    )
    
    # Add personal details
    await temp_db.add_personal_details(user1_id, {
        "first_name": "Alice",
        "last_name": "Smith",
        "passport_number": "P111",
        "email": "user1@example.com",
    })
    
    await temp_db.add_personal_details(user2_id, {
        "first_name": "Bob",
        "last_name": "Jones",
        "passport_number": "P222",
        "email": "user2@example.com",
    })
    
    await temp_db.add_personal_details(user3_id, {
        "first_name": "Charlie",
        "last_name": "Brown",
        "passport_number": "P333",
        "email": "user3@example.com",
    })
    
    # Batch query all three
    result = await temp_db.get_personal_details_batch([user1_id, user2_id, user3_id])
    
    assert len(result) == 3
    assert result[user1_id]["first_name"] == "Alice"
    assert result[user2_id]["first_name"] == "Bob"
    assert result[user3_id]["first_name"] == "Charlie"


@pytest.mark.asyncio
async def test_get_personal_details_batch_missing_users(temp_db):
    """Test batch query with some non-existent users."""
    # Create one user
    user_id = await temp_db.add_user(
        email="test@example.com",
        password="testpass",
        centre="Istanbul",
        category="Tourist",
        subcategory="Single Entry"
    )
    
    await temp_db.add_personal_details(user_id, {
        "first_name": "John",
        "last_name": "Doe",
        "passport_number": "P123",
        "email": "test@example.com",
    })
    
    # Query with mix of existing and non-existing IDs
    result = await temp_db.get_personal_details_batch([user_id, 9999, 8888])
    
    # Should only return the existing user
    assert len(result) == 1
    assert user_id in result
    assert 9999 not in result
    assert 8888 not in result


@pytest.mark.asyncio
async def test_get_personal_details_batch_invalid_ids():
    """Test batch query with invalid user IDs."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_file.close()
    db_path = temp_file.name
    
    db = Database(db_path)
    await db.connect()
    
    try:
        # Test with invalid IDs (negative, zero)
        with pytest.raises(ValueError, match="Invalid user_id"):
            await db.get_personal_details_batch([0])
        
        with pytest.raises(ValueError, match="Invalid user_id"):
            await db.get_personal_details_batch([-1])
        
        with pytest.raises(ValueError, match="Invalid user_id"):
            await db.get_personal_details_batch([1, -5, 3])
    finally:
        await db.close()
        try:
            os.unlink(db_path)
        except OSError:
            pass
