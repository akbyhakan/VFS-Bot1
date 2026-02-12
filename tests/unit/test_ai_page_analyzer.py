"""Tests for AIPageAnalyzer - AI-powered page analysis for unknown states."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.resilience.ai_page_analyzer import AIPageAnalyzer, PageAction, PageAnalysisResult


class TestPageAnalysisResult:
    """Tests for PageAnalysisResult Pydantic model."""

    def test_page_analysis_result_validation_success(self):
        """Test PageAnalysisResult model validates correct data."""
        result = PageAnalysisResult(
            page_purpose="SMS verification page",
            suggested_action=PageAction.FILL,
            target_selector="#sms-code",
            fill_value="123456",
            confidence=0.85,
            reasoning="Found SMS input field",
            suggested_indicators={
                "url_patterns": [".*sms.*"],
                "text_indicators": ["Enter code"],
                "css_selectors": ["#sms-code"],
            },
            suggested_state_name="sms_verification",
        )

        assert result.page_purpose == "SMS verification page"
        assert result.suggested_action == PageAction.FILL
        assert result.target_selector == "#sms-code"
        assert result.confidence == 0.85

    def test_page_analysis_result_confidence_bounds(self):
        """Test confidence must be between 0.0 and 1.0."""
        # Valid bounds
        PageAnalysisResult(
            page_purpose="Test",
            suggested_action=PageAction.CLICK,
            confidence=0.0,
            reasoning="test",
            suggested_indicators={},
            suggested_state_name="test",
        )
        PageAnalysisResult(
            page_purpose="Test",
            suggested_action=PageAction.CLICK,
            confidence=1.0,
            reasoning="test",
            suggested_indicators={},
            suggested_state_name="test",
        )

        # Invalid bounds
        with pytest.raises(ValueError):
            PageAnalysisResult(
                page_purpose="Test",
                suggested_action=PageAction.CLICK,
                confidence=-0.1,
                reasoning="test",
                suggested_indicators={},
                suggested_state_name="test",
            )

        with pytest.raises(ValueError):
            PageAnalysisResult(
                page_purpose="Test",
                suggested_action=PageAction.CLICK,
                confidence=1.1,
                reasoning="test",
                suggested_indicators={},
                suggested_state_name="test",
            )

    def test_page_action_enum_values(self):
        """Test PageAction enum has expected values."""
        assert PageAction.CLICK.value == "click"
        assert PageAction.WAIT.value == "wait"
        assert PageAction.FILL.value == "fill"
        assert PageAction.DISMISS.value == "dismiss"
        assert PageAction.NAVIGATE_BACK.value == "navigate_back"
        assert PageAction.REFRESH.value == "refresh"
        assert PageAction.ABORT.value == "abort"


class TestAIPageAnalyzerInitialization:
    """Tests for AIPageAnalyzer initialization."""

    @patch.dict("os.environ", {}, clear=True)
    def test_init_without_api_key(self):
        """Test initialization without GEMINI_API_KEY."""
        analyzer = AIPageAnalyzer()

        assert analyzer.enabled is False
        assert analyzer.client is None
        assert analyzer.model_name == "gemini-2.0-flash-exp"
        assert analyzer.temperature == 0.1
        assert analyzer.confidence_threshold == 0.7

    @patch.dict("os.environ", {"GEMINI_API_KEY": "test_key"})
    @patch("src.resilience.ai_page_analyzer.genai")
    def test_init_with_api_key(self, mock_genai):
        """Test initialization with GEMINI_API_KEY."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        analyzer = AIPageAnalyzer()

        assert analyzer.enabled is True
        assert analyzer.client == mock_client
        mock_genai.Client.assert_called_once_with(api_key="test_key")

    def test_custom_parameters(self):
        """Test initialization with custom parameters."""
        analyzer = AIPageAnalyzer(
            model_name="custom-model",
            temperature=0.5,
            confidence_threshold=0.8,
        )

        assert analyzer.model_name == "custom-model"
        assert analyzer.temperature == 0.5
        assert analyzer.confidence_threshold == 0.8


class TestHTMLSanitization:
    """Tests for HTML sanitization."""

    def test_sanitize_removes_scripts(self):
        """Test that script tags and contents are removed."""
        html = '<div>Test</div><script>alert("hack")</script><p>More</p>'
        result = AIPageAnalyzer._sanitize_html(html)

        assert "script" not in result.lower()
        assert "alert" not in result
        assert "Test" in result
        assert "More" in result

    def test_sanitize_removes_styles(self):
        """Test that style tags and contents are removed."""
        html = '<div>Test</div><style>.hack { color: red; }</style><p>More</p>'
        result = AIPageAnalyzer._sanitize_html(html)

        assert "style" not in result.lower()
        assert ".hack" not in result
        assert "Test" in result
        assert "More" in result

    def test_sanitize_removes_input_values(self):
        """Test that input values are removed."""
        html = '<input type="text" value="secret123">'
        result = AIPageAnalyzer._sanitize_html(html)

        assert "secret123" not in result
        assert "input" in result.lower()

    def test_sanitize_removes_hidden_tokens(self):
        """Test that hidden inputs with sensitive names are removed."""
        html = '<input type="hidden" name="csrf_token" value="abc123">'
        result = AIPageAnalyzer._sanitize_html(html)

        assert "csrf_token" not in result
        assert "abc123" not in result

    def test_sanitize_removes_data_attributes(self):
        """Test that data-* attributes are removed."""
        html = '<div data-user-id="12345" data-session="xyz">Content</div>'
        result = AIPageAnalyzer._sanitize_html(html)

        assert "data-user-id" not in result
        assert "data-session" not in result
        assert "Content" in result

    def test_sanitize_removes_event_handlers(self):
        """Test that inline event handlers are removed."""
        html = '<button onclick="doEvil()">Click</button>'
        result = AIPageAnalyzer._sanitize_html(html)

        assert "onclick" not in result.lower()
        assert "doEvil" not in result
        assert "Click" in result


class TestAnalyzePage:
    """Tests for analyze_page method."""

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test_key"})
    @patch("src.resilience.ai_page_analyzer.genai")
    async def test_analyze_page_returns_structured_result(self, mock_genai):
        """Test analyze_page returns PageAnalysisResult with structured data."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "page_purpose": "SMS verification",
                "suggested_action": "fill",
                "target_selector": "#sms-code",
                "fill_value": "",
                "confidence": 0.9,
                "reasoning": "Found SMS input field",
                "suggested_indicators": {
                    "url_patterns": [".*verify.*"],
                    "text_indicators": ["Enter code"],
                    "css_selectors": ["#sms-code"],
                },
                "suggested_state_name": "sms_verification",
            }
        )

        mock_client.models.generate_content = MagicMock(return_value=mock_response)
        mock_genai.Client.return_value = mock_client

        analyzer = AIPageAnalyzer()
        result = await analyzer.analyze_page(
            '<div>Enter verification code: <input id="sms-code"></div>',
            "https://example.com/verify",
        )

        assert result is not None
        assert isinstance(result, PageAnalysisResult)
        assert result.page_purpose == "SMS verification"
        assert result.suggested_action == PageAction.FILL
        assert result.target_selector == "#sms-code"
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test_key"})
    @patch("src.resilience.ai_page_analyzer.genai")
    async def test_analyze_page_filters_low_confidence(self, mock_genai):
        """Test analyze_page filters out low confidence results."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "page_purpose": "Unknown page",
                "suggested_action": "click",
                "target_selector": "#button",
                "fill_value": "",
                "confidence": 0.5,  # Below threshold (0.7)
                "reasoning": "Not sure",
                "suggested_indicators": {
                    "url_patterns": [],
                    "text_indicators": [],
                    "css_selectors": [],
                },
                "suggested_state_name": "unknown",
            }
        )

        mock_client.models.generate_content = MagicMock(return_value=mock_response)
        mock_genai.Client.return_value = mock_client

        analyzer = AIPageAnalyzer()
        result = await analyzer.analyze_page("<div>Test</div>", "https://example.com/test")

        assert result is None  # Filtered out due to low confidence

    @pytest.mark.asyncio
    async def test_analyze_page_without_client(self):
        """Test analyze_page returns None when client is not initialized."""
        analyzer = AIPageAnalyzer()
        analyzer.enabled = False
        analyzer.client = None

        result = await analyzer.analyze_page("<div>Test</div>", "https://example.com/test")

        assert result is None

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test_key"})
    @patch("src.resilience.ai_page_analyzer.genai")
    async def test_analyze_page_truncates_large_html(self, mock_genai):
        """Test analyze_page truncates large HTML content."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "page_purpose": "Test",
                "suggested_action": "wait",
                "target_selector": "",
                "fill_value": "",
                "confidence": 0.8,
                "reasoning": "Test",
                "suggested_indicators": {
                    "url_patterns": [],
                    "text_indicators": [],
                    "css_selectors": [],
                },
                "suggested_state_name": "test",
            }
        )

        mock_client.models.generate_content = MagicMock(return_value=mock_response)
        mock_genai.Client.return_value = mock_client

        analyzer = AIPageAnalyzer()
        large_html = "<div>" + ("x" * 100000) + "</div>"
        result = await analyzer.analyze_page(large_html, "https://example.com/test")

        assert result is not None
        # Check that generate_content was called with truncated HTML
        call_args = mock_client.models.generate_content.call_args
        assert len(call_args[1]["contents"]) < len(large_html)

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test_key"})
    @patch("src.resilience.ai_page_analyzer.genai")
    async def test_analyze_page_handles_exception(self, mock_genai):
        """Test analyze_page handles exceptions gracefully."""
        mock_client = MagicMock()
        mock_client.models.generate_content = MagicMock(
            side_effect=Exception("API error")
        )
        mock_genai.Client.return_value = mock_client

        analyzer = AIPageAnalyzer()
        result = await analyzer.analyze_page("<div>Test</div>", "https://example.com/test")

        assert result is None
