"""Webhook signature verification utilities."""

import hmac
import hashlib
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str,
    timestamp_tolerance: int = 300
) -> bool:
    """
    Verify webhook signature using HMAC-SHA256.
    
    Args:
        payload: Raw request body bytes
        signature: Signature from header (format: "t=timestamp,v1=signature")
        secret: Webhook secret key
        timestamp_tolerance: Maximum age of signature in seconds
        
    Returns:
        True if signature is valid
    """
    try:
        # Parse signature header
        parts = dict(part.split('=', 1) for part in signature.split(','))
        
        timestamp = parts.get('t')
        provided_sig = parts.get('v1')
        
        if not timestamp or not provided_sig:
            logger.warning("Invalid signature format")
            return False
        
        # Check timestamp to prevent replay attacks
        try:
            sig_timestamp = int(timestamp)
            current_time = int(time.time())
            
            if abs(current_time - sig_timestamp) > timestamp_tolerance:
                logger.warning(
                    f"Signature timestamp too old: {current_time - sig_timestamp}s"
                )
                return False
        except ValueError:
            logger.warning("Invalid timestamp in signature")
            return False
        
        # Compute expected signature
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        expected_sig = hmac.new(
            secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected_sig, provided_sig)
        
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False


def generate_webhook_signature(payload: str, secret: str) -> str:
    """
    Generate webhook signature for outgoing webhooks.
    
    Args:
        payload: Request body as string
        secret: Webhook secret key
        
    Returns:
        Signature header value
    """
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload}"
    
    signature = hmac.new(
        secret.encode('utf-8'),
        signed_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return f"t={timestamp},v1={signature}"
