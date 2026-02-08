"""WebSocket connection manager with rate limiting."""

import asyncio
import logging
import os
import time
from typing import Dict, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Thread-safe WebSocket connection manager with connection limits and rate limiting."""

    MAX_CONNECTIONS = int(os.getenv("MAX_WEBSOCKET_CONNECTIONS", "1000"))
    MESSAGES_PER_SECOND = 10  # Token bucket rate
    BURST_SIZE = 20  # Maximum burst capacity

    def __init__(self):
        """Initialize connection manager."""
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        # Rate limiting: token bucket for each connection
        self._rate_limits: Dict[WebSocket, Dict[str, float]] = {}

    def _check_rate_limit(self, websocket: WebSocket) -> bool:
        """
        Check if message is within rate limit using token bucket algorithm.

        Args:
            websocket: WebSocket connection to check

        Returns:
            True if message is allowed, False if rate limited
        """
        now = time.monotonic()

        # Initialize bucket if not exists
        if websocket not in self._rate_limits:
            self._rate_limits[websocket] = {
                "tokens": self.BURST_SIZE,
                "last_update": now,
            }

        bucket = self._rate_limits[websocket]
        elapsed = now - bucket["last_update"]

        # Add tokens based on elapsed time
        bucket["tokens"] = min(
            self.BURST_SIZE, bucket["tokens"] + elapsed * self.MESSAGES_PER_SECOND
        )
        bucket["last_update"] = now

        # Check if we have at least 1 token
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True

        return False

    async def connect(self, websocket: WebSocket) -> bool:
        """
        Connect a new WebSocket client with connection limit enforcement.

        Args:
            websocket: WebSocket connection

        Returns:
            True if connection was accepted, False if limit reached
        """
        # Note: WebSocket should already be accepted before calling this method
        async with self._lock:
            if len(self._connections) >= self.MAX_CONNECTIONS:
                logger.warning(
                    f"WebSocket connection limit reached ({self.MAX_CONNECTIONS}). "
                    "Rejecting new connection."
                )
                return False
            self._connections.add(websocket)
            # Initialize rate limit bucket
            self._rate_limits[websocket] = {
                "tokens": self.BURST_SIZE,
                "last_update": time.monotonic(),
            }
            logger.debug(f"WebSocket connected. Active connections: {len(self._connections)}")
            return True

    async def disconnect(self, websocket: WebSocket):
        """
        Disconnect a WebSocket client.

        Args:
            websocket: WebSocket connection
        """
        async with self._lock:
            self._connections.discard(websocket)
            # Clean up rate limit data
            self._rate_limits.pop(websocket, None)
            logger.debug(f"WebSocket disconnected. Active connections: {len(self._connections)}")

    async def send_message(self, websocket: WebSocket, message: dict) -> bool:
        """
        Send message to a WebSocket client with rate limiting.

        Args:
            websocket: WebSocket connection
            message: Message dictionary to send

        Returns:
            True if message was sent, False if rate limited
        """
        if not self._check_rate_limit(websocket):
            logger.warning("WebSocket message rate limit exceeded")
            return False

        try:
            await websocket.send_json(message)
            return True
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")
            return False

    async def broadcast(self, message: dict):
        """
        Broadcast message to all connected clients.

        Args:
            message: Message dictionary to broadcast
        """
        async with self._lock:
            connections = self._connections.copy()

        disconnected = []
        for connection in connections:
            try:
                # Note: Broadcast doesn't check rate limit to ensure
                # important updates reach all clients
                await connection.send_json(message)
            except (WebSocketDisconnect, RuntimeError, ConnectionError) as e:
                logger.debug(f"WebSocket connection closed during broadcast: {e}")
                disconnected.append(connection)
            except Exception as e:
                logger.error(f"Unexpected error broadcasting to WebSocket client: {e}")
                disconnected.append(connection)

        if disconnected:
            async with self._lock:
                for conn in disconnected:
                    self._connections.discard(conn)
                    self._rate_limits.pop(conn, None)
