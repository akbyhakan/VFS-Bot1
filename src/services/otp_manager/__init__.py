"""Centralized OTP Manager for VFS automation.

This module provides a unified OTP management system that handles OTP codes
from both email (catch-all mailbox) and SMS sources for 100+ concurrent bot sessions.
"""

from .email_otp_handler import EmailOTPHandler, get_email_otp_handler
from .email_processor import EmailProcessor
from .imap_listener import IMAPListener
from .manager import OTPManager, get_otp_manager
from .models import BotSession, IMAPConfig, OTPEntry, OTPSource, SessionState
from .otp_webhook import OTPWebhookService, get_otp_service
from .otp_webhook_routes import router as otp_router
from .pattern_matcher import HTMLTextExtractor, OTPPatternMatcher
from .session_registry import SessionRegistry
from .sms_handler import SMSWebhookHandler
from .webhook_token_manager import (
    SMSPayloadParser,
    WebhookToken,
    WebhookTokenManager,
)

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
    "EmailOTPHandler",
    "get_email_otp_handler",
    "OTPWebhookService",
    "get_otp_service",
    "otp_router",
    "SMSPayloadParser",
    "WebhookToken",
    "WebhookTokenManager",
]
