"""AI-powered page analysis for unknown page states using Google GenAI SDK."""

import json
import os
from enum import Enum
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field

from src.constants import Resilience


class PageAction(str, Enum):
    """Actions the bot can take on an unknown page."""

    CLICK = "click"  # Click a button/link
    WAIT = "wait"  # Wait for page to change
    FILL = "fill"  # Fill a form field
    DISMISS = "dismiss"  # Close a modal/popup
    NAVIGATE_BACK = "navigate_back"  # Go back in browser history
    REFRESH = "refresh"  # Refresh the page
    ABORT = "abort"  # Cannot determine action


class PageAnalysisResult(BaseModel):
    """Structured result from AI page analysis."""

    page_purpose: str = Field(description="What this page is about")
    suggested_action: PageAction = Field(description="Recommended action to take")
    target_selector: str = Field(
        default="", description="CSS selector for target element (if applicable)"
    )
    fill_value: str = Field(
        default="", description="Value to fill (if action is FILL)"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score (0.0-1.0)"
    )
    reasoning: str = Field(description="Why this action was chosen")
    suggested_indicators: dict = Field(
        default_factory=dict,
        description="URL patterns, text indicators, CSS selectors for future detection",
    )
    suggested_state_name: str = Field(
        description="Suggested name for this state (e.g., 'sms_verification')"
    )


class AIPageAnalyzer:
    """AI-powered page analyzer using Gemini for unknown page states."""

    def __init__(
        self,
        model_name: str = "gemini-2.0-flash-exp",
        temperature: float = 0.1,
        confidence_threshold: float = 0.7,
    ):
        """
        Initialize AI page analyzer.

        Args:
            model_name: Gemini model name (default: gemini-2.0-flash-exp)
            temperature: Temperature for generation (default: 0.1 for deterministic output)
            confidence_threshold: Minimum confidence to act on suggestion (default: 0.7)
        """
        self.model_name = model_name
        self.temperature = temperature
        self.confidence_threshold = confidence_threshold
        self.enabled = False
        self.client = None

        # Try to initialize Gemini API
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            try:
                from google import genai

                self.client = genai.Client(api_key=api_key)
                self.enabled = True
                logger.info(
                    f"🧠 AI page analyzer enabled (model: {self.model_name}, "
                    f"confidence threshold: {self.confidence_threshold})"
                )
            except ImportError:
                logger.warning(
                    "google-genai package not installed. "
                    "Install with: pip install google-genai"
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini API: {e}")
        else:
            logger.debug("GEMINI_API_KEY not set, AI page analyzer disabled")

    @staticmethod
    def _sanitize_html(html_content: str) -> str:
        """
        Sanitize HTML before sending to external LLM to prevent data leakage.

        Removes sensitive data:
        - Script and style contents
        - Input/textarea values
        - Meta tag content
        - Data attributes
        - Inline event handlers
        - Hidden inputs with sensitive names

        Args:
            html_content: Raw HTML content

        Returns:
            Sanitized HTML safe for LLM processing
        """
        import re

        # Remove script tags and their contents using simple state machine
        result = []
        in_script = False
        i = 0
        while i < len(html_content):
            if html_content[i : i + 7].lower() == "<script":
                in_script = True
                while i < len(html_content) and html_content[i] != ">":
                    i += 1
                i += 1
                continue
            if in_script and html_content[i : i + 9].lower() == "</script>":
                in_script = False
                i += 9
                continue
            if not in_script:
                result.append(html_content[i])
            i += 1

        html_content = "".join(result)

        # Remove style tags and their contents
        html_content = re.sub(
            r"<style[^>]*>.*?</style>", "", html_content, flags=re.IGNORECASE | re.DOTALL
        )

        # Remove input/textarea values
        html_content = re.sub(
            r'(<input[^>]*)\s+value\s*=\s*["\'][^"\']*["\']',
            r"\1",
            html_content,
            flags=re.IGNORECASE,
        )
        html_content = re.sub(
            r"(<textarea[^>]*>).*?(</textarea>)",
            r"\1\2",
            html_content,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # Remove meta tag content
        html_content = re.sub(
            r'(<meta[^>]*)\s+content\s*=\s*["\'][^"\']*["\']',
            r"\1",
            html_content,
            flags=re.IGNORECASE,
        )

        # Remove data-* attributes
        html_content = re.sub(
            r'\s+data-[a-zA-Z0-9-]+\s*=\s*["\'][^"\']*["\']',
            "",
            html_content,
            flags=re.IGNORECASE,
        )

        # Remove inline event handlers
        event_handlers = [
            "onclick",
            "onload",
            "onerror",
            "onsubmit",
            "onchange",
            "onfocus",
            "onblur",
        ]
        for handler in event_handlers:
            html_content = re.sub(
                rf'\s+{handler}\s*=\s*["\'][^"\']*["\']',
                "",
                html_content,
                flags=re.IGNORECASE,
            )

        # Remove hidden inputs with sensitive names
        sensitive_patterns = ["token", "csrf", "session", "nonce", "secret", "key"]
        for pattern in sensitive_patterns:
            html_content = re.sub(
                rf'<input[^>]*type\s*=\s*["\']hidden["\'][^>]*name\s*=\s*["\'][^"\']*{pattern}[^"\']*["\'][^>]*>',
                "",
                html_content,
                flags=re.IGNORECASE | re.DOTALL,
            )
            html_content = re.sub(
                rf'<input[^>]*name\s*=\s*["\'][^"\']*{pattern}[^"\']*["\'][^>]*type\s*=\s*["\']hidden["\'][^>]*>',
                "",
                html_content,
                flags=re.IGNORECASE | re.DOTALL,
            )

        return html_content

    def _build_prompt(
        self, html_content: str, url: str, screenshot_available: bool
    ) -> str:
        """
        Build the prompt for AI page analysis.

        Args:
            html_content: Sanitized HTML content
            url: Current page URL
            screenshot_available: Whether a screenshot is available

        Returns:
            Formatted prompt for the AI
        """
        prompt = f"""You are analyzing a page from a VFS Global visa appointment booking system that the bot doesn't recognize.

**Current URL:** {url}

**HTML Content:**
```html
{html_content}
```

**Your Task:**
Analyze this page and determine:
1. What is the purpose/type of this page?
2. What action should the bot take to proceed with the booking flow?
3. What is the CSS selector for the target element (if applicable)?
4. How confident are you in this recommendation (0.0-1.0)?
5. What indicators can identify this page in the future (URL patterns, text, CSS selectors)?
6. What should this page state be called (e.g., "sms_verification", "additional_info_required")?

**Available Actions:**
- CLICK: Click a button or link (provide CSS selector)
- WAIT: Wait for the page to change automatically
- FILL: Fill a form field (provide CSS selector and value placeholder)
- DISMISS: Close a modal or popup (provide CSS selector)
- NAVIGATE_BACK: Go back in browser history
- REFRESH: Refresh the page
- ABORT: Cannot determine a safe action

**Important Guidelines:**
- Only suggest CLICK if you can identify a clear "Continue", "Next", "Submit", or "OK" button
- Only suggest FILL if you can identify what data is needed and where
- Suggest DISMISS for modals/popups that need to be closed
- Suggest WAIT if the page appears to be loading or processing
- Suggest NAVIGATE_BACK if this is clearly an error or dead-end page
- Suggest ABORT if the page is ambiguous or requires human judgment
- Provide high confidence (>0.8) only for clear, obvious actions
- Provide medium confidence (0.6-0.8) for probable actions
- Provide low confidence (<0.6) for uncertain situations

**Response Format:**
Return a JSON object with:
- page_purpose: Brief description of what this page is
- suggested_action: One of the action types listed above
- target_selector: CSS selector for the target element (empty string if not applicable)
- fill_value: Placeholder for value to fill (empty string if not applicable)
- confidence: Your confidence score (0.0-1.0)
- reasoning: Brief explanation of why you chose this action
- suggested_indicators: Object with:
  - url_patterns: List of URL patterns that identify this page
  - text_indicators: List of text phrases that appear on this page
  - css_selectors: List of CSS selectors that uniquely identify this page
- suggested_state_name: Snake_case name for this page state
"""

        if screenshot_available:
            prompt += "\n**Note:** A screenshot of the page is available for visual analysis."

        return prompt

    async def analyze_page(
        self,
        html_content: str,
        url: str,
        screenshot_path: Optional[str] = None,
    ) -> Optional[PageAnalysisResult]:
        """
        Analyze an unknown page and suggest an action.

        Args:
            html_content: HTML content of the page
            url: Current page URL
            screenshot_path: Optional path to screenshot (for future enhancement)

        Returns:
            PageAnalysisResult with AI's analysis or None if analysis failed
        """
        if not self.enabled:
            logger.debug("AI page analyzer not enabled")
            return None

        if not self.client:
            logger.warning("AI client not initialized")
            return None

        try:
            # Limit HTML size to avoid token limits
            max_html_size = Resilience.AI_PAGE_ANALYZER_MAX_HTML_SIZE
            if len(html_content) > max_html_size:
                html_content = html_content[:max_html_size]
                logger.debug(f"HTML truncated to {max_html_size} characters")

            # Sanitize HTML to remove sensitive data
            html_content = self._sanitize_html(html_content)

            # Build prompt
            prompt = self._build_prompt(html_content, url, screenshot_path is not None)

            # Query LLM with structured output
            logger.info(f"🧠 Asking AI to analyze unknown page: {url[:100]}")

            # Define schema for structured output
            response_schema = {
                "type": "object",
                "properties": {
                    "page_purpose": {"type": "string"},
                    "suggested_action": {
                        "type": "string",
                        "enum": [
                            "click",
                            "wait",
                            "fill",
                            "dismiss",
                            "navigate_back",
                            "refresh",
                            "abort",
                        ],
                    },
                    "target_selector": {"type": "string"},
                    "fill_value": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "reasoning": {"type": "string"},
                    "suggested_indicators": {
                        "type": "object",
                        "properties": {
                            "url_patterns": {"type": "array", "items": {"type": "string"}},
                            "text_indicators": {"type": "array", "items": {"type": "string"}},
                            "css_selectors": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["url_patterns", "text_indicators", "css_selectors"],
                    },
                    "suggested_state_name": {"type": "string"},
                },
                "required": [
                    "page_purpose",
                    "suggested_action",
                    "target_selector",
                    "fill_value",
                    "confidence",
                    "reasoning",
                    "suggested_indicators",
                    "suggested_state_name",
                ],
            }

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={
                    "temperature": self.temperature,
                    "response_mime_type": "application/json",
                    "response_schema": response_schema,
                },
            )

            if response and response.text:
                # Parse JSON response into Pydantic model
                data = json.loads(response.text)
                result = PageAnalysisResult(**data)

                logger.info(
                    f"🧠 AI analysis: {result.page_purpose} "
                    f"→ {result.suggested_action.value} "
                    f"(confidence: {result.confidence:.2f})"
                )

                # Filter by confidence threshold
                if result.confidence >= self.confidence_threshold:
                    logger.info(
                        f"✅ AI analysis meets confidence threshold: {result.reasoning}"
                    )
                    return result
                else:
                    logger.warning(
                        f"❌ AI analysis rejected (confidence {result.confidence:.2f} "
                        f"< threshold {self.confidence_threshold})"
                    )
                    return None
            else:
                logger.warning("AI returned empty response")
                return None

        except Exception as e:
            logger.error(f"AI page analysis failed: {e}")
            return None
