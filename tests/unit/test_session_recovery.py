"""Tests for session_recovery module."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.services.session_recovery import SessionRecovery


class TestSessionRecovery:
    """Tests for SessionRecovery class."""

    @pytest.fixture
    def temp_checkpoint_file(self, tmp_path):
        """Create a temporary checkpoint file."""
        return tmp_path / "session_checkpoint.json"

    def test_init_creates_directory(self, temp_checkpoint_file):
        """Test that initialization creates the data directory."""
        recovery = SessionRecovery(str(temp_checkpoint_file))

        assert recovery is not None
        assert temp_checkpoint_file.parent.exists()

    def test_save_checkpoint_valid_step(self, temp_checkpoint_file):
        """Test saving a checkpoint with a valid step."""
        recovery = SessionRecovery(str(temp_checkpoint_file))

        recovery.save_checkpoint(
            step="logged_in", user_id=123, context={"email": "test@example.com"}
        )

        assert temp_checkpoint_file.exists()

        # Load checkpoint using recovery method (handles encryption)
        data = recovery.load_checkpoint()

        assert data["step"] == "logged_in"
        assert data["user_id"] == 123
        assert data["context"]["email"] == "test@example.com"
        assert "timestamp" in data

    def test_save_checkpoint_unknown_step(self, temp_checkpoint_file):
        """Test saving a checkpoint with an unknown step."""
        recovery = SessionRecovery(str(temp_checkpoint_file))

        # Should still save, but log a warning
        recovery.save_checkpoint(step="unknown_step", user_id=123, context={})

        assert temp_checkpoint_file.exists()

    def test_load_checkpoint_exists(self, temp_checkpoint_file):
        """Test loading an existing checkpoint."""
        recovery = SessionRecovery(str(temp_checkpoint_file))

        # Save a checkpoint
        recovery.save_checkpoint(
            step="logged_in", user_id=123, context={"email": "test@example.com"}
        )

        # Load it
        checkpoint = recovery.load_checkpoint()

        assert checkpoint is not None
        assert checkpoint["step"] == "logged_in"
        assert checkpoint["user_id"] == 123

    def test_load_checkpoint_not_exists(self, temp_checkpoint_file):
        """Test loading when checkpoint doesn't exist."""
        recovery = SessionRecovery(str(temp_checkpoint_file))

        checkpoint = recovery.load_checkpoint()

        assert checkpoint is None

    def test_load_checkpoint_expired(self, temp_checkpoint_file):
        """Test that old checkpoints are ignored."""
        recovery = SessionRecovery(str(temp_checkpoint_file))

        # Create an old checkpoint (2 hours ago)
        old_timestamp = datetime.now() - timedelta(hours=2)
        old_checkpoint = {
            "step": "logged_in",
            "step_index": 1,
            "user_id": 123,
            "timestamp": old_timestamp.isoformat(),
            "context": {},
        }
        temp_checkpoint_file.write_text(json.dumps(old_checkpoint))

        # Load should return None for expired checkpoint
        checkpoint = recovery.load_checkpoint()

        assert checkpoint is None
        # Checkpoint file should be deleted
        assert not temp_checkpoint_file.exists()

    def test_clear_checkpoint(self, temp_checkpoint_file):
        """Test clearing a checkpoint."""
        recovery = SessionRecovery(str(temp_checkpoint_file))

        # Save a checkpoint
        recovery.save_checkpoint(step="logged_in", user_id=123, context={})

        # Clear it
        recovery.clear_checkpoint()

        assert not temp_checkpoint_file.exists()
        assert recovery._current_checkpoint is None

    def test_can_resume_from_valid(self, temp_checkpoint_file):
        """Test can_resume_from with valid checkpoint."""
        recovery = SessionRecovery(str(temp_checkpoint_file))

        # Save checkpoint at "personal_info_filled"
        recovery.save_checkpoint(step="personal_info_filled", user_id=123, context={})

        # Should be able to resume from earlier steps
        assert recovery.can_resume_from("logged_in") is True
        assert recovery.can_resume_from("centre_selected") is True
        assert recovery.can_resume_from("personal_info_filled") is True

    def test_can_resume_from_invalid(self, temp_checkpoint_file):
        """Test can_resume_from with later step."""
        recovery = SessionRecovery(str(temp_checkpoint_file))

        # Save checkpoint at "logged_in"
        recovery.save_checkpoint(step="logged_in", user_id=123, context={})

        # Should not be able to resume from later steps
        assert recovery.can_resume_from("payment_completed") is False

    def test_can_resume_from_no_checkpoint(self, temp_checkpoint_file):
        """Test can_resume_from when no checkpoint exists."""
        recovery = SessionRecovery(str(temp_checkpoint_file))

        assert recovery.can_resume_from("logged_in") is False

    def test_get_resume_step(self, temp_checkpoint_file):
        """Test getting the resume step."""
        recovery = SessionRecovery(str(temp_checkpoint_file))

        recovery.save_checkpoint(step="logged_in", user_id=123, context={})

        step = recovery.get_resume_step()

        assert step == "logged_in"

    def test_get_resume_step_no_checkpoint(self, temp_checkpoint_file):
        """Test getting resume step when no checkpoint exists."""
        recovery = SessionRecovery(str(temp_checkpoint_file))

        step = recovery.get_resume_step()

        assert step is None

    def test_get_resume_context(self, temp_checkpoint_file):
        """Test getting the resume context."""
        recovery = SessionRecovery(str(temp_checkpoint_file))

        context_data = {"email": "test@example.com", "centre": "Amsterdam"}
        recovery.save_checkpoint(step="logged_in", user_id=123, context=context_data)

        context = recovery.get_resume_context()

        assert context == context_data

    def test_get_resume_context_no_checkpoint(self, temp_checkpoint_file):
        """Test getting resume context when no checkpoint exists."""
        recovery = SessionRecovery(str(temp_checkpoint_file))

        context = recovery.get_resume_context()

        assert context == {}

    def test_checkpoint_steps_order(self):
        """Test that checkpoint steps are in correct order."""
        recovery = SessionRecovery()

        steps = recovery.CHECKPOINT_STEPS

        # Verify some key steps are in logical order
        assert steps.index("initialized") < steps.index("logged_in")
        assert steps.index("logged_in") < steps.index("personal_info_filled")
        assert steps.index("personal_info_filled") < steps.index("payment_completed")
        assert steps.index("payment_completed") < steps.index("completed")

    def test_checkpoint_timezone_aware(self, temp_checkpoint_file):
        """Test that checkpoints are saved with timezone-aware UTC timestamps."""
        from datetime import timezone

        recovery = SessionRecovery(str(temp_checkpoint_file))

        recovery.save_checkpoint(step="logged_in", user_id=123, context={"test": "data"})

        # Load and verify timestamp is timezone-aware
        checkpoint = recovery.load_checkpoint()
        assert checkpoint is not None

        timestamp_str = checkpoint["timestamp"]
        parsed_dt = datetime.fromisoformat(timestamp_str)

        # Check if timestamp includes timezone info (ends with +00:00 or has timezone)
        # ISO format with timezone should either have +HH:MM or Z suffix
        assert (
            parsed_dt.tzinfo is not None or "+00:00" in timestamp_str or timestamp_str.endswith("Z")
        )

    def test_checkpoint_age_calculation_utc(self, temp_checkpoint_file):
        """Test that checkpoint age is calculated correctly using UTC."""
        from datetime import timezone

        recovery = SessionRecovery(str(temp_checkpoint_file))

        # Save a checkpoint
        recovery.save_checkpoint(step="logged_in", user_id=123, context={})

        # Should load successfully (not expired yet)
        checkpoint = recovery.load_checkpoint()
        assert checkpoint is not None
        assert checkpoint["step"] == "logged_in"

    def test_backward_compat_naive_checkpoint(self, temp_checkpoint_file):
        """Test backward compatibility with old timezone-naive checkpoints."""
        recovery = SessionRecovery(str(temp_checkpoint_file))

        # Manually create an old-style naive checkpoint (without timezone)
        old_checkpoint = {
            "step": "logged_in",
            "step_index": 1,
            "user_id": 123,
            "timestamp": "2024-01-01T12:00:00",  # No timezone info
            "context": {"test": "old_data"},
        }

        with open(temp_checkpoint_file, "w") as f:
            json.dump(old_checkpoint, f)

        # Should still be able to load (will be very old and likely ignored)
        # This tests that the code doesn't crash on old naive timestamps
        checkpoint = recovery.load_checkpoint()
        # Will be None because it's > 1 hour old, but shouldn't raise exception
        assert checkpoint is None or checkpoint["step"] == "logged_in"

    def test_encrypted_checkpoint_save_and_load(self, temp_checkpoint_file, monkeypatch):
        """Test saving and loading encrypted checkpoints."""
        from cryptography.fernet import Fernet

        # Set encryption key
        encryption_key = Fernet.generate_key().decode()
        monkeypatch.setenv("ENCRYPTION_KEY", encryption_key)

        recovery = SessionRecovery(str(temp_checkpoint_file))

        # Save a checkpoint
        recovery.save_checkpoint(
            step="logged_in",
            user_id=123,
            context={"email": "test@example.com", "password": "secret"},
        )

        assert temp_checkpoint_file.exists()

        # Verify file is encrypted by checking for Fernet token prefix
        raw_data = temp_checkpoint_file.read_bytes()
        # Fernet tokens start with version byte (0x80) followed by timestamp
        # The base64 encoding typically starts with 'gAAAAA'
        assert raw_data.startswith(b"gAAAAA"), "File should be encrypted with Fernet"

        # Load checkpoint - should decrypt successfully
        checkpoint = recovery.load_checkpoint()

        assert checkpoint is not None
        assert checkpoint["step"] == "logged_in"
        assert checkpoint["user_id"] == 123
        assert checkpoint["context"]["email"] == "test@example.com"
        assert checkpoint["context"]["password"] == "secret"

    def test_init_raises_without_encryption_key(self, temp_checkpoint_file, monkeypatch):
        """Test that SessionRecovery raises ConfigurationError when ENCRYPTION_KEY is not set."""
        from src.core.exceptions import ConfigurationError

        # Remove encryption key
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)

        # Should raise ConfigurationError when require_encryption=True (default)
        with pytest.raises(ConfigurationError) as exc_info:
            SessionRecovery(str(temp_checkpoint_file))

        assert "ENCRYPTION_KEY" in str(exc_info.value)
        assert "required" in str(exc_info.value).lower()

    def test_require_encryption_false_allows_plaintext(self, temp_checkpoint_file, monkeypatch):
        """Test that require_encryption=False allows plaintext fallback for testing."""
        # Remove encryption key
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)

        # Should NOT raise when require_encryption=False
        recovery = SessionRecovery(str(temp_checkpoint_file), require_encryption=False)

        # Save a checkpoint
        recovery.save_checkpoint(
            step="logged_in", user_id=123, context={"email": "test@example.com"}
        )

        assert temp_checkpoint_file.exists()

        # Verify file is NOT encrypted (readable as JSON)
        raw_data = temp_checkpoint_file.read_bytes()
        data = json.loads(raw_data.decode("utf-8"))
        assert data["step"] == "logged_in"

        # Load checkpoint - should work
        checkpoint = recovery.load_checkpoint()
        assert checkpoint is not None
        assert checkpoint["step"] == "logged_in"

    def test_backward_compat_unencrypted_to_encrypted(self, temp_checkpoint_file, monkeypatch):
        """Test backward compatibility: reading old unencrypted checkpoint migrates to encrypted format."""
        # First create a plaintext checkpoint file manually (simulating legacy data)
        legacy_checkpoint = {
            "step": "logged_in",
            "step_index": 1,
            "user_id": 123,
            "timestamp": datetime.now().isoformat(),
            "context": {"email": "test@example.com", "password": "legacy_secret"},
        }

        with open(temp_checkpoint_file, "w") as f:
            json.dump(legacy_checkpoint, f)

        # Verify it's plaintext
        raw_data_before = temp_checkpoint_file.read_bytes()
        assert b"legacy_secret" in raw_data_before

        # Now enable encryption and create recovery instance
        from cryptography.fernet import Fernet

        encryption_key = Fernet.generate_key().decode()
        monkeypatch.setenv("ENCRYPTION_KEY", encryption_key)

        recovery_encrypted = SessionRecovery(str(temp_checkpoint_file))
        checkpoint = recovery_encrypted.load_checkpoint()

        # Should successfully load the unencrypted checkpoint
        assert checkpoint is not None
        assert checkpoint["step"] == "logged_in"
        assert checkpoint["user_id"] == 123
        assert checkpoint["context"]["password"] == "legacy_secret"

        # Verify the file is now encrypted (re-encrypted on load)
        raw_data_after = temp_checkpoint_file.read_bytes()
        
        # Verify it's encrypted by checking that plaintext is NOT visible
        assert b"legacy_secret" not in raw_data_after, "Plaintext should not be visible in encrypted file"
        
        # Also verify it's not the same as the original plaintext JSON
        assert raw_data_after != raw_data_before, "File should be different after re-encryption"

        # Verify it can still be loaded
        recovery2 = SessionRecovery(str(temp_checkpoint_file))
        checkpoint2 = recovery2.load_checkpoint()
        assert checkpoint2 is not None
        assert checkpoint2["context"]["password"] == "legacy_secret"

    def test_encrypted_checkpoint_wrong_key(self, temp_checkpoint_file, monkeypatch):
        """Test that loading with wrong encryption key fails gracefully."""
        from cryptography.fernet import Fernet

        # Save with one key
        encryption_key_1 = Fernet.generate_key().decode()
        monkeypatch.setenv("ENCRYPTION_KEY", encryption_key_1)

        recovery = SessionRecovery(str(temp_checkpoint_file))
        recovery.save_checkpoint(
            step="logged_in", user_id=123, context={"email": "test@example.com"}
        )

        # Try to load with different key
        encryption_key_2 = Fernet.generate_key().decode()
        monkeypatch.setenv("ENCRYPTION_KEY", encryption_key_2)

        recovery_wrong_key = SessionRecovery(str(temp_checkpoint_file))
        checkpoint = recovery_wrong_key.load_checkpoint()

        # Should fail to decrypt and return None (error handled gracefully)
        assert checkpoint is None

    def test_encrypted_checkpoint_sensitive_data(self, temp_checkpoint_file, monkeypatch):
        """Test that sensitive data in context is encrypted."""
        from cryptography.fernet import Fernet

        # Set encryption key
        encryption_key = Fernet.generate_key().decode()
        monkeypatch.setenv("ENCRYPTION_KEY", encryption_key)

        recovery = SessionRecovery(str(temp_checkpoint_file))

        # Save checkpoint with sensitive data
        sensitive_context = {
            "email": "user@example.com",
            "password": "supersecret123",
            "token": "auth-token-xyz",
            "user_id": 456,
        }
        recovery.save_checkpoint(step="logged_in", user_id=123, context=sensitive_context)

        # Read raw file data
        raw_data = temp_checkpoint_file.read_bytes()

        # Verify sensitive data is NOT in plaintext
        raw_text = raw_data.decode("utf-8", errors="ignore")
        assert "supersecret123" not in raw_text
        assert "auth-token-xyz" not in raw_text
        assert "user@example.com" not in raw_text

        # But should be retrievable when decrypted
        checkpoint = recovery.load_checkpoint()
        assert checkpoint is not None
        assert checkpoint["context"]["password"] == "supersecret123"
        assert checkpoint["context"]["token"] == "auth-token-xyz"
        assert checkpoint["context"]["email"] == "user@example.com"
