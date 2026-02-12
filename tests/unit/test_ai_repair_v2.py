"""Tests for AIRepairV2 - structured output AI repair."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
import yaml

from src.resilience.ai_repair_v2 import AIRepairV2, RepairResult


class TestRepairResultModel:
    """Tests for RepairResult Pydantic model."""

    def test_repair_result_validation_success(self):
        """Test RepairResult model validates correct data."""
        result = RepairResult(
            is_found=True,
            new_selector="#email-input",
            confidence=0.85,
            reason="Found exact match by ID",
        )

        assert result.is_found is True
        assert result.new_selector == "#email-input"
        assert result.confidence == 0.85
        assert result.reason == "Found exact match by ID"

    def test_repair_result_confidence_bounds(self):
        """Test confidence must be between 0.0 and 1.0."""
        # Valid bounds
        RepairResult(is_found=True, new_selector="#test", confidence=0.0, reason="test")
        RepairResult(is_found=True, new_selector="#test", confidence=1.0, reason="test")

        # Invalid bounds
        with pytest.raises(ValueError):
            RepairResult(
                is_found=True, new_selector="#test", confidence=-0.1, reason="test"
            )

        with pytest.raises(ValueError):
            RepairResult(
                is_found=True, new_selector="#test", confidence=1.1, reason="test"
            )


class TestAIRepairV2Initialization:
    """Tests for AIRepairV2 initialization."""

    @patch.dict("os.environ", {}, clear=True)
    def test_init_without_api_key_disables_repair(self):
        """Test initialization without GEMINI_API_KEY disables repair."""
        repair = AIRepairV2()

        assert repair.enabled is False
        assert repair.client is None

    @patch.dict("os.environ", {"GEMINI_API_KEY": "test_key"})
    @patch("src.resilience.ai_repair_v2.genai")
    def test_init_with_api_key_enables_repair(self, mock_genai):
        """Test initialization with GEMINI_API_KEY enables repair."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        repair = AIRepairV2()

        assert repair.enabled is True
        assert repair.client == mock_client

    def test_init_with_custom_model(self):
        """Test initialization with custom model name."""
        repair = AIRepairV2(model_name="gemini-pro")

        assert repair.model_name == "gemini-pro"

    def test_init_with_custom_temperature(self):
        """Test initialization with custom temperature."""
        repair = AIRepairV2(temperature=0.5)

        assert repair.temperature == 0.5


class TestHTMLSanitization:
    """Tests for HTML sanitization."""

    def test_sanitize_removes_script_tags(self):
        """Test script tags and contents are removed."""
        html = '<script>alert("secret")</script><div>content</div>'
        sanitized = AIRepairV2._sanitize_html(html)

        assert "secret" not in sanitized
        assert "<script>" not in sanitized
        assert "<div>content</div>" in sanitized

    def test_sanitize_removes_style_tags(self):
        """Test style tags and contents are removed."""
        html = "<style>.secret { color: red; }</style><div>content</div>"
        sanitized = AIRepairV2._sanitize_html(html)

        assert ".secret" not in sanitized
        assert "<style>" not in sanitized

    def test_sanitize_redacts_input_values(self):
        """Test input values are redacted."""
        html = '<input type="text" value="sensitive_data">'
        sanitized = AIRepairV2._sanitize_html(html)

        assert "sensitive_data" not in sanitized
        assert "[redacted]" in sanitized

    def test_sanitize_redacts_textarea_contents(self):
        """Test textarea contents are redacted."""
        html = "<textarea>sensitive content</textarea>"
        sanitized = AIRepairV2._sanitize_html(html)

        assert "sensitive content" not in sanitized
        assert "[redacted]" in sanitized

    def test_sanitize_removes_data_attributes(self):
        """Test data-* attributes are removed."""
        html = '<div data-user-id="123" data-token="xyz">content</div>'
        sanitized = AIRepairV2._sanitize_html(html)

        assert "data-user-id" not in sanitized
        assert "data-token" not in sanitized

    def test_sanitize_removes_event_handlers(self):
        """Test inline event handlers are removed."""
        html = '<button onclick="doSomething()">Click</button>'
        sanitized = AIRepairV2._sanitize_html(html)

        assert "onclick" not in sanitized


class TestRepairSelector:
    """Tests for repair_selector method."""

    @pytest.mark.asyncio
    async def test_repair_selector_not_enabled(self):
        """Test repair_selector returns None when not enabled."""
        repair = AIRepairV2()
        repair.enabled = False

        result = await repair.repair_selector(
            "<html></html>", "#old-selector", "Email input"
        )

        assert result is None

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test_key"})
    @patch("src.resilience.ai_repair_v2.genai")
    async def test_repair_selector_returns_structured_result(self, mock_genai):
        """Test repair_selector returns RepairResult with structured data."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "is_found": True,
                "new_selector": "#new-email-input",
                "confidence": 0.9,
                "reason": "Found by ID attribute",
            }
        )

        mock_client.models.generate_content = MagicMock(return_value=mock_response)
        mock_genai.Client.return_value = mock_client

        repair = AIRepairV2()
        result = await repair.repair_selector(
            "<html><input id='new-email-input'></html>",
            "#old-email",
            "Email input field",
        )

        assert result is not None
        assert isinstance(result, RepairResult)
        assert result.is_found is True
        assert result.new_selector == "#new-email-input"
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test_key"})
    @patch("src.resilience.ai_repair_v2.genai")
    async def test_repair_selector_filters_low_confidence(self, mock_genai):
        """Test repair_selector filters results below confidence threshold."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "is_found": True,
                "new_selector": "#maybe-email",
                "confidence": 0.3,  # Below threshold of 0.7
                "reason": "Not very confident",
            }
        )

        mock_client.models.generate_content = MagicMock(return_value=mock_response)
        mock_genai.Client.return_value = mock_client

        repair = AIRepairV2()
        result = await repair.repair_selector(
            "<html></html>", "#old-email", "Email input"
        )

        assert result is None  # Filtered due to low confidence

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test_key"})
    @patch("src.resilience.ai_repair_v2.genai")
    async def test_repair_selector_truncates_large_html(self, mock_genai):
        """Test repair_selector truncates HTML exceeding max size."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "is_found": True,
                "new_selector": "#test",
                "confidence": 0.8,
                "reason": "test",
            }
        )

        mock_client.models.generate_content = MagicMock(return_value=mock_response)
        mock_genai.Client.return_value = mock_client

        repair = AIRepairV2()

        large_html = "<html>" + ("x" * 100000) + "</html>"
        await repair.repair_selector(large_html, "#old", "Test element")

        # Check that truncated HTML was passed
        call_args = mock_client.models.generate_content.call_args
        prompt = call_args[1]["contents"]

        # HTML should be truncated to max size (50,000)
        assert len(prompt) < len(large_html)

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test_key"})
    @patch("src.resilience.ai_repair_v2.genai")
    async def test_repair_selector_graceful_on_error(self, mock_genai):
        """Test repair_selector handles errors gracefully."""
        mock_client = MagicMock()
        mock_client.models.generate_content = MagicMock(
            side_effect=Exception("API error")
        )
        mock_genai.Client.return_value = mock_client

        repair = AIRepairV2()
        result = await repair.repair_selector(
            "<html></html>", "#old", "Test element"
        )

        assert result is None


class TestPersistToYAML:
    """Tests for persist_to_yaml method."""

    def test_persist_to_yaml_adds_to_fallbacks(self, tmp_path):
        """Test persist_to_yaml adds AI suggestion to fallbacks."""
        yaml_file = tmp_path / "selectors.yaml"
        yaml_data = {
            "defaults": {
                "login": {
                    "email_input": {
                        "primary": "#email",
                        "fallbacks": ["#user-email"],
                    }
                }
            }
        }
        yaml_file.write_text(yaml.dump(yaml_data))

        repair = AIRepairV2(selectors_file=str(yaml_file))
        success = repair.persist_to_yaml("login.email_input", "#new-email")

        assert success is True

        # Read updated YAML
        with open(yaml_file) as f:
            updated = yaml.safe_load(f)

        fallbacks = updated["defaults"]["login"]["email_input"]["fallbacks"]
        assert "#new-email" in fallbacks
        assert fallbacks[0] == "#new-email"  # Added at the beginning

    def test_persist_to_yaml_creates_new_entry(self, tmp_path):
        """Test persist_to_yaml creates new entry if doesn't exist."""
        yaml_file = tmp_path / "selectors.yaml"
        yaml_data = {"defaults": {"login": {}}}
        yaml_file.write_text(yaml.dump(yaml_data))

        repair = AIRepairV2(selectors_file=str(yaml_file))
        success = repair.persist_to_yaml("login.new_field", "#new-selector")

        assert success is True

        with open(yaml_file) as f:
            updated = yaml.safe_load(f)

        assert updated["defaults"]["login"]["new_field"]["primary"] == "#new-selector"

    def test_persist_to_yaml_file_not_found(self, tmp_path):
        """Test persist_to_yaml returns False when file doesn't exist."""
        yaml_file = tmp_path / "nonexistent.yaml"

        repair = AIRepairV2(selectors_file=str(yaml_file))
        success = repair.persist_to_yaml("login.email", "#test")

        assert success is False


class TestPromptBuilding:
    """Tests for prompt building."""

    def test_build_prompt_includes_all_info(self):
        """Test _build_prompt includes broken selector, description, and HTML."""
        repair = AIRepairV2()

        prompt = repair._build_prompt(
            broken_selector="#old-email",
            element_description="Email input field",
            html_content="<html><input id='email'></html>",
        )

        assert "#old-email" in prompt
        assert "Email input field" in prompt
        assert "<input id='email'>" in prompt
        assert "JSON" in prompt  # Should mention JSON output format


class TestGracefulDegradation:
    """Tests for graceful degradation."""

    @pytest.mark.asyncio
    async def test_graceful_degradation_no_genai_package(self):
        """Test graceful degradation when google-genai not installed."""
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test_key"}):
            with patch("src.resilience.ai_repair_v2.genai", None):
                # Should not raise ImportError during init
                repair = AIRepairV2()

                # Should return None during repair
                result = await repair.repair_selector(
                    "<html></html>", "#test", "Test"
                )
                assert result is None
