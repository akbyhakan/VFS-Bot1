"""AI-powered selector auto-repair using Google GenAI SDK with structured output."""

import os
import re
from pathlib import Path
from typing import Optional

import yaml
from loguru import logger
from pydantic import BaseModel, Field

from src.constants import Resilience


class RepairResult(BaseModel):
    """Structured result from AI repair operation."""

    is_found: bool = Field(description="Whether a valid selector was found")
    new_selector: str = Field(description="The suggested CSS selector")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    reason: str = Field(description="Explanation for the suggested selector")


class AIRepairV2:
    """LLM-based selector recovery with structured output using Pydantic."""

    def __init__(
        self,
        selectors_file: str = "config/selectors.yaml",
        model_name: str = "gemini-2.0-flash-exp",
        temperature: float = 0.1,
    ):
        """
        Initialize AI selector repair with structured output.

        Args:
            selectors_file: Path to selectors YAML file
            model_name: Gemini model name (default: gemini-2.0-flash-exp)
            temperature: Temperature for generation (default: 0.1 for deterministic output)
        """
        self.selectors_file = Path(selectors_file)
        self.model_name = model_name
        self.temperature = temperature
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
                    f"🤖 AI-powered selector auto-repair V2 enabled (model: {self.model_name})"
                )
            except ImportError:
                logger.warning(
                    "google-genai package not installed. "
                    "Install with: pip install google-genai"
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini API: {e}")
        else:
            logger.debug("GEMINI_API_KEY not set, AI repair disabled")

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
        result = []
        in_style = False
        i = 0
        while i < len(html_content):
            if html_content[i : i + 6].lower() == "<style":
                in_style = True
                while i < len(html_content) and html_content[i] != ">":
                    i += 1
                i += 1
                continue
            if in_style and html_content[i : i + 8].lower() == "</style>":
                in_style = False
                i += 8
                continue
            if not in_style:
                result.append(html_content[i])
            i += 1

        html_content = "".join(result)

        # Replace input and textarea values
        html_content = re.sub(
            r'(<input[^>]*)\svalue\s*=\s*["\'][^"\']*["\']',
            r'\1 value="[redacted]"',
            html_content,
            flags=re.IGNORECASE,
        )
        html_content = re.sub(
            r"<textarea[^>]*>.*?</textarea>",
            "<textarea>[redacted]</textarea>",
            html_content,
            flags=re.DOTALL | re.IGNORECASE,
        )

        # Replace meta content
        html_content = re.sub(
            r'(<meta[^>]*)\scontent\s*=\s*["\'][^"\']*["\']',
            r'\1 content="[redacted]"',
            html_content,
            flags=re.IGNORECASE,
        )

        # Remove data-* attributes
        html_content = re.sub(
            r'\sdata-[a-zA-Z0-9_-]+\s*=\s*["\'][^"\']*["\']',
            "",
            html_content,
            flags=re.IGNORECASE,
        )

        # Remove inline event handlers
        event_handlers = [
            "onclick",
            "onload",
            "onchange",
            "onsubmit",
            "onmouseover",
            "onmouseout",
            "onfocus",
            "onblur",
            "onerror",
            "onkeyup",
            "onkeydown",
        ]
        for handler in event_handlers:
            html_content = re.sub(
                rf'\s{handler}\s*=\s*["\'][^"\']*["\']',
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

    async def repair_selector(
        self, html_content: str, broken_selector: str, element_description: str
    ) -> Optional[RepairResult]:
        """
        Ask LLM to suggest a new selector with structured output.

        Args:
            html_content: HTML content of the page
            broken_selector: Failed selector
            element_description: Human-readable description of the element

        Returns:
            RepairResult with structured data or None if repair failed
        """
        if not self.enabled:
            logger.debug("AI repair not enabled")
            return None

        if not self.client:
            logger.warning("AI client not initialized")
            return None

        try:
            # Limit HTML size to avoid token limits
            if len(html_content) > Resilience.AI_REPAIR_MAX_HTML_SIZE:
                html_content = html_content[: Resilience.AI_REPAIR_MAX_HTML_SIZE]
                logger.debug(
                    f"HTML truncated to {Resilience.AI_REPAIR_MAX_HTML_SIZE} characters"
                )

            # Sanitize HTML to remove sensitive data
            html_content = self._sanitize_html(html_content)

            # Build prompt
            prompt = self._build_prompt(broken_selector, element_description, html_content)

            # Query LLM with structured output
            logger.info(f"🤖 Asking AI for selector suggestion: {broken_selector}")

            # Define schema for structured output
            response_schema = {
                "type": "object",
                "properties": {
                    "is_found": {"type": "boolean"},
                    "new_selector": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "reason": {"type": "string"},
                },
                "required": ["is_found", "new_selector", "confidence", "reason"],
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
                import json

                data = json.loads(response.text)
                result = RepairResult(**data)

                logger.info(
                    f"🤖 AI suggested: {result.new_selector} "
                    f"(confidence: {result.confidence:.2f}, found: {result.is_found})"
                )

                # Filter by confidence threshold
                if result.is_found and result.confidence >= Resilience.AI_REPAIR_CONFIDENCE_THRESHOLD:
                    logger.info(f"✅ AI suggestion meets confidence threshold: {result.reason}")
                    return result
                else:
                    logger.warning(
                        f"❌ AI suggestion rejected (confidence {result.confidence:.2f} "
                        f"< threshold {Resilience.AI_REPAIR_CONFIDENCE_THRESHOLD})"
                    )
                    return None
            else:
                logger.warning("AI returned empty response")
                return None

        except ImportError:
            logger.warning("google-genai not available, AI repair disabled")
            return None
        except Exception as e:
            logger.error(f"AI selector repair failed: {e}")
            return None

    def _build_prompt(
        self, broken_selector: str, element_description: str, html_content: str
    ) -> str:
        """
        Build prompt for LLM with structured output requirements.

        Args:
            broken_selector: Failed selector
            element_description: Element description
            html_content: Page HTML

        Returns:
            Formatted prompt
        """
        prompt = f"""You are a web scraping expert. A CSS selector has failed on a website.

**Failed Selector:** {broken_selector}
**Element Description:** {element_description}

**Current Page HTML (sanitized, partial):**
```html
{html_content}
```

**Task:** Find the BEST CSS selector for this element.

**Return JSON with:**
- is_found: true if you found a good selector, false otherwise
- new_selector: The CSS selector string (or empty if not found)
- confidence: Your confidence score from 0.0 to 1.0 (1.0 = very confident)
- reason: Brief explanation of your choice

**Requirements:**
1. Selector must be unique and specific
2. Prefer ID > class > attribute selectors
3. Avoid nth-child if possible
4. If element not found in HTML, set is_found=false and confidence=0.0

**Your response (JSON only):**"""

        return prompt

    def persist_to_yaml(self, selector_path: str, new_selector: str) -> bool:
        """
        Auto-update YAML file with successful AI suggestion.

        Args:
            selector_path: Dot-separated selector path
            new_selector: New selector to add

        Returns:
            True if update succeeded, False otherwise
        """
        try:
            # Load current YAML
            if not self.selectors_file.exists():
                logger.warning(f"Selectors file not found: {self.selectors_file}")
                return False

            with open(self.selectors_file, "r", encoding="utf-8") as f:
                selectors = yaml.safe_load(f)

            if not isinstance(selectors, dict):
                logger.warning("Selectors file is empty or invalid, cannot update")
                return False

            # Ensure defaults section exists
            if "defaults" not in selectors:
                selectors["defaults"] = {}

            # Navigate to the path and update
            keys = selector_path.split(".")
            current = selectors["defaults"]

            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]

            # Update the selector
            final_key = keys[-1]
            if final_key in current:
                if isinstance(current[final_key], dict):
                    # Add to fallbacks
                    if "fallbacks" not in current[final_key]:
                        current[final_key]["fallbacks"] = []

                    # Add AI suggestion as new fallback if not already present
                    if new_selector not in current[final_key]["fallbacks"]:
                        current[final_key]["fallbacks"].insert(0, new_selector)
                        logger.info(f"🤖 Added AI suggestion to fallbacks: {selector_path}")
                else:
                    # Convert to dict structure
                    old_selector = current[final_key]
                    current[final_key] = {"primary": old_selector, "fallbacks": [new_selector]}
                    logger.info(f"🤖 Converted to dict structure: {selector_path}")
            else:
                # Create new entry
                current[final_key] = {"primary": new_selector, "fallbacks": []}
                logger.info(f"🤖 Created new selector entry: {selector_path}")

            # Save updated YAML
            with open(self.selectors_file, "w", encoding="utf-8") as f:
                yaml.dump(selectors, f, default_flow_style=False, allow_unicode=True)

            logger.info(f"✅ Updated {self.selectors_file} with AI suggestion")
            return True

        except Exception as e:
            logger.error(f"Failed to update YAML file: {e}")
            return False
