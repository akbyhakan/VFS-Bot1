# Security Best Practices for VFS-Bot

This document outlines security best practices, configurations, and guidelines for maintaining a secure VFS-Bot deployment.

## Table of Contents

1. [Content Security Policy (CSP)](#content-security-policy)
2. [Payment Security](#payment-security)
3. [Proxy Security](#proxy-security)
4. [Secure Memory Handling](#secure-memory-handling)
5. [Alert System](#alert-system)
6. [Circuit Breaker](#circuit-breaker)
7. [General Security Guidelines](#general-security-guidelines)

---

## Content Security Policy

### Environment-Aware CSP

VFS-Bot implements environment-aware Content Security Policy to balance security and development needs:

**Production (Strict Mode):**
- `unsafe-inline` and `unsafe-eval` are **disabled**
- Nonce-based script and style loading required
- HSTS (HTTP Strict Transport Security) enabled
- All resources upgraded to HTTPS

**Development Mode:**
- Relaxed CSP for hot-reloading and development tools
- `unsafe-inline` and `unsafe-eval` allowed
- Local connections permitted

### Configuration

The CSP mode is automatically determined by the `ENV` environment variable:

```bash
# Production (strict CSP)
ENV=production

# Development (relaxed CSP)
ENV=development
ENV=dev
ENV=local
ENV=testing
```

You can also explicitly set CSP mode:

```python
from web.middleware.security_headers import SecurityHeadersMiddleware

# Force strict CSP
app.add_middleware(SecurityHeadersMiddleware, strict_csp=True)

# Force relaxed CSP (not recommended for production)
app.add_middleware(SecurityHeadersMiddleware, strict_csp=False)
```

### Best Practices

1. **Always run production with strict CSP** - Set `ENV=production`
2. **Use nonces for inline scripts** - Access via `request.state.csp_nonce`
3. **Avoid inline event handlers** - Use event listeners instead
4. **Load resources from self or trusted CDNs** - Specify in CSP policy

---

## Payment Security

### Automated Payments Are Disabled

**CRITICAL:** Automated card payment processing is **completely disabled** for PCI-DSS compliance.

Any attempt to configure automated payments will result in a `ValueError`:

```python
# This will FAIL
config = {"payment": {"method": "automated_card"}}
service = PaymentService(config)  # Raises ValueError
```

### Manual Payment Only

Only manual payment processing is supported:

```python
config = {"payment": {"method": "manual"}}
service = PaymentService(config)
```

### PCI-DSS Compliance

See [docs/PCI_DSS_COMPLIANCE.md](./PCI_DSS_COMPLIANCE.md) for details on:
- Why automated payments are disabled
- Requirements for PCI-DSS Level 1 compliance
- Alternative payment integration approaches

### CVV Security

CVV is **NEVER stored** in the database and only exists in memory during transaction processing.

---

## Proxy Security

### Database-Backed Proxy Management

VFS-Bot uses database-backed proxy management with encrypted credentials for enhanced security.

**Key Security Features:**

1. **Encrypted Storage**: Proxy passwords are encrypted using Fernet (AES-128 CBC) before storage
2. **No Hardcoded Credentials**: All credentials removed from config files
3. **Password Masking**: Passwords are masked in logs for safe logging
4. **JWT Authentication**: All proxy management endpoints require JWT authentication
5. **Input Validation**: Port ranges, server names validated before storage

### Configuration

**IMPORTANT:** Never commit real proxy credentials to version control.

The `config/proxy-endpoints.csv` file should contain only the header and examples:

```csv
endpoint
# Format: server:port:username:password
# Example: gw.netnut.net:5959:your_username:your_password
```

### Adding Proxies

Use the API endpoints to add proxies securely:

```bash
# Add a single proxy
curl -X POST https://your-api.com/api/proxy/add \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "server": "gw.netnut.net",
    "port": 5959,
    "username": "your_username",
    "password": "your_password"
  }'

# Upload CSV file
curl -X POST https://your-api.com/api/proxy/upload \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@proxies.csv"
```

### Encryption Key Management

Proxy passwords are encrypted using the `ENCRYPTION_KEY` environment variable:

```bash
# Generate a new encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Set in environment
export ENCRYPTION_KEY="your_generated_key_here"
```

**CRITICAL:** 
- Store the encryption key securely (e.g., AWS Secrets Manager, HashiCorp Vault)
- Never commit the encryption key to version control
- Rotate keys periodically using the key rotation support
- Back up encrypted data before key rotation

### API Endpoints

All proxy management endpoints require JWT authentication:

- `POST /api/proxy/add` - Add single proxy
- `GET /api/proxy/list` - List all proxies (passwords excluded)
- `GET /api/proxy/{id}` - Get specific proxy details
- `PUT /api/proxy/{id}` - Update proxy
- `DELETE /api/proxy/{id}` - Delete proxy
- `DELETE /api/proxy/clear-all` - Delete all proxies
- `POST /api/proxy/reset-failures` - Reset failure counters
- `POST /api/proxy/upload` - Upload CSV file (max 10MB)

### Password Masking in Logs

Use the `mask_proxy_password()` utility for safe logging:

```python
from src.utils.security.netnut_proxy import mask_proxy_password

endpoint = "gw.netnut.net:5959:username:password"
safe_log = mask_proxy_password(endpoint)
# Output: gw.netnut.net:5959:username:***
logger.info(f"Using proxy: {safe_log}")
```

### Best Practices

1. **Never commit credentials** - Use `.gitignore` to exclude proxy files
2. **Rotate credentials regularly** - Update proxy passwords periodically
3. **Monitor failure rates** - Use the failure tracking to identify compromised proxies
4. **Use unique credentials** - Each proxy should have unique authentication
5. **Limit access** - Only authorized services should access proxy endpoints
6. **Audit logs** - Monitor proxy CRUD operations via audit logs

---

### CVV Security (Payment)

CVV codes are handled with special security measures:

```python
from src.utils.secure_memory import SecureCVV

# Use context manager for automatic memory cleanup
with SecureCVV(cvv_input) as cvv:
    # Use cvv securely
    process_payment(cvv)
# CVV is automatically cleared from memory
```

**Security guarantees:**
- CVV exists only within the context manager
- Memory is zeroed using `ctypes.memset`
- No CVV is ever logged or stored

---

## Secure Memory Handling

### Utility Functions

The `src.utils.secure_memory` module provides utilities for handling sensitive data:

#### `secure_zero_memory(data)`

Securely zeros out memory containing sensitive data:

```python
from src.utils.secure_memory import secure_zero_memory

sensitive_data = bytearray(b"secret_key_12345")
# ... use data ...
secure_zero_memory(sensitive_data)
# Memory is now zeroed
```

#### `SecureCVV` Context Manager

Handles CVV codes with automatic cleanup:

```python
from src.utils.secure_memory import SecureCVV

user_input_cvv = request.form.get("cvv")

with SecureCVV(user_input_cvv) as cvv:
    # cvv is available as string
    result = payment_gateway.charge(cvv=cvv)
# cvv is automatically cleared from memory
```

### Best Practices

1. **Use context managers** for sensitive data
2. **Never log sensitive data** - Use sanitized versions
3. **Clear memory immediately** after use
4. **Use secure_zero_memory** for bytearray/bytes cleanup

---

## Alert System

### Multi-Channel Alerts

The alert service supports multiple notification channels:

- **LOG** - Always available, logs to application logs
- **TELEGRAM** - Send alerts to Telegram bot
- **EMAIL** - Send email notifications
- **WEBHOOK** - POST alerts to custom webhook

### Configuration

```python
from src.services.alert_service import (
    configure_alert_service,
    AlertConfig,
    AlertChannel,
)

config = AlertConfig(
    enabled_channels=[
        AlertChannel.LOG,
        AlertChannel.TELEGRAM,
    ],
    telegram_bot_token="your_bot_token",
    telegram_chat_id="your_chat_id",
)

configure_alert_service(config)
```

### Sending Alerts

```python
from src.services.alert_service import send_critical_alert

# Send critical alert
await send_critical_alert(
    "Payment service failure detected",
    metadata={"error_count": 5, "service": "payment"}
)
```

### Alert Severity Levels

- `INFO` - Informational messages
- `WARNING` - Warning conditions
- `ERROR` - Error conditions
- `CRITICAL` - Critical conditions requiring immediate attention

---

## Circuit Breaker

### Purpose

The circuit breaker prevents cascading failures by temporarily blocking operations when error thresholds are exceeded.

### States

- **CLOSED** - Normal operation, requests allowed
- **OPEN** - Too many errors, requests blocked
- **HALF_OPEN** - Testing if service recovered

### Configuration

Circuit breaker constants in `src/constants.py`:

```python
class CircuitBreaker:
    FAIL_THRESHOLD = 5              # Consecutive errors to open
    MAX_ERRORS_PER_HOUR = 20        # Total errors in window
    ERROR_TRACKING_WINDOW = 3600    # Time window (seconds)
    RESET_TIMEOUT_SECONDS = 60      # Time before half-open attempt
    BACKOFF_BASE_SECONDS = 60       # Base backoff time
    BACKOFF_MAX_SECONDS = 600       # Maximum backoff time
```

### Usage

```python
from src.core.circuit_breaker import CircuitBreaker

# For general use with decorator pattern
cb = CircuitBreaker(
    failure_threshold=5,
    timeout_seconds=60.0,
    name="MyService"
)

@cb.protected
async def risky_operation():
    # Your code here
    pass

# Or for bot-specific wrapper with backward-compatible API
from src.services.bot.circuit_breaker_service import CircuitBreakerService

cb = CircuitBreakerService()

# Check if available
if await cb.is_available():
    try:
        # Perform operation
        result = await risky_operation()
        await cb.record_success()
    except Exception as e:
        await cb.record_failure()
else:
    # Circuit is open, skip operation
    logger.warning("Circuit breaker is OPEN")
```

### Monitoring

```python
# Get circuit breaker statistics
stats = await cb.get_stats()

print(f"State: {stats.state}")
print(f"Consecutive errors: {stats.consecutive_errors}")
print(f"Total errors in window: {stats.total_errors_in_window}")
```

---

## General Security Guidelines

### Environment Variables

**Always use `.env` file for sensitive configuration:**

```bash
# Never commit these to git!
SECRET_KEY=your-very-long-secret-key-here
DATABASE_PASSWORD=strong-password
API_KEY=your-api-key

# Use strong secrets (64+ characters for SECRET_KEY)
SECRET_KEY=$(openssl rand -hex 32)
```

### API Keys and Tokens

1. **Never hardcode** API keys in source code
2. **Use environment variables** for all secrets
3. **Rotate keys regularly** (every 90 days minimum)
4. **Use separate keys** for dev/staging/production

### Authentication

1. **Use strong passwords** - Minimum 12 characters, mixed case, numbers, symbols
2. **Enable 2FA** where available
3. **Lock accounts** after failed login attempts (configured in `RateLimits.LOGIN_MAX_REQUESTS`)
4. **Use JWT tokens** with short expiration (configured in `Security.JWT_EXPIRY_HOURS`)

### Database Security

1. **Use encrypted connections** for remote databases
2. **Limit connection pool size** - Prevents resource exhaustion
3. **Set query timeouts** - Prevents long-running queries
4. **Regular backups** - Automated and tested

### Docker Security

1. **Use non-root user** in containers
2. **Scan images** for vulnerabilities
3. **Use specific versions** - Avoid `latest` tag
4. **Minimize image size** - Fewer attack surfaces

### Network Security

1. **Use HTTPS only** in production
2. **Configure firewall rules** - Whitelist only required ports
3. **Use VPN/private networks** for database access
4. **Enable rate limiting** - Configured in `RateLimits` class

### Logging

1. **Never log sensitive data** - passwords, API keys, CVV, etc.
2. **Use structured logging** - JSON format preferred
3. **Rotate logs regularly** - Prevent disk space issues
4. **Monitor logs** for security events

### Dependency Management

1. **Keep dependencies updated** - `pip install -U -r requirements.txt`
2. **Use security scanners** - `pip-audit`, `safety`
3. **Pin versions** in `requirements.txt`
4. **Review security advisories** - Check GitHub Security tab

### Code Security

1. **Input validation** - Validate all user inputs
2. **Output encoding** - Prevent XSS attacks
3. **SQL parameterization** - Use parameterized queries
4. **CSRF protection** - Enable in web framework

### Incident Response

1. **Monitor alerts** - Configure alert service
2. **Have response plan** - Document procedures
3. **Regular drills** - Practice incident response
4. **Post-mortem analysis** - Learn from incidents

---

## Security Checklist

Before deploying to production:

- [ ] Set `ENV=production`
- [ ] Configure strict CSP
- [ ] Enable HSTS
- [ ] Use HTTPS only
- [ ] Configure alert service (Telegram/Email)
- [ ] Set up monitoring and logging
- [ ] Review and rotate all API keys
- [ ] Enable rate limiting
- [ ] Configure circuit breaker thresholds
- [ ] Set strong SECRET_KEY (64+ characters)
- [ ] Enable 2FA for admin accounts
- [ ] Configure database encryption
- [ ] Set up automated backups
- [ ] Review and test disaster recovery plan
- [ ] Scan dependencies for vulnerabilities
- [ ] Configure firewall rules
- [ ] Set up intrusion detection
- [ ] Document security procedures
- [ ] Train team on security practices

---

## Reporting Security Issues

If you discover a security vulnerability, please follow responsible disclosure:

1. **Do not** open a public GitHub issue
2. **Email** security contact (see main SECURITY.md)
3. **Include** detailed steps to reproduce
4. **Wait** for acknowledgment before public disclosure

---

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [PCI DSS Requirements](https://www.pcisecuritystandards.org/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)
- [CSP Reference](https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP)

---

**Last Updated:** 2026-01-28  
**Version:** 1.0.0
