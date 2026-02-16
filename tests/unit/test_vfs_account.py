"""Tests for VFSAccount model and manager."""

from unittest.mock import MagicMock, patch

import pytest

from src.models.vfs_account import VFSAccount
from src.services.account.vfs_account_manager import VFSAccountManager
from src.services.otp_manager.webhook_token_manager import WebhookTokenManager


class TestVFSAccount:
    """Tests for VFSAccount dataclass."""

    def test_account_creation(self):
        """Test creating a VFS account."""
        account = VFSAccount(
            account_id="test_account",
            vfs_email="user@example.com",
            vfs_password="encrypted_password",
            phone_number="+905551234567",
            target_email="bot@example.com",
            webhook_token="tk_test123",
            webhook_url="https://api.example.com/webhook/sms/tk_test123",
        )

        assert account.account_id == "test_account"
        assert account.vfs_email == "user@example.com"
        assert account.phone_number == "+905551234567"
        assert account.is_active is True

    def test_account_to_dict(self):
        """Test converting account to dictionary."""
        account = VFSAccount(
            account_id="test_account",
            vfs_email="user@example.com",
            vfs_password="encrypted_password",
            phone_number="+905551234567",
            target_email="bot@example.com",
            webhook_token="tk_test123",
            webhook_url="https://api.example.com/webhook/sms/tk_test123",
            country="Netherlands",
        )

        data = account.to_dict()

        assert data["account_id"] == "test_account"
        assert data["vfs_email"] == "user@example.com"
        assert data["country"] == "Netherlands"
        assert data["is_active"] is True
        assert "created_at" in data


class TestVFSAccountManager:
    """Tests for VFSAccountManager."""

    @pytest.fixture
    def mock_webhook_manager(self):
        """Create a mock webhook manager."""
        manager = MagicMock(spec=WebhookTokenManager)
        manager.generate_token.return_value = "tk_mock123456"
        manager.register_token.return_value = MagicMock()
        manager.get_webhook_url.return_value = "https://api.example.com/webhook/sms/tk_mock123456"
        return manager

    @pytest.fixture
    def account_manager(self, mock_webhook_manager):
        """Create account manager with mock webhook manager."""
        return VFSAccountManager(webhook_token_manager=mock_webhook_manager)

    def test_initialization(self, mock_webhook_manager):
        """Test manager initialization."""
        manager = VFSAccountManager(webhook_token_manager=mock_webhook_manager)

        assert manager.webhook_manager == mock_webhook_manager
        assert len(manager._accounts) == 0

    def test_initialization_creates_webhook_manager_if_none(self):
        """Test that manager creates webhook manager if not provided."""
        manager = VFSAccountManager()

        assert manager.webhook_manager is not None
        assert isinstance(manager.webhook_manager, WebhookTokenManager)

    @patch("src.models.vfs_account.encrypt_password")
    def test_register_account(self, mock_encrypt, account_manager, mock_webhook_manager):
        """Test account registration."""
        mock_encrypt.return_value = "encrypted_password"

        account = account_manager.register_account(
            vfs_email="user@example.com",
            vfs_password="plain_password",
            phone_number="+905551234567",
            target_email="bot@example.com",
            country="Netherlands",
        )

        assert account.vfs_email == "user@example.com"
        assert account.phone_number == "+905551234567"
        assert account.country == "Netherlands"
        assert account.webhook_token == "tk_mock123456"
        assert account.webhook_url == "https://api.example.com/webhook/sms/tk_mock123456"

        # Verify password was encrypted
        mock_encrypt.assert_called_once_with("plain_password")
        assert account.vfs_password == "encrypted_password"

        # Verify webhook manager was called
        mock_webhook_manager.generate_token.assert_called_once()
        mock_webhook_manager.register_token.assert_called_once()

    @patch("src.models.vfs_account.encrypt_password")
    def test_register_account_duplicate_email_raises_error(self, mock_encrypt, account_manager):
        """Test that duplicate email raises error."""
        mock_encrypt.return_value = "encrypted_password"

        account_manager.register_account(
            vfs_email="user@example.com",
            vfs_password="password",
            phone_number="+905551234567",
            target_email="bot@example.com",
        )

        with pytest.raises(ValueError, match="Account with email .* already exists"):
            account_manager.register_account(
                vfs_email="user@example.com",
                vfs_password="password",
                phone_number="+905559876543",
                target_email="bot2@example.com",
            )

    @patch("src.models.vfs_account.encrypt_password")
    def test_register_account_duplicate_phone_raises_error(self, mock_encrypt, account_manager):
        """Test that duplicate phone raises error."""
        mock_encrypt.return_value = "encrypted_password"

        account_manager.register_account(
            vfs_email="user1@example.com",
            vfs_password="password",
            phone_number="+905551234567",
            target_email="bot@example.com",
        )

        with pytest.raises(ValueError, match="Account with phone .* already exists"):
            account_manager.register_account(
                vfs_email="user2@example.com",
                vfs_password="password",
                phone_number="+905551234567",
                target_email="bot2@example.com",
            )

    @patch("src.models.vfs_account.encrypt_password")
    def test_get_account(self, mock_encrypt, account_manager):
        """Test getting account by ID."""
        mock_encrypt.return_value = "encrypted_password"

        account = account_manager.register_account(
            vfs_email="user@example.com",
            vfs_password="password",
            phone_number="+905551234567",
            target_email="bot@example.com",
        )

        result = account_manager.get_account(account.account_id)

        assert result is not None
        assert result.account_id == account.account_id

    def test_get_account_not_found(self, account_manager):
        """Test getting non-existent account."""
        result = account_manager.get_account("non_existent")

        assert result is None

    @patch("src.models.vfs_account.encrypt_password")
    def test_get_account_by_email(self, mock_encrypt, account_manager):
        """Test getting account by email."""
        mock_encrypt.return_value = "encrypted_password"

        account_manager.register_account(
            vfs_email="user@example.com",
            vfs_password="password",
            phone_number="+905551234567",
            target_email="bot@example.com",
        )

        result = account_manager.get_account_by_email("user@example.com")

        assert result is not None
        assert result.vfs_email == "user@example.com"

    @patch("src.models.vfs_account.encrypt_password")
    def test_get_account_by_token(self, mock_encrypt, account_manager):
        """Test getting account by webhook token."""
        mock_encrypt.return_value = "encrypted_password"

        account = account_manager.register_account(
            vfs_email="user@example.com",
            vfs_password="password",
            phone_number="+905551234567",
            target_email="bot@example.com",
        )

        result = account_manager.get_account_by_token(account.webhook_token)

        assert result is not None
        assert result.webhook_token == account.webhook_token

    @patch("src.models.vfs_account.encrypt_password")
    def test_get_account_by_phone(self, mock_encrypt, account_manager):
        """Test getting account by phone number."""
        mock_encrypt.return_value = "encrypted_password"

        account_manager.register_account(
            vfs_email="user@example.com",
            vfs_password="password",
            phone_number="+905551234567",
            target_email="bot@example.com",
        )

        result = account_manager.get_account_by_phone("+905551234567")

        assert result is not None
        assert result.phone_number == "+905551234567"

    @patch("src.models.vfs_account.encrypt_password")
    def test_update_account(self, mock_encrypt, account_manager):
        """Test updating account fields."""
        mock_encrypt.return_value = "encrypted_password"

        account = account_manager.register_account(
            vfs_email="user@example.com",
            vfs_password="password",
            phone_number="+905551234567",
            target_email="bot@example.com",
        )

        updated = account_manager.update_account(
            account.account_id, country="Germany", visa_type="Business"
        )

        assert updated.country == "Germany"
        assert updated.visa_type == "Business"

    @patch("src.models.vfs_account.encrypt_password")
    def test_update_account_password(self, mock_encrypt, account_manager):
        """Test updating account password encrypts it."""
        mock_encrypt.return_value = "encrypted_password"

        account = account_manager.register_account(
            vfs_email="user@example.com",
            vfs_password="old_password",
            phone_number="+905551234567",
            target_email="bot@example.com",
        )

        mock_encrypt.return_value = "new_encrypted_password"

        updated = account_manager.update_account(account.account_id, vfs_password="new_password")

        assert updated.vfs_password == "new_encrypted_password"

    def test_update_account_not_found_raises_error(self, account_manager):
        """Test updating non-existent account raises error."""
        with pytest.raises(ValueError, match="Account not found"):
            account_manager.update_account("non_existent", country="Germany")

    @patch("src.models.vfs_account.encrypt_password")
    def test_deactivate_account(self, mock_encrypt, account_manager, mock_webhook_manager):
        """Test deactivating account."""
        mock_encrypt.return_value = "encrypted_password"

        account = account_manager.register_account(
            vfs_email="user@example.com",
            vfs_password="password",
            phone_number="+905551234567",
            target_email="bot@example.com",
        )

        account_manager.deactivate_account(account.account_id)

        assert account.is_active is False
        mock_webhook_manager.revoke_token.assert_called_once_with(account.webhook_token)

    def test_deactivate_account_not_found_raises_error(self, account_manager):
        """Test deactivating non-existent account raises error."""
        with pytest.raises(ValueError, match="Account not found"):
            account_manager.deactivate_account("non_existent")

    @patch("src.models.vfs_account.encrypt_password")
    def test_reactivate_account(self, mock_encrypt, account_manager, mock_webhook_manager):
        """Test reactivating account."""
        mock_encrypt.return_value = "encrypted_password"

        account = account_manager.register_account(
            vfs_email="user@example.com",
            vfs_password="password",
            phone_number="+905551234567",
            target_email="bot@example.com",
        )

        account_manager.deactivate_account(account.account_id)

        # Mock validate_token to return a mock token
        mock_token = MagicMock()
        mock_webhook_manager.validate_token.return_value = mock_token

        account_manager.reactivate_account(account.account_id)

        assert account.is_active is True
        assert mock_token.is_active is True

    @patch("src.models.vfs_account.encrypt_password")
    def test_list_accounts(self, mock_encrypt, account_manager):
        """Test listing accounts."""
        mock_encrypt.return_value = "encrypted_password"

        for i in range(3):
            account_manager.register_account(
                vfs_email=f"user{i}@example.com",
                vfs_password="password",
                phone_number=f"+90555123456{i}",
                target_email=f"bot{i}@example.com",
            )

        accounts = account_manager.list_accounts()

        assert len(accounts) == 3

    @patch("src.models.vfs_account.encrypt_password")
    def test_list_accounts_active_only(self, mock_encrypt, account_manager):
        """Test listing only active accounts."""
        mock_encrypt.return_value = "encrypted_password"

        account1 = account_manager.register_account(
            vfs_email="user1@example.com",
            vfs_password="password",
            phone_number="+905551234561",
            target_email="bot1@example.com",
        )

        account_manager.register_account(
            vfs_email="user2@example.com",
            vfs_password="password",
            phone_number="+905551234562",
            target_email="bot2@example.com",
        )

        account_manager.deactivate_account(account1.account_id)

        active_accounts = account_manager.list_accounts(active_only=True)
        all_accounts = account_manager.list_accounts(active_only=False)

        assert len(active_accounts) == 1
        assert len(all_accounts) == 2

    @patch("src.models.vfs_account.encrypt_password")
    @patch("src.models.vfs_account.decrypt_password")
    def test_get_decrypted_password(self, mock_decrypt, mock_encrypt, account_manager):
        """Test getting decrypted password."""
        mock_encrypt.return_value = "encrypted_password"
        mock_decrypt.return_value = "plain_password"

        account = account_manager.register_account(
            vfs_email="user@example.com",
            vfs_password="plain_password",
            phone_number="+905551234567",
            target_email="bot@example.com",
        )

        password = account_manager.get_decrypted_password(account.account_id)

        assert password == "plain_password"
        mock_decrypt.assert_called_once_with("encrypted_password")

    def test_get_decrypted_password_account_not_found(self, account_manager):
        """Test getting password for non-existent account."""
        password = account_manager.get_decrypted_password("non_existent")

        assert password is None

    @patch("src.models.vfs_account.encrypt_password")
    @patch("src.models.vfs_account.decrypt_password")
    def test_get_decrypted_password_decryption_error(
        self, mock_decrypt, mock_encrypt, account_manager
    ):
        """Test handling decryption error."""
        mock_encrypt.return_value = "encrypted_password"
        mock_decrypt.side_effect = Exception("Decryption failed")

        account = account_manager.register_account(
            vfs_email="user@example.com",
            vfs_password="password",
            phone_number="+905551234567",
            target_email="bot@example.com",
        )

        password = account_manager.get_decrypted_password(account.account_id)

        assert password is None
