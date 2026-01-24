"""Tests for semantic locator support."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from src.utils.selectors import SelectorManager


@pytest.fixture
def temp_selectors_with_semantic(tmp_path):
    """Create a temporary selectors file with semantic locators."""
    selectors_content = {
        "version": "test-2.0",
        "login": {
            "email_input": {
                "primary": "input#email",
                "fallbacks": ["input[type='email']"],
                "semantic": {
                    "role": "textbox",
                    "label": "E-posta",
                    "label_en": "Email",
                    "placeholder": "example@email.com",
                },
            },
            "password_input": {
                "primary": "input#password",
                "fallbacks": ["input[type='password']"],
                "semantic": {
                    "role": "textbox",
                    "label": "Şifre",
                    "label_en": "Password",
                    "type": "password",
                },
            },
            "submit_button": {
                "primary": "button[type='submit']",
                "semantic": {"role": "button", "text": "Giriş Yap", "text_en": "Login"},
            },
        },
    }

    selectors_file = tmp_path / "selectors.yaml"
    with open(selectors_file, "w") as f:
        yaml.dump(selectors_content, f)

    return selectors_file


def test_get_semantic_exists(temp_selectors_with_semantic):
    """Test getting semantic locator info when it exists."""
    manager = SelectorManager(str(temp_selectors_with_semantic))

    semantic = manager._get_semantic("login.email_input")

    assert semantic is not None
    assert semantic["role"] == "textbox"
    assert semantic["label"] == "E-posta"
    assert semantic["label_en"] == "Email"
    assert semantic["placeholder"] == "example@email.com"


def test_get_semantic_not_exists(temp_selectors_with_semantic):
    """Test getting semantic locator for selector without it."""
    manager = SelectorManager(str(temp_selectors_with_semantic))

    # Add a selector without semantic
    manager._selectors["login"]["no_semantic"] = {"primary": "input#test", "fallbacks": []}

    semantic = manager._get_semantic("login.no_semantic")

    assert semantic is None


def test_get_semantic_nonexistent_path(temp_selectors_with_semantic):
    """Test getting semantic for non-existent path."""
    manager = SelectorManager(str(temp_selectors_with_semantic))

    semantic = manager._get_semantic("nonexistent.path")

    assert semantic is None


@pytest.mark.asyncio
async def test_try_semantic_locator_by_role(temp_selectors_with_semantic):
    """Test trying semantic locator with role."""
    manager = SelectorManager(str(temp_selectors_with_semantic))

    # Mock page and locator
    mock_locator = AsyncMock()
    mock_locator.wait_for = AsyncMock()

    mock_page = MagicMock()
    mock_page.get_by_role = MagicMock(return_value=mock_locator)

    semantic = {"role": "button", "text": "Login"}

    result = await manager._try_semantic_locator(mock_page, semantic)

    assert result is not None
    mock_page.get_by_role.assert_called_once_with("button", name="Login")
    mock_locator.wait_for.assert_called_once()


@pytest.mark.asyncio
async def test_try_semantic_locator_by_label(temp_selectors_with_semantic):
    """Test trying semantic locator with label."""
    manager = SelectorManager(str(temp_selectors_with_semantic))

    # Mock page - role fails, label succeeds
    mock_locator_fail = AsyncMock()
    mock_locator_fail.wait_for = AsyncMock(side_effect=Exception("Not found"))

    mock_locator_success = AsyncMock()
    mock_locator_success.wait_for = AsyncMock()

    mock_page = MagicMock()
    mock_page.get_by_role = MagicMock(return_value=mock_locator_fail)
    mock_page.get_by_label = MagicMock(return_value=mock_locator_success)

    semantic = {"role": "textbox", "label": "Email"}

    result = await manager._try_semantic_locator(mock_page, semantic)

    assert result is not None
    mock_page.get_by_label.assert_called()


@pytest.mark.asyncio
async def test_try_semantic_locator_by_text(temp_selectors_with_semantic):
    """Test trying semantic locator with text."""
    manager = SelectorManager(str(temp_selectors_with_semantic))

    # Mock - role and label fail, text succeeds
    mock_locator_fail = AsyncMock()
    mock_locator_fail.wait_for = AsyncMock(side_effect=Exception("Not found"))

    mock_locator_success = AsyncMock()
    mock_locator_success.wait_for = AsyncMock()

    mock_page = MagicMock()
    mock_page.get_by_role = MagicMock(return_value=mock_locator_fail)
    mock_page.get_by_text = MagicMock(return_value=mock_locator_success)

    semantic = {"text": "Login"}

    result = await manager._try_semantic_locator(mock_page, semantic)

    assert result is not None
    mock_page.get_by_text.assert_called_with("Login", exact=True)


@pytest.mark.asyncio
async def test_try_semantic_locator_by_placeholder(temp_selectors_with_semantic):
    """Test trying semantic locator with placeholder."""
    manager = SelectorManager(str(temp_selectors_with_semantic))

    # Mock - only placeholder succeeds
    mock_locator_success = AsyncMock()
    mock_locator_success.wait_for = AsyncMock()

    mock_page = MagicMock()
    mock_page.get_by_placeholder = MagicMock(return_value=mock_locator_success)

    semantic = {"placeholder": "example@email.com"}

    result = await manager._try_semantic_locator(mock_page, semantic)

    assert result is not None
    mock_page.get_by_placeholder.assert_called_with("example@email.com")


@pytest.mark.asyncio
async def test_try_semantic_locator_all_fail(temp_selectors_with_semantic):
    """Test trying semantic locator when all methods fail."""
    manager = SelectorManager(str(temp_selectors_with_semantic))

    # Mock - all fail
    mock_locator_fail = AsyncMock()
    mock_locator_fail.wait_for = AsyncMock(side_effect=Exception("Not found"))

    mock_page = MagicMock()
    mock_page.get_by_role = MagicMock(return_value=mock_locator_fail)
    mock_page.get_by_label = MagicMock(return_value=mock_locator_fail)
    mock_page.get_by_text = MagicMock(return_value=mock_locator_fail)

    semantic = {"role": "button", "label": "Submit", "text": "Submit"}

    result = await manager._try_semantic_locator(mock_page, semantic)

    assert result is None


@pytest.mark.asyncio
async def test_wait_for_selector_semantic_priority(temp_selectors_with_semantic):
    """Test that semantic locators are tried first."""
    manager = SelectorManager(str(temp_selectors_with_semantic))

    # Mock semantic locator succeeds
    mock_locator = AsyncMock()
    mock_locator.wait_for = AsyncMock()

    mock_page = MagicMock()
    mock_page.get_by_role = MagicMock(return_value=mock_locator)
    mock_page.wait_for_selector = AsyncMock()  # This should not be called

    result = await manager.wait_for_selector(mock_page, "login.submit_button")

    # Semantic locator should be used
    assert result is not None
    mock_page.get_by_role.assert_called()
    # CSS selector should not be tried
    mock_page.wait_for_selector.assert_not_called()


@pytest.mark.asyncio
async def test_wait_for_selector_fallback_to_css(temp_selectors_with_semantic):
    """Test fallback to CSS when semantic fails."""
    manager = SelectorManager(str(temp_selectors_with_semantic))

    # Mock semantic fails, CSS succeeds
    mock_locator_fail = AsyncMock()
    mock_locator_fail.wait_for = AsyncMock(side_effect=Exception("Not found"))

    mock_page = MagicMock()
    mock_page.get_by_role = MagicMock(return_value=mock_locator_fail)
    mock_page.get_by_label = MagicMock(return_value=mock_locator_fail)
    mock_page.wait_for_selector = AsyncMock()
    mock_page.locator = lambda x: f"locator({x})"

    result = await manager.wait_for_selector(mock_page, "login.email_input")

    # Should fallback to CSS selector
    assert result is not None
    mock_page.wait_for_selector.assert_called()


@pytest.mark.asyncio
async def test_semantic_locator_multi_language_support(temp_selectors_with_semantic):
    """Test multi-language support in semantic locators."""
    manager = SelectorManager(str(temp_selectors_with_semantic))

    semantic = manager._get_semantic("login.password_input")

    # Should have both Turkish and English labels
    assert "label" in semantic
    assert "label_en" in semantic
    assert semantic["label"] == "Şifre"
    assert semantic["label_en"] == "Password"


@pytest.mark.asyncio
async def test_semantic_locator_role_without_name(temp_selectors_with_semantic):
    """Test semantic locator with role but without name."""
    manager = SelectorManager(str(temp_selectors_with_semantic))

    mock_locator = AsyncMock()
    mock_locator.wait_for = AsyncMock()

    mock_page = MagicMock()
    mock_page.get_by_role = MagicMock(return_value=mock_locator)

    # Only role, no text/label
    semantic = {"role": "textbox"}

    result = await manager._try_semantic_locator(mock_page, semantic)

    assert result is not None
    # Should call get_by_role without name parameter
    mock_page.get_by_role.assert_called_with("textbox")


@pytest.mark.asyncio
async def test_semantic_locator_prefers_role_with_text(temp_selectors_with_semantic):
    """Test that role with text is preferred over label."""
    manager = SelectorManager(str(temp_selectors_with_semantic))

    mock_locator = AsyncMock()
    mock_locator.wait_for = AsyncMock()

    mock_page = MagicMock()
    mock_page.get_by_role = MagicMock(return_value=mock_locator)

    semantic = {"role": "button", "text": "Login", "label": "Submit"}

    result = await manager._try_semantic_locator(mock_page, semantic)

    assert result is not None
    # Should use text, not label, for role name
    mock_page.get_by_role.assert_called_with("button", name="Login")
