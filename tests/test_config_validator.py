"""Tests for configuration validator module."""

from src.config_validator import ConfigValidator


class TestConfigValidator:
    """Tests for ConfigValidator class."""

    def test_validate_with_valid_config(self):
        """Test validation passes with valid config."""
        config = {
            "vfs": {"base_url": "https://visa.vfsglobal.com", "country": "tur", "mission": "deu"},
            "bot": {"check_interval": 30},
            "captcha": {"provider": "manual"},
            "notifications": {"telegram": {"enabled": True}},
        }

        result = ConfigValidator.validate(config)

        assert result is True

    def test_validate_with_missing_sections(self, caplog):
        """Test validation fails with missing sections."""
        config = {"vfs": {"base_url": "https://visa.vfsglobal.com"}}

        result = ConfigValidator.validate(config)

        assert result is False
        assert "Missing required section" in caplog.text

    def test_validate_with_missing_vfs_fields(self, caplog):
        """Test validation fails with missing VFS fields."""
        config = {
            "vfs": {
                "base_url": "https://visa.vfsglobal.com"
                # Missing country and mission
            },
            "bot": {"check_interval": 30},
            "captcha": {},
            "notifications": {},
        }

        result = ConfigValidator.validate(config)

        assert result is False
        assert "Missing vfs.country" in caplog.text
        assert "Missing vfs.mission" in caplog.text

    def test_validate_with_missing_bot_fields(self, caplog):
        """Test validation fails with missing bot fields."""
        config = {
            "vfs": {"base_url": "https://visa.vfsglobal.com", "country": "tur", "mission": "deu"},
            "bot": {
                # Missing check_interval
            },
            "captcha": {},
            "notifications": {},
        }

        result = ConfigValidator.validate(config)

        assert result is False
        assert "Missing bot.check_interval" in caplog.text

    def test_validate_check_interval_too_low(self, caplog):
        """Test validation fails when check_interval is too low."""
        config = {
            "vfs": {"base_url": "https://visa.vfsglobal.com", "country": "tur", "mission": "deu"},
            "bot": {"check_interval": 5},  # Too low
            "captcha": {},
            "notifications": {},
        }

        result = ConfigValidator.validate(config)

        assert result is False
        assert "check_interval must be >= 10 seconds" in caplog.text

    def test_validate_check_interval_zero(self, caplog):
        """Test validation fails when check_interval is zero."""
        config = {
            "vfs": {"base_url": "https://visa.vfsglobal.com", "country": "tur", "mission": "deu"},
            "bot": {"check_interval": 0},
            "captcha": {},
            "notifications": {},
        }

        result = ConfigValidator.validate(config)

        assert result is False

    def test_validate_check_interval_at_minimum(self):
        """Test validation passes when check_interval is at minimum."""
        config = {
            "vfs": {"base_url": "https://visa.vfsglobal.com", "country": "tur", "mission": "deu"},
            "bot": {"check_interval": 10},  # Minimum valid value
            "captcha": {},
            "notifications": {},
        }

        result = ConfigValidator.validate(config)

        assert result is True

    def test_required_sections_defined(self):
        """Test that required sections are properly defined."""
        assert "vfs" in ConfigValidator.REQUIRED_SECTIONS
        assert "bot" in ConfigValidator.REQUIRED_SECTIONS
        assert "captcha" in ConfigValidator.REQUIRED_SECTIONS
        assert "notifications" in ConfigValidator.REQUIRED_SECTIONS

    def test_vfs_required_fields_defined(self):
        """Test that VFS required fields are properly defined."""
        assert "base_url" in ConfigValidator.VFS_REQUIRED
        assert "country" in ConfigValidator.VFS_REQUIRED
        assert "mission" in ConfigValidator.VFS_REQUIRED

    def test_bot_required_fields_defined(self):
        """Test that bot required fields are properly defined."""
        assert "check_interval" in ConfigValidator.BOT_REQUIRED
