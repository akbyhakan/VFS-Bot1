"""Tests for AI-powered selector auto-repair."""

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
import yaml

from src.selector import AISelectorRepair


class TestHTMLSanitization:
    """Tests for HTML sanitization before sending to LLM."""

    def test_sanitize_removes_script_contents(self):
        """Test that script tags and contents are removed."""
        html = '<script>alert("secret data")</script><div>content</div>'
        sanitized = AISelectorRepair._sanitize_html_for_llm(html)

        assert "secret data" not in sanitized
        assert "<script>" not in sanitized  # Entire tag removed
        assert "<div>content</div>" in sanitized

    def test_sanitize_removes_style_contents(self):
        """Test that style tags and contents are removed."""
        html = "<style>.secret { color: red; }</style><div>content</div>"
        sanitized = AISelectorRepair._sanitize_html_for_llm(html)

        assert ".secret" not in sanitized
        assert "<style>" not in sanitized  # Entire tag removed

    def test_sanitize_redacts_input_values(self):
        """Test that input values are redacted."""
        html = '<input type="text" value="sensitive_data" name="user">'
        sanitized = AISelectorRepair._sanitize_html_for_llm(html)

        assert "sensitive_data" not in sanitized
        assert "[redacted]" in sanitized

    def test_sanitize_redacts_textarea_contents(self):
        """Test that textarea contents are redacted."""
        html = "<textarea>sensitive text data</textarea>"
        sanitized = AISelectorRepair._sanitize_html_for_llm(html)

        assert "sensitive text data" not in sanitized
        assert "[redacted]" in sanitized

    def test_sanitize_redacts_meta_content(self):
        """Test that meta tag content is redacted."""
        html = '<meta name="csrf-token" content="secret_csrf_token">'
        sanitized = AISelectorRepair._sanitize_html_for_llm(html)

        assert "secret_csrf_token" not in sanitized
        assert "[redacted]" in sanitized

    def test_sanitize_removes_data_attributes(self):
        """Test that data-* attributes are removed."""
        html = '<div data-user-id="12345" data-session="xyz">content</div>'
        sanitized = AISelectorRepair._sanitize_html_for_llm(html)

        assert "data-user-id" not in sanitized
        assert "data-session" not in sanitized
        assert "12345" not in sanitized
        assert "xyz" not in sanitized

    def test_sanitize_removes_event_handlers(self):
        """Test that inline event handlers are removed."""
        html = '<button onclick="alert(\'test\')" onload="init()">Click</button>'
        sanitized = AISelectorRepair._sanitize_html_for_llm(html)

        assert "onclick" not in sanitized
        assert "onload" not in sanitized
        assert "alert" not in sanitized

    def test_sanitize_removes_hidden_inputs_with_token(self):
        """Test that hidden inputs with sensitive names are removed."""
        html = """
            <input type="hidden" name="csrf_token" value="secret">
            <input type="hidden" name="session_id" value="xyz">
            <input type="hidden" name="user_nonce" value="abc">
            <input type="text" name="username">
        """
        sanitized = AISelectorRepair._sanitize_html_for_llm(html)

        assert 'name="csrf_token"' not in sanitized
        assert 'name="session_id"' not in sanitized
        assert 'name="user_nonce"' not in sanitized
        assert 'name="username"' in sanitized  # Regular input should remain

    def test_sanitize_complex_html(self):
        """Test sanitization of complex HTML with multiple sensitive elements."""
        html = """
            <html>
            <head>
                <script>var secret = "token123";</script>
                <style>.hidden { display: none; }</style>
                <meta name="csrf" content="csrf_token_value">
            </head>
            <body>
                <form>
                    <input type="text" name="username" value="john_doe">
                    <input type="password" name="password" value="secret_password">
                    <input type="hidden" name="csrf_token" value="hidden_csrf">
                    <textarea>User comment here</textarea>
                    <button onclick="submit()">Submit</button>
                </form>
                <div data-user-id="12345" data-analytics="track">Content</div>
            </body>
            </html>
        """
        sanitized = AISelectorRepair._sanitize_html_for_llm(html)

        # Verify sensitive data is removed
        assert "secret = " not in sanitized or "token123" not in sanitized
        assert ".hidden" not in sanitized
        assert "csrf_token_value" not in sanitized
        assert "john_doe" not in sanitized
        assert "secret_password" not in sanitized
        assert "hidden_csrf" not in sanitized
        assert "User comment here" not in sanitized
        assert "data-user-id" not in sanitized
        assert "data-analytics" not in sanitized
        assert "onclick" not in sanitized

        # Verify structure remains
        assert "<form>" in sanitized
        assert 'name="username"' in sanitized
        assert 'name="password"' in sanitized
        assert "<button>" in sanitized


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
        assert repair.client is None


def test_ai_repair_init_with_api_key(temp_selectors_file):
    """Test initialization with API key."""
    # Mock the entire google.genai module before import
    import sys

    mock_genai = MagicMock()

    with patch.dict(sys.modules, {"google.genai": mock_genai, "google": MagicMock(genai=mock_genai)}):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            repair = AISelectorRepair(str(temp_selectors_file))

            assert repair.enabled is True
            assert repair.client is not None
            mock_genai.Client.assert_called_with(api_key="test-key")


def test_ai_repair_init_import_error(temp_selectors_file):
    """Test graceful handling when google-genai is not installed."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
        # Simulate ImportError by removing from sys.modules and making import fail
        import sys

        original_import = __builtins__["__import__"]

        def mock_import(name, *args, **kwargs):
            if "google.genai" in name or (name == "google" and "genai" in str(args)):
                raise ImportError("No module named 'google.genai'")
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

    with patch.dict(sys.modules, {"google.genai": mock_genai, "google": MagicMock(genai=mock_genai)}):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            # Mock client and response
            mock_response = MagicMock()
            mock_response.text = "input#new-email-field"

            mock_models = MagicMock()
            mock_models.generate_content.return_value = mock_response

            mock_client = MagicMock()
            mock_client.models = mock_models
            mock_genai.Client.return_value = mock_client

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

    with patch.dict(sys.modules, {"google.genai": mock_genai, "google": MagicMock(genai=mock_genai)}):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            # Mock client and response
            mock_response = MagicMock()
            mock_response.text = "input#invalid-selector"

            mock_models = MagicMock()
            mock_models.generate_content.return_value = mock_response

            mock_client = MagicMock()
            mock_client.models = mock_models
            mock_genai.Client.return_value = mock_client

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

    with patch.dict(sys.modules, {"google.genai": mock_genai, "google": MagicMock(genai=mock_genai)}):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            # Mock empty response
            mock_response = MagicMock()
            mock_response.text = ""

            mock_models = MagicMock()
            mock_models.generate_content.return_value = mock_response

            mock_client = MagicMock()
            mock_client.models = mock_models
            mock_genai.Client.return_value = mock_client

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

    with patch.dict(sys.modules, {"google.genai": mock_genai, "google": MagicMock(genai=mock_genai)}):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            # Mock response with markdown
            mock_response = MagicMock()
            mock_response.text = "```css\ninput#email-field\n```"

            mock_models = MagicMock()
            mock_models.generate_content.return_value = mock_response

            mock_client = MagicMock()
            mock_client.models = mock_models
            mock_genai.Client.return_value = mock_client

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

    with patch.dict(sys.modules, {"google.genai": mock_genai, "google": MagicMock(genai=mock_genai)}):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            mock_response = MagicMock()
            mock_response.text = "input#test"

            mock_models = MagicMock()
            mock_models.generate_content.return_value = mock_response

            mock_client = MagicMock()
            mock_client.models = mock_models
            mock_genai.Client.return_value = mock_client

            repair = AISelectorRepair(str(temp_selectors_file))

            # Large HTML content
            large_html = "<html>" + "x" * 100000 + "</html>"

            mock_page = AsyncMock()
            mock_page.content.return_value = large_html
            mock_page.wait_for_selector = AsyncMock()

            await repair.suggest_selector(mock_page, "login.email_input", "Email")

            # Check that prompt was called with limited HTML
            call_args = mock_models.generate_content.call_args[1]["contents"]
            # HTML should be truncated to 50KB
            assert len(call_args) < len(large_html)


@pytest.mark.asyncio
async def test_suggest_selector_exception_handling(temp_selectors_file):
    """Test exception handling in suggest_selector."""
    import sys

    mock_genai = MagicMock()

    with patch.dict(sys.modules, {"google.genai": mock_genai, "google": MagicMock(genai=mock_genai)}):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            mock_models = MagicMock()
            mock_models.generate_content.side_effect = Exception("API Error")

            mock_client = MagicMock()
            mock_client.models = mock_models
            mock_genai.Client.return_value = mock_client

            repair = AISelectorRepair(str(temp_selectors_file))

            mock_page = AsyncMock()
            mock_page.content.return_value = "<html></html>"

            # Should not crash, should return None
            result = await repair.suggest_selector(mock_page, "login.email_input", "Email Input")

            assert result is None


# YAML edge case tests for _add_to_yaml
class TestYAMLEdgeCasesInAddToYAML:
    """Tests for YAML safe_load type checking in _add_to_yaml method."""

    @pytest.fixture
    def temp_selectors_file(self, tmp_path):
        """Create a temporary selectors file."""
        selectors_file = tmp_path / "selectors.yaml"
        with open(selectors_file, "w") as f:
            yaml.dump({"version": "1.0", "login": {"email_input": "input#email"}}, f)
        return selectors_file

    def test_add_to_yaml_with_empty_file(self, tmp_path, caplog):
        """Test that _add_to_yaml handles empty YAML file gracefully."""
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")

        repair = AISelectorRepair(str(empty_file))

        # Should not crash, should log warning and return early
        repair._add_to_yaml("login.email_input", "input#new-email")

        # File should remain empty (or unchanged)
        content = empty_file.read_text()
        assert content == ""  # Should not be modified

        # Verify warning was logged
        assert "Selectors file is empty or invalid" in caplog.text

    def test_add_to_yaml_with_none_content(self, tmp_path, caplog):
        """Test that _add_to_yaml handles YAML file that returns None."""
        none_file = tmp_path / "none.yaml"
        none_file.write_text("~\n")

        repair = AISelectorRepair(str(none_file))

        # Should not crash, should log warning and return early
        repair._add_to_yaml("login.email_input", "input#new-email")

        # File should remain unchanged (contains None)
        with open(none_file, "r") as f:
            loaded = yaml.safe_load(f)
        assert loaded is None

        # Verify warning was logged
        assert "Selectors file is empty or invalid" in caplog.text

    def test_add_to_yaml_with_list_content(self, tmp_path, caplog):
        """Test that _add_to_yaml handles YAML file that returns a list."""
        list_file = tmp_path / "list.yaml"
        list_file.write_text("- item1\n- item2\n")

        repair = AISelectorRepair(str(list_file))

        # Should not crash, should log warning and return early
        repair._add_to_yaml("login.email_input", "input#new-email")

        # File should remain unchanged (still a list)
        with open(list_file, "r") as f:
            loaded = yaml.safe_load(f)
        assert isinstance(loaded, list)

        # Verify warning was logged
        assert "Selectors file is empty or invalid" in caplog.text

    def test_add_to_yaml_with_string_content(self, tmp_path, caplog):
        """Test that _add_to_yaml handles YAML file that returns a string."""
        string_file = tmp_path / "string.yaml"
        string_file.write_text("just a string\n")

        repair = AISelectorRepair(str(string_file))

        # Should not crash, should log warning and return early
        repair._add_to_yaml("login.email_input", "input#new-email")

        # File should remain unchanged (still a string)
        with open(string_file, "r") as f:
            loaded = yaml.safe_load(f)
        assert isinstance(loaded, str)

        # Verify warning was logged
        assert "Selectors file is empty or invalid" in caplog.text

    def test_add_to_yaml_with_valid_dict(self, temp_selectors_file):
        """Test that _add_to_yaml works correctly with valid dict YAML."""
        repair = AISelectorRepair(str(temp_selectors_file))

        # Should successfully add to valid YAML
        repair._add_to_yaml("login.password_input", "input#new-password")

        # File should be updated
        with open(temp_selectors_file, "r") as f:
            loaded = yaml.safe_load(f)

        assert isinstance(loaded, dict)
        assert "login" in loaded
        # The new selector should be added
        assert "password_input" in loaded["login"]
