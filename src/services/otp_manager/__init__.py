"""Centralized OTP Manager for VFS automation.

This module provides a unified OTP management system that handles OTP codes
from both email (catch-all mailbox) and SMS sources for 100+ concurrent bot sessions.
"""

from .email_processor import EmailProcessor
from .imap_listener import IMAPListener
from .manager import OTPManager, get_otp_manager
from .models import BotSession, IMAPConfig, OTPEntry, OTPSource, SessionState
from .pattern_matcher import HTMLTextExtractor, OTPPatternMatcher
from .session_registry import SessionRegistry
from .sms_handler import SMSWebhookHandler

__all__ = [
    "OTPSource",
    "SessionState",
    "OTPEntry",
    "BotSession",
    "IMAPConfig",
    "HTMLTextExtractor",
    "OTPPatternMatcher",
    "SessionRegistry",
    "EmailProcessor",
    "IMAPListener",
    "SMSWebhookHandler",
    "OTPManager",
    "get_otp_manager",
]
