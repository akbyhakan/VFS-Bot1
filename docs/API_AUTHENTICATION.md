# API Authentication Guide

This document describes the authentication mechanisms available for the VFS-Bot API endpoints.

## Overview

The VFS-Bot web dashboard provides two authentication methods:

1. **JWT Token Authentication** - Recommended for web/mobile applications
2. **API Key Authentication** - Recommended for server-to-server communication

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
ADMIN_PASSWORD=your-secure-password
```

### Login Endpoint

**POST** `/api/auth/login`

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
     http://localhost:8000/api/logs
```

### Protected Endpoints

The following endpoints require JWT authentication:

- `GET /api/logs` - Retrieve bot logs

## API Key Authentication

### Configuration

Add this environment variable to your `.env` file:

```env
DASHBOARD_API_KEY=your-secure-api-key-here
```

### Using API Key

The following endpoints require API key authentication:

- `POST /api/bot/start` - Start the bot
- `POST /api/bot/stop` - Stop the bot

Include the API key in the Authorization header:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     -X POST \
     -H "Content-Type: application/json" \
     -d '{"action": "start", "config": {}}' \
     http://localhost:8000/api/bot/start
```

## Generate New API Key

**POST** `/api/auth/generate-key`

Requires admin secret (one-time use):

```bash
curl -X POST \
     -H "Content-Type: application/json" \
     -d '{"secret": "YOUR_ADMIN_SECRET"}' \
     http://localhost:8000/api/auth/generate-key
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

## Security Best Practices

1. **Use Strong Secrets**: Generate random, long secret keys
2. **HTTPS Only**: Always use HTTPS in production
3. **Rotate Keys**: Regularly rotate API keys and JWT secrets
4. **Environment Variables**: Never commit secrets to version control
5. **Token Expiry**: Set appropriate JWT expiry times (default: 24 hours)

## Example: Python Client

```python
import requests

# Login and get JWT token
response = requests.post(
    "http://localhost:8000/api/auth/login",
    json={"username": "admin", "password": "your-password"}
)
token = response.json()["access_token"]

# Use token to access protected endpoint
headers = {"Authorization": f"Bearer {token}"}
logs = requests.get("http://localhost:8000/api/logs", headers=headers)
print(logs.json())
```

## Example: JavaScript/Node.js Client

```javascript
// Login and get JWT token
const loginResponse = await fetch('http://localhost:8000/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: 'admin', password: 'your-password' })
});
const { access_token } = await loginResponse.json();

// Use token to access protected endpoint
const logsResponse = await fetch('http://localhost:8000/api/logs', {
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
