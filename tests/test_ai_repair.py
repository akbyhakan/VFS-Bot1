"""Tests for AI-powered selector auto-repair."""

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
import yaml

from src.utils.ai_selector_repair import AISelectorRepair


@pytest.fixture
def temp_selectors_file(tmp_path):
    """Create a temporary selectors file."""
    selectors_content = {
        "version": "test-1.0",
        "login": {"email_input": {"primary": "input#email", "fallbacks": ["input[type='email']"]}},
    }

    selectors_file = tmp_path / "selectors.yaml"
    with open(selectors_file, "w") as f:
        yaml.dump(selectors_content, f)

    return selectors_file


def test_ai_repair_init_no_api_key(temp_selectors_file):
    """Test initialization without API key."""
    with patch.dict(os.environ, {}, clear=True):
        repair = AISelectorRepair(str(temp_selectors_file))

        assert repair.enabled is False
        assert repair.model is None


def test_ai_repair_init_with_api_key(temp_selectors_file):
    """Test initialization with API key."""
    # Mock the entire google.generativeai module before import
    import sys

    mock_genai = MagicMock()

    with patch.dict(sys.modules, {"google.generativeai": mock_genai}):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            mock_model = MagicMock()
            mock_genai.GenerativeModel.return_value = mock_model

            repair = AISelectorRepair(str(temp_selectors_file))

            assert repair.enabled is True
            assert repair.model is not None
            mock_genai.configure.assert_called_with(api_key="test-key")


def test_ai_repair_init_import_error(temp_selectors_file):
    """Test graceful handling when google-generativeai is not installed."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
        # Simulate ImportError by removing from sys.modules and making import fail
        import sys

        original_import = __builtins__["__import__"]

        def mock_import(name, *args, **kwargs):
            if "google.generativeai" in name:
                raise ImportError("No module named 'google.generativeai'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            repair = AISelectorRepair(str(temp_selectors_file))

            # Should gracefully degrade
            assert repair.enabled is False


@pytest.mark.asyncio
async def test_suggest_selector_disabled(temp_selectors_file):
    """Test suggest_selector when AI repair is disabled."""
    repair = AISelectorRepair(str(temp_selectors_file))
    repair.enabled = False

    mock_page = AsyncMock()

    result = await repair.suggest_selector(mock_page, "login.email_input", "Email Input")

    assert result is None


@pytest.mark.asyncio
async def test_suggest_selector_success(temp_selectors_file):
    """Test successful selector suggestion."""
    import sys

    mock_genai = MagicMock()

    with patch.dict(sys.modules, {"google.generativeai": mock_genai}):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            # Mock model response
            mock_response = MagicMock()
            mock_response.text = "input#new-email-field"

            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model

            repair = AISelectorRepair(str(temp_selectors_file))

            # Mock page
            mock_page = AsyncMock()
            mock_page.content.return_value = "<html><body>Test</body></html>"
            mock_page.wait_for_selector = AsyncMock()  # Validation succeeds

            result = await repair.suggest_selector(mock_page, "login.email_input", "Email Input")

            assert result == "input#new-email-field"


@pytest.mark.asyncio
async def test_suggest_selector_validation_fails(temp_selectors_file):
    """Test suggestion when validation fails."""
    import sys

    mock_genai = MagicMock()

    with patch.dict(sys.modules, {"google.generativeai": mock_genai}):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            # Mock model response
            mock_response = MagicMock()
            mock_response.text = "input#invalid-selector"

            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model

            repair = AISelectorRepair(str(temp_selectors_file))

            # Mock page - validation fails
            mock_page = AsyncMock()
            mock_page.content.return_value = "<html><body>Test</body></html>"
            mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Not found"))

            result = await repair.suggest_selector(mock_page, "login.email_input", "Email Input")

            assert result is None


@pytest.mark.asyncio
async def test_suggest_selector_empty_response(temp_selectors_file):
    """Test handling of empty AI response."""
    import sys

    mock_genai = MagicMock()

    with patch.dict(sys.modules, {"google.generativeai": mock_genai}):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            # Mock empty response
            mock_response = MagicMock()
            mock_response.text = ""

            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model

            repair = AISelectorRepair(str(temp_selectors_file))

            mock_page = AsyncMock()
            mock_page.content.return_value = "<html><body>Test</body></html>"

            result = await repair.suggest_selector(mock_page, "login.email_input", "Email Input")

            assert result is None


def test_build_prompt(temp_selectors_file):
    """Test prompt building."""
    repair = AISelectorRepair(str(temp_selectors_file))

    prompt = repair._build_prompt(
        "login.email_input", "Email Input Field", "<html><body><input id='email' /></body></html>"
    )

    assert "login.email_input" in prompt
    assert "Email Input Field" in prompt
    assert "<html>" in prompt
    assert "CSS selector" in prompt


@pytest.mark.asyncio
async def test_validate_suggestion_success(temp_selectors_file):
    """Test successful validation."""
    repair = AISelectorRepair(str(temp_selectors_file))

    mock_page = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()

    result = await repair._validate_suggestion(mock_page, "input#email")

    assert result is True
    mock_page.wait_for_selector.assert_called_with("input#email", timeout=5000, state="visible")


@pytest.mark.asyncio
async def test_validate_suggestion_failure(temp_selectors_file):
    """Test failed validation."""
    repair = AISelectorRepair(str(temp_selectors_file))

    mock_page = AsyncMock()
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Not found"))

    result = await repair._validate_suggestion(mock_page, "input#invalid")

    assert result is False


def test_add_to_yaml_new_fallback(temp_selectors_file):
    """Test adding AI suggestion as fallback."""
    repair = AISelectorRepair(str(temp_selectors_file))

    repair._add_to_yaml("login.email_input", "input#ai-suggested")

    # Load and verify
    with open(temp_selectors_file, "r") as f:
        selectors = yaml.safe_load(f)

    email_input = selectors["login"]["email_input"]
    assert "input#ai-suggested" in email_input["fallbacks"]
    # Should be at the front
    assert email_input["fallbacks"][0] == "input#ai-suggested"


def test_add_to_yaml_convert_string_to_dict(temp_selectors_file):
    """Test converting string selector to dict structure."""
    # Add a simple string selector
    with open(temp_selectors_file, "r") as f:
        selectors = yaml.safe_load(f)

    selectors["login"]["simple_selector"] = "button#submit"

    with open(temp_selectors_file, "w") as f:
        yaml.dump(selectors, f)

    repair = AISelectorRepair(str(temp_selectors_file))
    repair._add_to_yaml("login.simple_selector", "button#ai-submit")

    # Load and verify
    with open(temp_selectors_file, "r") as f:
        selectors = yaml.safe_load(f)

    simple = selectors["login"]["simple_selector"]
    assert isinstance(simple, dict)
    assert simple["primary"] == "button#submit"
    assert "button#ai-submit" in simple["fallbacks"]


def test_add_to_yaml_create_new_entry(temp_selectors_file):
    """Test creating new selector entry."""
    repair = AISelectorRepair(str(temp_selectors_file))

    repair._add_to_yaml("login.new_field", "input#new")

    # Load and verify
    with open(temp_selectors_file, "r") as f:
        selectors = yaml.safe_load(f)

    assert "new_field" in selectors["login"]
    assert selectors["login"]["new_field"]["primary"] == "input#new"


def test_add_to_yaml_avoid_duplicates(temp_selectors_file):
    """Test that duplicates are not added."""
    repair = AISelectorRepair(str(temp_selectors_file))

    # Add same selector twice
    repair._add_to_yaml("login.email_input", "input#duplicate")
    repair._add_to_yaml("login.email_input", "input#duplicate")

    # Load and verify
    with open(temp_selectors_file, "r") as f:
        selectors = yaml.safe_load(f)

    fallbacks = selectors["login"]["email_input"]["fallbacks"]
    # Should only appear once
    assert fallbacks.count("input#duplicate") == 1


def test_add_to_yaml_file_not_found():
    """Test graceful handling when YAML file doesn't exist."""
    repair = AISelectorRepair("nonexistent.yaml")

    # Should not crash
    repair._add_to_yaml("login.email_input", "input#test")


@pytest.mark.asyncio
async def test_suggest_selector_strips_markdown(temp_selectors_file):
    """Test that markdown artifacts are stripped from AI response."""
    import sys

    mock_genai = MagicMock()

    with patch.dict(sys.modules, {"google.generativeai": mock_genai}):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            # Mock response with markdown
            mock_response = MagicMock()
            mock_response.text = "```css\ninput#email-field\n```"

            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model

            repair = AISelectorRepair(str(temp_selectors_file))

            mock_page = AsyncMock()
            mock_page.content.return_value = "<html></html>"
            mock_page.wait_for_selector = AsyncMock()

            result = await repair.suggest_selector(mock_page, "login.email_input", "Email Input")

            # Should have stripped markdown
            assert result == "input#email-field"


@pytest.mark.asyncio
async def test_suggest_selector_limits_html_size(temp_selectors_file):
    """Test that HTML content is limited to 50KB."""
    import sys

    mock_genai = MagicMock()

    with patch.dict(sys.modules, {"google.generativeai": mock_genai}):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            mock_response = MagicMock()
            mock_response.text = "input#test"

            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model

            repair = AISelectorRepair(str(temp_selectors_file))

            # Large HTML content
            large_html = "<html>" + "x" * 100000 + "</html>"

            mock_page = AsyncMock()
            mock_page.content.return_value = large_html
            mock_page.wait_for_selector = AsyncMock()

            await repair.suggest_selector(mock_page, "login.email_input", "Email")

            # Check that prompt was called with limited HTML
            call_args = mock_model.generate_content.call_args[0][0]
            # HTML should be truncated to 50KB
            assert len(call_args) < len(large_html)


@pytest.mark.asyncio
async def test_suggest_selector_exception_handling(temp_selectors_file):
    """Test exception handling in suggest_selector."""
    import sys

    mock_genai = MagicMock()

    with patch.dict(sys.modules, {"google.generativeai": mock_genai}):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            mock_model = MagicMock()
            mock_model.generate_content.side_effect = Exception("API Error")
            mock_genai.GenerativeModel.return_value = mock_model

            repair = AISelectorRepair(str(temp_selectors_file))

            mock_page = AsyncMock()
            mock_page.content.return_value = "<html></html>"

            # Should not crash, should return None
            result = await repair.suggest_selector(mock_page, "login.email_input", "Email Input")

            assert result is None
