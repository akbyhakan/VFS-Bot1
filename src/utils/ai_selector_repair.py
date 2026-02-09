"""AI-powered selector auto-repair using Google Gemini."""

import logging
import os
import re
from pathlib import Path
from typing import Optional

import yaml
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class AISelectorRepair:
    """LLM-based selector recovery when all fallbacks fail."""

    def __init__(self, selectors_file: str = "config/selectors.yaml"):
        """
        Initialize AI selector repair.

        Args:
            selectors_file: Path to selectors YAML file
        """
        self.selectors_file = Path(selectors_file)
        self.enabled = False
        self.model = None

        # Try to initialize Gemini API
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            try:
                import google.generativeai as genai

                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel("gemini-pro")
                self.enabled = True
                logger.info("🤖 AI-powered selector auto-repair enabled")
            except ImportError:
                logger.warning(
                    "google-generativeai package not installed. "
                    "Install with: pip install google-generativeai"
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini API: {e}")
        else:
            logger.debug("GEMINI_API_KEY not set, AI repair disabled")

    @staticmethod
    def _sanitize_html_for_llm(html_content: str) -> str:
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
        # Remove script and style block contents
        # Use more robust regex to handle whitespace in closing tags
        html_content = re.sub(r'<script[^>]*>.*?</\s*script\s*>', '<script></script>', 
                             html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = re.sub(r'<style[^>]*>.*?</\s*style\s*>', '<style></style>', 
                             html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Replace input and textarea values
        html_content = re.sub(r'(<input[^>]*)\svalue\s*=\s*["\'][^"\']*["\']', 
                             r'\1 value="[redacted]"', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<textarea[^>]*>.*?</textarea>', 
                             '<textarea>[redacted]</textarea>', 
                             html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Replace meta content
        html_content = re.sub(r'(<meta[^>]*)\scontent\s*=\s*["\'][^"\']*["\']', 
                             r'\1 content="[redacted]"', html_content, flags=re.IGNORECASE)
        
        # Remove data-* attributes
        html_content = re.sub(r'\sdata-[a-zA-Z0-9_-]+\s*=\s*["\'][^"\']*["\']', 
                             '', html_content, flags=re.IGNORECASE)
        
        # Remove inline event handlers
        event_handlers = [
            'onclick', 'onload', 'onchange', 'onsubmit', 'onmouseover', 
            'onmouseout', 'onfocus', 'onblur', 'onerror', 'onkeyup', 'onkeydown'
        ]
        for handler in event_handlers:
            html_content = re.sub(rf'\s{handler}\s*=\s*["\'][^"\']*["\']', 
                                 '', html_content, flags=re.IGNORECASE)
        
        # Remove hidden inputs with sensitive names
        sensitive_patterns = ['token', 'csrf', 'session', 'nonce', 'secret', 'key']
        for pattern in sensitive_patterns:
            html_content = re.sub(
                rf'<input[^>]*type\s*=\s*["\']hidden["\'][^>]*name\s*=\s*["\'][^"\']*{pattern}[^"\']*["\'][^>]*>',
                '', html_content, flags=re.IGNORECASE | re.DOTALL
            )
            html_content = re.sub(
                rf'<input[^>]*name\s*=\s*["\'][^"\']*{pattern}[^"\']*["\'][^>]*type\s*=\s*["\']hidden["\'][^>]*>',
                '', html_content, flags=re.IGNORECASE | re.DOTALL
            )
        
        return html_content

    async def suggest_selector(
        self, page: Page, selector_path: str, element_description: str
    ) -> Optional[str]:
        """
        Ask LLM to suggest a new selector.

        Args:
            page: Playwright page object
            selector_path: Failed selector path
            element_description: Human-readable description of the element

        Returns:
            Suggested selector or None
        """
        if not self.enabled:
            logger.debug("AI repair not enabled")
            return None

        if not self.model:
            logger.warning("AI model not initialized")
            return None

        try:
            # Extract current page HTML (first 50KB to avoid token limits)
            html_content = await page.content()
            html_content = html_content[:50000]  # Limit to 50KB
            
            # Sanitize HTML to remove sensitive data before sending to LLM
            html_content = self._sanitize_html_for_llm(html_content)

            # Build prompt
            prompt = self._build_prompt(selector_path, element_description, html_content)

            # Query LLM
            logger.info(f"🤖 Asking AI for selector suggestion for: {selector_path}")
            response = self.model.generate_content(prompt)

            if response and response.text:
                suggested_selector = response.text.strip()
                # Remove common markdown artifacts and clean up
                suggested_selector = (
                    suggested_selector.replace("```css", "")
                    .replace("```", "")
                    .replace("`", "")
                    .strip()
                )
                # Remove any newlines and extra whitespace
                suggested_selector = " ".join(suggested_selector.split())

                logger.info(f"🤖 AI suggested selector: {suggested_selector}")

                # Validate the suggestion
                is_valid = await self._validate_suggestion(page, suggested_selector)

                if is_valid:
                    logger.info("✅ AI suggestion validated successfully!")
                    # Auto-update YAML file
                    self._add_to_yaml(selector_path, suggested_selector)
                    return str(suggested_selector)
                else:
                    logger.warning("❌ AI suggestion failed validation")
                    return None
            else:
                logger.warning("AI returned empty response")
                return None

        except Exception as e:
            logger.error(f"AI selector repair failed: {e}")
            return None

    def _build_prompt(self, selector_path: str, element_description: str, html_content: str) -> str:
        """
        Build prompt for LLM.

        Args:
            selector_path: Failed selector path
            element_description: Element description
            html_content: Page HTML

        Returns:
            Formatted prompt
        """
        prompt = f"""You are a web scraping expert. A CSS selector has failed on a website.

**Failed Selector Path:** {selector_path}
**Element Description:** {element_description}

**Current Page HTML (partial):**
```html
{html_content}
```

**Task:** Find the BEST CSS selector for this element. Return ONLY the selector, no explanation.

**Requirements:**
1. Selector must be unique and specific
2. Prefer ID > class > attribute selectors
3. Avoid nth-child if possible
4. Return format: Just the selector string (e.g., "input#email-field")

**Your response (selector only):**"""

        return prompt

    async def _validate_suggestion(self, page: Page, selector: str) -> bool:
        """
        Test if AI suggestion works on the page.

        Args:
            page: Playwright page object
            selector: Suggested selector

        Returns:
            True if selector is valid
        """
        try:
            await page.wait_for_selector(selector, timeout=5000, state="visible")
            return True
        except Exception as e:
            logger.debug(f"Validation failed for {selector}: {e}")
            return False

    def _add_to_yaml(self, selector_path: str, new_selector: str) -> None:
        """
        Auto-update YAML file with successful suggestion.

        Args:
            selector_path: Dot-separated selector path
            new_selector: New selector to add
        """
        try:
            # Load current YAML
            if not self.selectors_file.exists():
                logger.warning(f"Selectors file not found: {self.selectors_file}")
                return

            with open(self.selectors_file, "r", encoding="utf-8") as f:
                selectors = yaml.safe_load(f)

            # Navigate to the path and update
            keys = selector_path.split(".")
            current = selectors

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
                        logger.info(f"🤖 Added AI suggestion to fallbacks for: {selector_path}")
                else:
                    # Convert to dict structure
                    old_selector = current[final_key]
                    current[final_key] = {"primary": old_selector, "fallbacks": [new_selector]}
                    logger.info(
                        f"🤖 Converted to dict structure with AI suggestion: {selector_path}"
                    )
            else:
                # Create new entry
                current[final_key] = {"primary": new_selector, "fallbacks": []}
                logger.info(f"🤖 Created new selector entry: {selector_path}")

            # Save updated YAML
            with open(self.selectors_file, "w", encoding="utf-8") as f:
                yaml.dump(selectors, f, default_flow_style=False, allow_unicode=True)

            logger.info(f"✅ Updated {self.selectors_file} with AI suggestion")

        except Exception as e:
            logger.error(f"Failed to update YAML file: {e}")
