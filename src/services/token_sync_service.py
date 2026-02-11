"""Token synchronization service to bridge SessionManager and VFSApiClient."""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TokenSyncService:
    """
    Synchronizes token state between VFSApiClient and SessionManager.

    This service bridges the gap between two independent token management systems:
    - VFSApiClient.VFSSession: In-memory VFS Global API token
    - SessionManager: Persistent Dashboard/Anti-detection JWT

    Responsibilities:
    - Sync token state after VFSApiClient login or refresh
    - Provide proactive token refresh logic based on configurable buffer
    - Handle cases where anti-detection is disabled (SessionManager is None)
    """

    def __init__(
        self,
        session_manager: Optional[Any] = None,
        token_refresh_buffer_minutes: Optional[int] = None,
    ):
        """
        Initialize TokenSyncService.

        Args:
            session_manager: SessionManager instance (None if anti-detection disabled)
            token_refresh_buffer_minutes: Minutes before expiry to trigger proactive refresh
                                         (default: from TOKEN_REFRESH_BUFFER_MINUTES env var)
        """
        self.session_manager = session_manager

        # Get token refresh buffer from parameter or environment
        if token_refresh_buffer_minutes is None:
            token_refresh_buffer_minutes = int(os.getenv("TOKEN_REFRESH_BUFFER_MINUTES", "5"))
        self.token_refresh_buffer_minutes = token_refresh_buffer_minutes

        logger.info(
            f"TokenSyncService initialized with buffer: {self.token_refresh_buffer_minutes} minutes"
            f" (SessionManager: {'enabled' if session_manager else 'disabled'})"
        )

    def sync_from_vfs_session(self, vfs_session: Any) -> None:
        """
        Sync token state from VFSApiClient.VFSSession to SessionManager.

        This should be called after:
        - VFSApiClient.login() succeeds
        - VFSApiClient._refresh_token() succeeds

        Args:
            vfs_session: VFSSession object with access_token, refresh_token, expires_at
        """
        # Skip if anti-detection is disabled
        if self.session_manager is None:
            logger.debug("SessionManager disabled, skipping token sync")
            return

        if vfs_session is None:
            logger.warning("Cannot sync: VFSSession is None")
            return

        try:
            # Extract tokens from VFSSession
            access_token = vfs_session.access_token
            refresh_token = vfs_session.refresh_token

            if not access_token:
                logger.warning("Cannot sync: access_token is None")
                return

            # Sync to SessionManager
            self.session_manager.set_tokens(access_token, refresh_token)
            logger.info(f"Token synced to SessionManager (expires: {vfs_session.expires_at})")

        except Exception as e:
            logger.error(f"Failed to sync tokens to SessionManager: {e}", exc_info=True)

    def should_proactive_refresh(self, vfs_session: Any) -> bool:
        """
        Check if token should be proactively refreshed.

        Returns True if the token will expire within the configured buffer period.

        Args:
            vfs_session: VFSSession object with expires_at datetime

        Returns:
            True if token should be refreshed proactively, False otherwise
        """
        if vfs_session is None:
            logger.debug("VFSSession is None, no proactive refresh needed")
            return False

        try:
            # Check if token will expire within buffer period
            now = datetime.now(timezone.utc)
            expires_at = vfs_session.expires_at

            # Ensure expires_at is timezone-aware
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            # Calculate time until expiry
            time_until_expiry = expires_at - now
            time_until_expiry_seconds = time_until_expiry.total_seconds()
            buffer_seconds = self.token_refresh_buffer_minutes * 60

            should_refresh = time_until_expiry_seconds <= buffer_seconds

            if should_refresh:
                logger.info(
                    f"Token will expire in {time_until_expiry_seconds:.0f}s "
                    f"(buffer: {buffer_seconds}s) - proactive refresh recommended"
                )
            else:
                logger.debug(
                    f"Token valid for {time_until_expiry_seconds:.0f}s "
                    f"(buffer: {buffer_seconds}s)"
                )

            return should_refresh

        except Exception as e:
            logger.error(f"Error checking token expiry: {e}", exc_info=True)
            # Default to not refreshing on error
            return False

    async def ensure_fresh_token(self, vfs_api_client: Any) -> bool:
        """
        Ensure token is fresh by proactively refreshing if needed.

        This method checks if a refresh is needed and triggers it if so.
        After refresh, it syncs the new token to SessionManager.

        Args:
            vfs_api_client: VFSApiClient instance with session and _refresh_token method

        Returns:
            True if token is fresh (no refresh needed or refresh successful),
            False if refresh was needed but failed
        """
        if vfs_api_client is None:
            logger.warning("Cannot ensure fresh token: VFSApiClient is None")
            return False

        if not hasattr(vfs_api_client, "session"):
            logger.warning("Cannot ensure fresh token: VFSApiClient has no session")
            return False

        vfs_session = vfs_api_client.session

        # Check if proactive refresh is needed
        if not self.should_proactive_refresh(vfs_session):
            logger.debug("Token is fresh, no refresh needed")
            return True

        # Attempt proactive refresh
        logger.info("Initiating proactive token refresh...")
        try:
            # Use VFSApiClient's built-in refresh mechanism
            if not hasattr(vfs_api_client, "_refresh_token"):
                logger.error("VFSApiClient does not have _refresh_token method")
                return False

            await vfs_api_client._refresh_token()

            # Sync the refreshed token to SessionManager
            self.sync_from_vfs_session(vfs_api_client.session)

            logger.info("Proactive token refresh completed successfully")
            return True

        except Exception as e:
            logger.error(f"Proactive token refresh failed: {e}", exc_info=True)
            return False
