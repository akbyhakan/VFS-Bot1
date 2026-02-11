"""IMAP listener for monitoring catch-all mailbox.

This module provides an IMAP listener that monitors a catch-all mailbox
for incoming OTP emails and routes them to appropriate sessions.
"""

import imaplib
import logging
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from email import message_from_bytes
from typing import Optional

from .email_processor import EmailProcessor
from .models import IMAPConfig
from .session_registry import SessionRegistry

logger = logging.getLogger(__name__)


class IMAPListener:
    """IMAP listener for catch-all mailbox monitoring."""

    def __init__(
        self,
        email: str,
        app_password: str,
        imap_config: IMAPConfig,
        email_processor: EmailProcessor,
        session_registry: SessionRegistry,
        poll_interval: int = 3,
        max_email_age_seconds: int = 300,
        max_processed_uids: int = 10000,
        noop_interval_seconds: int = 120,
    ):
        """
        Initialize IMAP listener.

        Args:
            email: Email address
            app_password: App password
            imap_config: IMAP configuration
            email_processor: Email processor instance
            session_registry: Session registry instance
            poll_interval: Poll interval in seconds
            max_email_age_seconds: Maximum age of emails to process
            max_processed_uids: Maximum size of processed UIDs set before cleanup
            noop_interval_seconds: Interval for IMAP NOOP keepalive commands
        """
        self._email = email
        self._app_password = app_password
        self._imap_config = imap_config
        self._email_processor = email_processor
        self._session_registry = session_registry
        self._poll_interval = poll_interval
        self._max_email_age = max_email_age_seconds
        self._max_processed_uids = max_processed_uids
        self._noop_interval = noop_interval_seconds

        self._running = False
        self._thread: Optional[threading.Thread] = None
        # Use both deque (for ordering) and set (for fast lookup)
        self._processed_uids_queue: deque = deque()
        self._processed_uids_set: set = set()
        self._lock = threading.Lock()

        # Health tracking
        self._last_noop_time = time.time()
        self._connection_healthy = False
        self._last_successful_poll: Optional[datetime] = None
        self._total_reconnects = 0
        self._consecutive_poll_errors = 0

    def start(self):
        """Start IMAP listener thread."""
        if self._running:
            logger.warning("IMAP listener already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("IMAP listener started")

    def stop(self):
        """Stop IMAP listener thread."""
        if not self._running:
            return

        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("IMAP listener stopped")

    def _connect_imap(self) -> imaplib.IMAP4_SSL:
        """Create and authenticate IMAP connection."""
        try:
            mail = imaplib.IMAP4_SSL(self._imap_config.host, self._imap_config.port)
            mail.login(self._email, self._app_password)
            mail.select(self._imap_config.folder)
            logger.debug(f"IMAP connection established to {self._imap_config.host}")
            return mail
        except Exception as e:
            logger.error(f"IMAP connection failed: {e}")
            raise

    def _listen_loop(self):
        """Main IMAP listening loop."""
        reconnect_delay = 5
        max_reconnect_delay = 60

        while self._running:
            mail = None
            try:
                mail = self._connect_imap()
                self._connection_healthy = True
                self._last_noop_time = time.time()
                reconnect_delay = 5  # Reset on successful connection

                # Main poll loop
                while self._running:
                    try:
                        # Send NOOP keepalive if interval elapsed
                        current_time = time.time()
                        if current_time - self._last_noop_time >= self._noop_interval:
                            try:
                                mail.noop()
                                self._last_noop_time = current_time
                                logger.debug("IMAP NOOP keepalive sent")
                            except Exception as e:
                                logger.warning(f"NOOP keepalive failed: {e}")
                                raise  # Trigger reconnection

                        self._poll_emails(mail)
                        self._last_successful_poll = datetime.now(timezone.utc)
                        self._consecutive_poll_errors = 0

                        # Cleanup processed UIDs after successful poll
                        self._cleanup_processed_uids()

                        time.sleep(self._poll_interval)
                    except (imaplib.IMAP4.abort, imaplib.IMAP4.error) as e:
                        # Protocol-level errors - reconnect immediately
                        logger.error(f"IMAP protocol error: {e}")
                        self._consecutive_poll_errors += 1
                        break  # Reconnect
                    except Exception as e:
                        self._consecutive_poll_errors += 1
                        logger.error(
                            f"Error polling emails (consecutive: {self._consecutive_poll_errors}): {e}"
                        )

                        # Break after 5 consecutive errors
                        if self._consecutive_poll_errors >= 5:
                            logger.critical("5 consecutive poll errors - stopping IMAP listener")
                            self._running = False
                            break
                        break  # Reconnect

            except Exception as e:
                logger.error(f"IMAP listener error: {e}")
                self._total_reconnects += 1

            finally:
                self._connection_healthy = False
                if mail:
                    try:
                        mail.close()
                        mail.logout()
                    except Exception as e:
                        logger.debug(f"Error closing IMAP connection: {e}")

            # Wait before reconnecting
            if self._running:
                logger.info(
                    f"Reconnecting in {reconnect_delay}s... (total reconnects: {self._total_reconnects})"
                )
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)

    def _poll_emails(self, mail: imaplib.IMAP4_SSL) -> None:
        """Poll for new emails."""
        # Search for recent unread emails
        since_time = datetime.now(timezone.utc) - timedelta(seconds=self._max_email_age)
        since_date = since_time.strftime("%d-%b-%Y")

        try:
            _, message_numbers = mail.search(None, f"(UNSEEN SINCE {since_date})")
        except Exception as e:
            logger.error(f"IMAP search failed: {e}")
            raise

        if not message_numbers[0]:
            return

        for num in message_numbers[0].split():
            try:
                # Check if already processed
                with self._lock:
                    if num in self._processed_uids_set:
                        continue
                    self._processed_uids_set.add(num)
                    self._processed_uids_queue.append(num)

                # Fetch and process email
                _, msg_data = mail.fetch(num, "(RFC822)")
                if msg_data and msg_data[0] and isinstance(msg_data[0], tuple):
                    email_body = msg_data[0][1]
                    msg = message_from_bytes(email_body)

                    # Process email
                    otp_entry = self._email_processor.process_email(msg)
                    if otp_entry:
                        # Find session and notify
                        session = self._session_registry.find_by_email(otp_entry.target_identifier)
                        if session:
                            self._session_registry.notify_otp(session.session_id, otp_entry.code)
                            logger.info(f"OTP delivered to session {session.session_id}")

            except Exception as e:
                logger.warning(f"Error processing email: {e}")
                with self._lock:
                    self._processed_uids_set.discard(num)
                    # Remove from queue if present (may not be at end)
                    try:
                        self._processed_uids_queue.remove(num)
                    except ValueError:
                        pass

    def _cleanup_processed_uids(self) -> None:
        """Clean up processed UIDs set to prevent unbounded memory growth."""
        with self._lock:
            current_size = len(self._processed_uids_set)
            if current_size > self._max_processed_uids:
                # Remove oldest UIDs from the front of the deque
                target_size = self._max_processed_uids // 2
                to_remove = current_size - target_size

                # Remove oldest UIDs (defensive check in case of edge cases)
                for _ in range(to_remove):
                    if self._processed_uids_queue:
                        oldest_uid = self._processed_uids_queue.popleft()
                        self._processed_uids_set.discard(oldest_uid)
                    else:
                        # Queue exhausted before target - should not happen
                        break

                logger.info(
                    f"Cleaned up processed UIDs: {current_size} -> {len(self._processed_uids_set)} "
                    f"(removed {to_remove} oldest UIDs)"
                )

    def get_health(self) -> dict:
        """
        Get IMAP listener health status.

        Returns:
            Dictionary with health metrics
        """
        with self._lock:
            return {
                "connected": self._connection_healthy,
                "last_successful_poll": (
                    self._last_successful_poll.isoformat() if self._last_successful_poll else None
                ),
                "total_reconnects": self._total_reconnects,
                "consecutive_poll_errors": self._consecutive_poll_errors,
                "processed_uids_count": len(self._processed_uids_set),
            }
