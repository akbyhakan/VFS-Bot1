"""Pattern matching utilities for OTP extraction.

This module provides utilities for extracting OTP codes from text,
including HTML parsing and regex-based pattern matching.
"""

import re
from html.parser import HTMLParser
from typing import List, Optional, Pattern

from loguru import logger


class HTMLTextExtractor(HTMLParser):
    """Extract plain text from HTML content."""

    def __init__(self):
        super().__init__()
        self.text = []
        self.in_script = False
        self.in_style = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "script":
            self.in_script = True
        elif tag.lower() == "style":
            self.in_style = True

    def handle_endtag(self, tag):
        if tag.lower() == "script":
            self.in_script = False
        elif tag.lower() == "style":
            self.in_style = False

    def handle_data(self, data):
        if not self.in_script and not self.in_style:
            self.text.append(data)

    def get_text(self) -> str:
        return " ".join(self.text)


# Email OTP patterns (6-digit focused, used for email-based OTP)
EMAIL_OTP_PATTERNS: List[str] = [
    r"VFS\s+Global.*?(\d{6})",  # VFS Global specific
    r"doğrulama\s+kodu[:\s]+(\d{6})",  # Turkish: verification code
    r"doğrulama[:\s]+(\d{6})",  # Turkish: verification
    r"tek\s+kullanımlık\s+şifre[:\s]+(\d{6})",  # Turkish: one-time password
    r"OTP[:\s]+(\d{6})",  # OTP: 123456
    r"kod[:\s]+(\d{6})",  # Turkish: code
    r"code[:\s]+(\d{6})",  # code: 123456
    r"verification\s+code[:\s]+(\d{6})",  # verification code: 123456
    r"authentication\s+code[:\s]+(\d{6})",  # authentication code: 123456
    r"\b(\d{6})\b",  # 6-digit code (fallback)
]

# SMS OTP patterns (4-6 digit range, used for SMS-based OTP)
SMS_OTP_PATTERNS: List[str] = [
    # --- Keyword-based patterns (most specific, checked first) ---
    r"(?:verification|doğrulama)\s*(?:code|kodu?)?[:\s]+(\d{4,6})",
    r"(?:OTP|one.time)\s*(?:code|password)?[:\s]+(\d{4,6})",
    r"(?:passcode|pass\s*code)\s*(?:is)?[:\s]+(\d{4,6})",
    r"(?:code|kod|şifre)[:\s]+(\d{4,6})",
    r"VFS[^0-9]{0,20}(\d{4,6})",  # VFS-specific context
    # --- Bare digit fallbacks (least specific, checked last) ---
    r"\b(\d{6})\b",  # 6-digit code
    r"\b(\d{5})\b",  # 5-digit code
    # NOTE: 4-digit bare pattern removed — too many false positives
    # (years, PINs, prices). Use keyword patterns above for 4-digit OTPs.
]


class OTPPatternMatcher:
    """Regex-based OTP code extractor."""

    # Default patterns for backward compatibility
    DEFAULT_PATTERNS: List[str] = EMAIL_OTP_PATTERNS

    def __init__(self, custom_patterns: Optional[List[str]] = None):
        """
        Initialize OTP pattern matcher.

        Args:
            custom_patterns: Optional list of custom regex patterns
        """
        patterns = custom_patterns or self.DEFAULT_PATTERNS
        self._patterns: List[Pattern] = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in patterns]

    def extract_otp(self, text: str) -> Optional[str]:
        """
        Extract OTP code from text.

        Args:
            text: Text to search for OTP

        Returns:
            Extracted OTP code or None
        """
        if not text:
            return None

        for pattern in self._patterns:
            match = pattern.search(text)
            if match:
                otp = match.group(1)
                logger.debug("OTP code successfully extracted")
                return otp

        logger.warning(f"No OTP found in text: {text[:100]}...")
        return None
