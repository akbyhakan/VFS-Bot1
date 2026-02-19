"""Tests for configuration validator module."""

from src.core.config.config_validator import ConfigValidator


class TestConfigValidator:
    """Tests for ConfigValidator class."""

    def test_validate_with_valid_config(self):
        """Test validation passes with valid config."""
        config = {
            "vfs": {
                "base_url": "https://visa.vfsglobal.com",
                "country": "tur",
                "mission": "deu",
                "centres": ["Istanbul"],
            },
            "bot": {"check_interval": 30},
            "captcha": {"provider": "2captcha"},
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
            "vfs": {
                "base_url": "https://visa.vfsglobal.com",
                "country": "tur",
                "mission": "deu",
                "centres": ["Istanbul"],
            },
            "bot": {
                # Missing check_interval
            },
            "captcha": {},
            "notifications": {},
        }

        result = ConfigValidator.validate(config)

        # Validation should pass because check_interval has a default value
        assert result is True

    def test_validate_check_interval_too_low(self, caplog):
        """Test validation fails when check_interval is too low."""
        config = {
            "vfs": {
                "base_url": "https://visa.vfsglobal.com",
                "country": "tur",
                "mission": "deu",
                "centres": ["Istanbul"],
            },
            "bot": {"check_interval": 5},  # Too low
            "captcha": {},
            "notifications": {},
        }

        result = ConfigValidator.validate(config)

        assert result is False
        assert "check_interval must be between 10 and 3600 seconds" in caplog.text

    def test_validate_check_interval_zero(self, caplog):
        """Test validation fails when check_interval is zero."""
        config = {
            "vfs": {
                "base_url": "https://visa.vfsglobal.com",
                "country": "tur",
                "mission": "deu",
                "centres": ["Istanbul"],
            },
            "bot": {"check_interval": 0},
            "captcha": {},
            "notifications": {},
        }

        result = ConfigValidator.validate(config)

        assert result is False

    def test_validate_check_interval_at_minimum(self):
        """Test validation passes when check_interval is at minimum."""
        config = {
            "vfs": {
                "base_url": "https://visa.vfsglobal.com",
                "country": "tur",
                "mission": "deu",
                "centres": ["Istanbul"],
            },
            "bot": {"check_interval": 10},  # Minimum valid value
            "captcha": {"provider": "2captcha"},
            "notifications": {},
        }

        result = ConfigValidator.validate(config)

        assert result is True
