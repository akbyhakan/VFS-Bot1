# SMS Webhook Setup Guide

This guide explains how to set up SMS Forwarder to send OTP messages to VFS-Bot via webhooks.

## Overview

The SMS webhook system enables each VFS account to receive SMS OTP messages automatically through a unique webhook URL. SMS Forwarder app on Android forwards SMS messages to these webhook URLs.

### Architecture

```
SIM Cards (150+)  ──► Android Phone (SMS Forwarder)  ──► Webhook URLs  ──► VFS-Bot Sessions
```

## Prerequisites

1. Android phone with all SIM cards
2. SMS Forwarder app installed
3. VFS-Bot running and accessible from the internet
4. Base webhook URL configured (e.g., `https://your-api-domain.example.com`)

## Setup Steps

### 1. Register VFS Account

Each VFS account needs to be registered to get a unique webhook URL:

```python
from src.services.otp_manager import OTPManager

# Initialize OTP Manager
manager = OTPManager(
    email="admin@example.com",
    app_password="xxxx-xxxx-xxxx-xxxx"
)
manager.start()

# Register VFS account
account = manager.register_account(
    vfs_email="user@email.com",
    vfs_password="password123",
    phone_number="+905551234567",
    target_email="bot@example.com",
    country="Netherlands"
)

print(f"Webhook URL: {account.webhook_url}")
# Output: https://your-api-domain.example.com/webhook/sms/tk_a1b2c3d4e5f6g7h8i9j0k1l2
```

### 2. Configure SMS Forwarder

For each SIM card:

1. Open SMS Forwarder app
2. Create a new forwarding rule
3. Set conditions:
   - From: Any (or specific VFS numbers)
   - Contains: "OTP" or "code" (optional)
4. Set action:
   - Type: **Webhook**
   - Method: **POST**
   - URL: Use the webhook URL from step 1
   - Content Type: **application/json**

#### Payload Template

SMS Forwarder should send one of these formats:

**Format 1 (Recommended):**
```json
{
  "message": "{{SMS_CONTENT}}",
  "from": "{{SENDER_NUMBER}}",
  "timestamp": "{{TIMESTAMP}}",
  "sim_slot": {{SIM_SLOT}}
}
```

**Format 2 (Alternative):**
```json
{
  "text": "{{SMS_CONTENT}}",
  "phone": "{{SENDER_NUMBER}}"
}
```

**Format 3 (Minimal):**
```json
{
  "body": "{{SMS_CONTENT}}"
}
```

### 3. Test Webhook

Before going live, test the webhook:

```bash
# Test endpoint (doesn't process OTP)
curl -X POST "https://your-api-domain.example.com/webhook/sms/tk_a1b2c3d4e5f6g7h8i9j0k1l2/test" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Your VFS OTP is 123456",
    "from": "+905551234567"
  }'

# Expected response:
{
  "status": "test_success",
  "message": "Webhook is correctly configured",
  "account_id": "acc_...",
  "parsed_message": "Your VFS OTP is 123456",
  "note": "This is a test - OTP was NOT processed"
}
```

### 4. Start Bot Session

When starting a bot session for the account:

```python
# Start session - automatically links to webhook
session_id = manager.start_session(account.account_id)

# Wait for OTP (from SMS or email)
otp = manager.wait_for_otp(session_id, timeout=120)

if otp:
    print(f"OTP received: {otp}")
    # Use OTP for VFS login

# End session - unlinks from webhook
manager.end_session(session_id)
```

## Supported Payload Formats

The webhook system automatically parses different SMS Forwarder formats:

### Message Field Priority
1. `message`
2. `text`
3. `body`
4. `sms`
5. `content`
6. `msg`

### Phone Field Priority
1. `from`
2. `phone`
3. `phone_number`
4. `sender`
5. `number`

### OTP Extraction Patterns
The system automatically extracts OTP codes using these patterns:
- `OTP: 123456`
- `code: 123456`
- `verification: 123456`
- Any 4-8 digit number

## Webhook Endpoints

### POST /webhook/sms/{token}
Receives SMS from forwarder.

**Request:**
```json
{
  "message": "Your OTP is 123456",
  "from": "+905551234567"
}
```

**Response:**
```json
{
  "status": "success",
  "account_id": "acc_...",
  "otp_extracted": true,
  "session_id": "session_...",
  "message": "OTP received and processed"
}
```

### GET /webhook/sms/{token}/status
Check webhook token status.

**Response:**
```json
{
  "status": "active",
  "account_id": "acc_...",
  "phone_number": "+905551234567",
  "webhook_url": "https://your-api-domain.example.com/webhook/sms/tk_...",
  "created_at": "2026-01-29T15:00:00Z",
  "last_used_at": "2026-01-29T15:30:00Z",
  "session_linked": true,
  "session_id": "session_..."
}
```

### POST /webhook/sms/{token}/test
Test webhook without processing OTP.

## Security

### Rate Limiting
- 60 requests per minute per IP address
- 10 test requests per minute per IP address

### Token Format
- Prefix: `tk_`
- Length: 24 random hex characters
- Example: `tk_a1b2c3d4e5f6g7h8i9j0k1l2`
- Tokens are cryptographically random and unpredictable

### Optional HMAC Signature
For additional security, configure webhook signature:

```bash
# In .env file
WEBHOOK_SIGNATURE_SECRET=your-secret-key-here
```

Then SMS Forwarder should include:
```
X-Webhook-Signature: sha256=<hmac_signature>
```

## Troubleshooting

### No OTP Extracted

**Problem:** Webhook receives SMS but doesn't extract OTP.

**Solutions:**
1. Check SMS format matches expected patterns
2. Test with `/test` endpoint to verify payload parsing
3. Check logs for extraction errors
4. Verify OTP is in the expected format (4-8 digits)

### Token Not Found

**Problem:** Webhook returns 404 "Invalid token".

**Solutions:**
1. Verify token in URL is correct
2. Check if account is still active
3. Use `/status` endpoint to verify token

### No Session Linked

**Problem:** OTP extracted but not delivered to session.

**Solutions:**
1. Verify `start_session()` was called for the account
2. Check if session expired (default 600 seconds)
3. Verify session is waiting for OTP

### Rate Limit Exceeded

**Problem:** Webhook returns 429 "Too Many Requests".

**Solutions:**
1. Reduce SMS Forwarder retry frequency
2. Check if multiple devices are forwarding to same webhook
3. Contact admin to increase rate limit if needed

## Environment Variables

Add to `.env` file:

```bash
# Base URL for webhook endpoints
WEBHOOK_BASE_URL=https://your-api-domain.example.com

# Token prefix (default: tk_)
WEBHOOK_TOKEN_PREFIX=tk_

# Rate limit (requests per minute)
WEBHOOK_RATE_LIMIT=60

# Optional HMAC signature secret
WEBHOOK_SIGNATURE_SECRET=
```

## Example Usage

Complete example with error handling:

```python
from src.services.otp_manager import OTPManager
import logging

logging.basicConfig(level=logging.INFO)

# Initialize manager
manager = OTPManager(
    email="admin@example.com",
    app_password="xxxx-xxxx-xxxx-xxxx"
)
manager.start()

try:
    # Register account
    account = manager.register_account(
        vfs_email="user@email.com",
        vfs_password="secure_password",
        phone_number="+905551234567",
        target_email="bot@example.com",
        country="Netherlands",
        visa_type="Tourist"
    )
    
    print(f"✓ Account registered")
    print(f"✓ Webhook URL: {account.webhook_url}")
    print(f"✓ Configure this URL in SMS Forwarder")
    
    # Start session
    session_id = manager.start_session(account.account_id)
    print(f"✓ Session started: {session_id}")
    
    # Wait for OTP
    print("⏳ Waiting for OTP (120 seconds)...")
    otp = manager.wait_for_otp(session_id, timeout=120)
    
    if otp:
        print(f"✓ OTP received: {otp}")
        # Use OTP for login
    else:
        print("✗ OTP timeout")
    
    # Cleanup
    manager.end_session(session_id)
    print("✓ Session ended")
    
finally:
    manager.stop()
```

## Best Practices

1. **One webhook per phone number** - Each SIM card should forward to its corresponding account's webhook
2. **Test before production** - Always use `/test` endpoint to verify setup
3. **Monitor rate limits** - Keep SMS forwarding under 60 requests/minute
4. **Use HTTPS** - Never use HTTP in production
5. **Secure tokens** - Treat webhook tokens like passwords
6. **Monitor logs** - Check logs for delivery issues
7. **Session timeout** - Start sessions only when needed to avoid timeouts

## Support

For issues:
1. Check logs: `tail -f logs/vfs-bot.log`
2. Test webhook: `curl -X POST .../test`
3. Check status: `curl .../status`
4. Review this documentation
5. Contact support with error details
