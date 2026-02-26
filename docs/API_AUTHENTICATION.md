# API Authentication Guide

This document describes the authentication mechanisms available for the VFS-Bot API endpoints.

## Overview

The VFS-Bot web dashboard provides three authentication methods:

1. **JWT Token Authentication** - Recommended for web/mobile applications
2. **API Key Authentication** - Recommended for server-to-server communication
3. **Hybrid Authentication** - Automatically accepts either JWT or API Key (used for bot control endpoints)

## JWT Token Authentication

### Configuration

Add these environment variables to your `.env` file:

```env
# JWT Configuration
API_SECRET_KEY=your-secret-key-here-min-32-characters
JWT_ALGORITHM=HS384
JWT_EXPIRY_HOURS=24

# Admin Credentials
ADMIN_USERNAME=admin
# ⚠️ MUST be a bcrypt hash in production. Generate with:
#   python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('your-password'))"
ADMIN_PASSWORD=$2b$12$your-bcrypt-hashed-password-here
```

### Login Endpoint

**POST** `/api/v1/auth/login`

Request body:
```json
{
  "username": "admin",
  "password": "your-password"
}
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Using JWT Token

Include the token in the Authorization header for protected endpoints:

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://localhost:8000/api/v1/bot/logs
```

### Protected Endpoints

The following endpoints require JWT authentication:

- `GET /api/v1/vfs-accounts` - Retrieve VFS accounts
- `POST /api/v1/vfs-accounts` - Create VFS account
- `PUT /api/v1/vfs-accounts/{id}` - Update VFS account
- `PATCH /api/v1/vfs-accounts/{id}` - Toggle VFS account active status
- `DELETE /api/v1/vfs-accounts/{id}` - Delete VFS account
- `GET /api/v1/audit/logs` - View audit logs
- `GET /api/v1/payment/payment-card` - View payment card

## Hybrid Authentication

Hybrid authentication accepts **either** JWT tokens or API keys, automatically detecting which one is provided. This provides maximum flexibility for API consumers.

### How It Works

1. The system first attempts to validate the token as a JWT
2. If JWT validation fails, it tries to validate as an API key
3. If both fail, a 401 Unauthorized error is returned
4. The authentication metadata includes an `auth_method` field indicating which method was used

### Endpoints Using Hybrid Authentication

The following bot control endpoints accept both JWT tokens and API keys:

- `POST /api/v1/bot/start` - Start the bot
- `POST /api/v1/bot/stop` - Stop the bot
- `POST /api/v1/bot/restart` - Restart the bot
- `POST /api/v1/bot/check-now` - Trigger manual check
- `GET /api/v1/bot/logs` - Retrieve bot logs

### Using Hybrid Authentication

You can use either a JWT token or an API key - the system will accept both:

```bash
# Using JWT token
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -X POST \
     http://localhost:8000/api/v1/bot/start

# Using API key
curl -H "Authorization: Bearer YOUR_API_KEY" \
     -X POST \
     http://localhost:8000/api/v1/bot/start
```

Both requests will work identically, giving you flexibility in how you authenticate.

## API Key Authentication

### Configuration

Add this environment variable to your `.env` file:

```env
DASHBOARD_API_KEY=your-secure-api-key-here
```

### Using API Key

API keys can be used directly for hybrid authentication endpoints (see above) or for any other endpoints that specifically require API key authentication.

Include the API key in the Authorization header:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     -X POST \
     -H "Content-Type: application/json" \
     -d '{"action": "start", "config": {}}' \
     http://localhost:8000/api/v1/bot/start
```

## Generate New API Key

**POST** `/api/v1/auth/generate-key`

Requires admin secret (one-time use):

```bash
curl -X POST \
     -H "Content-Type: application/json" \
     -d '{"secret": "YOUR_ADMIN_SECRET"}' \
     http://localhost:8000/api/v1/auth/generate-key
```

Configure the admin secret:

```env
ADMIN_SECRET=one-time-secret-for-key-generation
```

## Public Endpoints

These endpoints do not require authentication:

- `GET /` - Dashboard home page
- `GET /health` - Health check
- `GET /api/status` - Bot status
- `GET /metrics` - Metrics endpoint
- `WS /ws` - WebSocket connection

## Webhook Security

Webhook endpoints use HMAC signature verification to ensure requests come from trusted sources.

### Configuration

Add the webhook secret to your `.env` file:

```env
SMS_WEBHOOK_SECRET=your-webhook-secret-32-chars-minimum
```

### Webhook Signature Verification

All webhook endpoints (`/api/webhook/sms`, `/api/webhook/otp/*`, etc.) require signature verification:

- **Production**: `SMS_WEBHOOK_SECRET` is required; unsigned requests are rejected
- **Development with secret**: Signatures are verified; invalid signatures are rejected
- **Development without secret**: Warning is logged; unsigned requests are allowed

### Generating Webhook Signatures

Signatures use HMAC-SHA256 with the format: `t=<timestamp>,v1=<signature>`

Example in Python:
```python
import hmac
import hashlib
import time
import json

payload = {"from": "+1234567890", "text": "Your OTP is 123456"}
secret = "your-webhook-secret"
timestamp = int(time.time())

# Create signed payload
signed_payload = f"{timestamp}.{json.dumps(payload)}"
signature = hmac.new(
    secret.encode(),
    signed_payload.encode(),
    hashlib.sha256
).hexdigest()

# Header value
header = f"t={timestamp},v1={signature}"
```

Send the signature in the `X-Webhook-Signature` header:
```bash
curl -X POST \
     -H "Content-Type: application/json" \
     -H "X-Webhook-Signature: t=1234567890,v1=abc123..." \
     -d '{"from": "+1234567890", "text": "Your OTP is 123456"}' \
     http://localhost:8000/api/webhook/sms
```

## Security Best Practices

1. **Use Strong Secrets**: Generate random, long secret keys (minimum 32 characters)
2. **HTTPS Only**: Always use HTTPS in production
3. **Rotate Keys**: Regularly rotate API keys, JWT secrets, and webhook secrets
4. **Environment Variables**: Never commit secrets to version control
5. **Token Expiry**: Set appropriate JWT expiry times (default: 24 hours)
6. **Webhook Signatures**: Always configure `SMS_WEBHOOK_SECRET` in production
7. **Timestamp Validation**: Webhook signatures include timestamps to prevent replay attacks (5-minute tolerance)

## Example: Python Client

```python
import requests

# Login and get JWT token
response = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    json={"username": "admin", "password": "your-password"}
)
token = response.json()["access_token"]

# Use token to access protected endpoint
headers = {"Authorization": f"Bearer {token}"}
logs = requests.get("http://localhost:8000/api/v1/bot/logs", headers=headers)
print(logs.json())
```

## Example: JavaScript/Node.js Client

```javascript
// Login and get JWT token
const loginResponse = await fetch('http://localhost:8000/api/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: 'admin', password: 'your-password' })
});
const { access_token } = await loginResponse.json();

// Use token to access protected endpoint
const logsResponse = await fetch('http://localhost:8000/api/v1/bot/logs', {
  headers: { 'Authorization': `Bearer ${access_token}` }
});
const logs = await logsResponse.json();
console.log(logs);
```

## Troubleshooting

### 401 Unauthorized

- Check that your credentials or API key are correct
- Verify the token hasn't expired
- Ensure the Authorization header is properly formatted

### 403 Forbidden

- Endpoint requires authentication but none was provided
- Check that you're using the correct authentication method

### Token Expired

- JWT tokens expire after the configured time (default: 24 hours)
- Login again to get a new token
