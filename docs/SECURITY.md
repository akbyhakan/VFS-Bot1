# Security Best Practices for VFS-Bot

This document outlines security best practices, configurations, and guidelines for maintaining a secure VFS-Bot deployment.

## Table of Contents

1. [Content Security Policy (CSP)](#content-security-policy)
2. [Payment Security](#payment-security)
3. [Proxy Security](#proxy-security)
4. [Log Sanitization](#log-sanitization)
5. [Secure Memory Handling](#secure-memory-handling)
6. [Alert System](#alert-system)
7. [Circuit Breaker](#circuit-breaker)
8. [General Security Guidelines](#general-security-guidelines)

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

### Automated Payment with Encrypted CVV

VFS-Bot supports automated payment processing for personal use. Card data is encrypted at rest using Fernet (AES-128 CBC).

### CVV Security

CVV is stored **encrypted** (Fernet AES-128) in the database — this is optional and only used for automated payment support. The `SecureCVV` context manager handles in-memory cleanup to minimize the window during which CVV exists in cleartext memory.

```python
from src.utils.secure_memory import SecureCVV

with SecureCVV(user_input_cvv) as cvv:
    # cvv is available as string
    result = payment_gateway.charge(cvv=cvv)
# cvv is automatically cleared from memory
```

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
curl -c cookies.txt -b cookies.txt \
  -X POST https://your-api.com/api/v1/proxy/add \
  -H "Content-Type: application/json" \
  -d '{
    "server": "gw.netnut.net",
    "port": 5959,
    "username": "your_username",
    "password": "your_password"
  }'

# Alternative: use Authorization header for non-browser clients
# curl -X POST https://your-api.com/api/v1/proxy/add \
#   -H "Authorization: Bearer YOUR_JWT_TOKEN" \
#   -H "Content-Type: application/json" \
#   -d '{ ... }'

# Upload CSV file
curl -c cookies.txt -b cookies.txt \
  -X POST https://your-api.com/api/v1/proxy/upload \
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

- `POST /api/v1/proxy/add` - Add single proxy
- `GET /api/v1/proxy/list` - List all proxies (passwords excluded)
- `GET /api/v1/proxy/{id}` - Get specific proxy details
- `PUT /api/v1/proxy/{id}` - Update proxy
- `DELETE /api/v1/proxy/{id}` - Delete proxy
- `DELETE /api/v1/proxy/clear-all` - Delete all proxies
- `POST /api/v1/proxy/reset-failures` - Reset failure counters
- `POST /api/v1/proxy/upload` - Upload CSV file (max 10MB)

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

## Log Sanitization

### Protection Against Log Injection

VFS-Bot implements log sanitization to prevent log injection attacks. User-controlled values are sanitized before being written to logs to prevent:

- **ANSI Escape Sequence Injection**: Attackers cannot inject color codes or terminal control sequences
- **Newline Injection**: Prevents forging of fake log entries by injecting newline characters
- **Control Character Injection**: Removes potentially harmful control characters

### Usage

Use the `sanitize_log_value()` function to sanitize any user-controlled data before logging:

```python
from src.utils.log_sanitizer import sanitize_log_value

# Sanitize environment variables
env = os.getenv("ENV", "production")
logger.warning(
    f"Unknown environment '{sanitize_log_value(env, max_length=50)}', "
    f"defaulting to 'production'"
)

# Sanitize user input
user_input = request.form.get("username")
logger.info(f"Login attempt for user: {sanitize_log_value(user_input)}")
```

### How It Works

The `sanitize_log_value()` function:

1. **Removes control characters**: NULL bytes, backspace, delete, etc.
2. **Removes ANSI escape sequences**: Color codes like `\x1b[31m`
3. **Removes newlines**: Both Unix (`\n`) and Windows (`\r\n`) style
4. **Truncates long values**: Limits output to `max_length` (default: 100 characters)
5. **Handles None/empty values**: Returns safe string representations

**Example:**

```python
# Malicious input with ANSI and newline injection
malicious = "\x1b[31mERROR\x1b[0m\nFAKE: Database deleted"

# Sanitized output
sanitized = sanitize_log_value(malicious)
# Result: "ERRORFAKE: Database deleted"
```

### Best Practices

1. **Always sanitize user input before logging** - Any value from external sources should be sanitized
2. **Set appropriate max_length** - Use shorter limits for values like usernames (50), longer for messages (200)
3. **Preserve Unicode characters** - Normal Unicode (Turkish, emoji, etc.) is safely preserved
4. **Use for all untrusted sources** - Environment variables, HTTP headers, form data, API responses

### What Gets Sanitized

The sanitizer removes these patterns (regex):
```
\x1b\[[0-9;]*[a-zA-Z]  # ANSI escape sequences
\r?\n                  # Newlines (Unix and Windows)
[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]  # Control characters
```

### What's NOT Sanitized

- Normal text and spaces
- Unicode characters (Turkish: ğüşıöç, emoji: 🎉, etc.)
- Punctuation and special characters (!, @, #, etc.)

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

#### `SecureKeyContext` Context Manager

Handles encryption keys securely in memory. This context manager converts the key string to a mutable bytearray immediately and zeroes it on exit, minimizing the window during which the key exists in cleartext memory:

```python
from src.utils.secure_memory import SecureKeyContext
import os

# Secure handling of encryption keys
with SecureKeyContext(os.getenv("SECRET_KEY")) as key_bytes:
    # key_bytes is a bytearray — use it for crypto operations
    cipher = AES.new(bytes(key_bytes), AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(data, AES.block_size))
# key_bytes is now zeroed in memory
```

**Security Guarantees:**
- Key is converted to mutable bytearray immediately
- String reference is cleared to allow garbage collection
- Memory is zeroed using `ctypes.memset` on context exit
- Cleanup happens even if an exception occurs

**IMPORTANT Python Limitations:**

Due to Python language constraints, the original immutable string returned by `os.getenv()` cannot be zeroed and remains in memory until the garbage collector reclaims it. For maximum security in production:

```bash
# Disable core dumps to prevent key exposure in crash dumps
ulimit -c 0

# Or use systemd service configuration
[Service]
LimitCORE=0
```

### Best Practices

1. **Use context managers** for sensitive data (SecureCVV, SecureKeyContext)
2. **Never log sensitive data** - Use sanitized versions (see [Log Sanitization](#log-sanitization))
3. **Clear memory immediately** after use
4. **Use secure_zero_memory** for bytearray/bytes cleanup
5. **Disable core dumps** in production environments
6. **Handle keys early** - Use SecureKeyContext immediately after reading environment variables

---

## Alert System

### Multi-Channel Alerts

The alert service supports multiple notification channels:

- **LOG** - Always available, logs to application logs
- **TELEGRAM** - Send alerts to Telegram bot
- **WEBHOOK** - POST alerts to custom webhook

### Configuration

```python
from src.services.notification.alert_service import (
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
from src.services.notification.alert_service import send_critical_alert

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

1. **Use encrypted connections** for remote PostgreSQL databases (TLS/SSL)
2. **Limit connection pool size** - Prevents resource exhaustion (configure via `DB_POOL_SIZE`)
3. **Set query timeouts** - Prevents long-running queries
4. **Regular backups** - Use `pg_dump` for PostgreSQL backups, automated and tested
5. **Connection security** - Use strong passwords in `DATABASE_URL` and restrict network access

#### Multi-Worker Database Pool Configuration

⚠️ **CRITICAL**: When running multiple workers/instances of the bot, the total number of database connections can exceed PostgreSQL's `max_connections` limit.

**Problem**: If each worker creates a pool of 20 connections and you run 4 workers, that's 80 connections total (plus admin connections).

**Solution**: Set environment variables to control per-worker pool size:

```bash
# Example: PostgreSQL max_connections = 100
DB_MAX_CONNECTIONS=100  # PostgreSQL max_connections setting
DB_WORKER_COUNT=4        # Number of bot workers running

# Result: Each worker gets ~20 connections (100 * 0.8 / 4)
# The 0.8 factor reserves 20% for admin/superuser connections
```

The bot automatically calculates: `pool_size = min(DB_MAX_CONNECTIONS * 0.8 / DB_WORKER_COUNT, 20)`

If these variables are not set, the bot uses CPU-based calculation (may cause issues with multiple workers).

### Redis Security

1. **Always use password authentication** - Set `REDIS_PASSWORD` environment variable
2. **Bind to localhost only** - In `docker-compose.yml`, use `127.0.0.1:6379:6379`
3. **Use encrypted connections** - Configure Redis TLS/SSL for production
4. **Disable dangerous commands** - Use `rename-command` in redis.conf

#### Docker Compose Redis Configuration

When using Docker Compose, Redis password is **required**:

```yaml
redis:
  command: redis-server --requirepass ${REDIS_PASSWORD:?}
```

Set in `.env` file:
```bash
# Generate secure password
REDIS_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(24))")
```

The `REDIS_URL` must include the password:
```bash
REDIS_URL=redis://:your-password@redis:6379/0
```

### Docker Security

1. **Use non-root user** in containers
2. **Scan images** for vulnerabilities
3. **Use specific versions** - Avoid `latest` tag
4. **Minimize image size** - Fewer attack surfaces

### Network Security

1. **Use HTTPS only** in production - `HTTPSRedirectMiddleware` automatically redirects HTTP→HTTPS in production mode
2. **Configure firewall rules** - Whitelist only required ports
3. **Use VPN/private networks** for database access
4. **Enable rate limiting** - Configured in `RateLimits` class

### Logging

1. **Never log sensitive data** - passwords, API keys, CVV, etc.
2. **Use structured logging** - JSON format preferred
3. **Rotate logs regularly** - Prevent disk space issues
4. **Monitor logs** for security events

### Dependency Management

1. **Keep dependencies updated** - `pip install -U -e ".[dev]"` or `pip install -U .`
2. **Use security scanners** - `pip-audit`, `safety`
3. **Pin versions** in `pyproject.toml`
4. **Review security advisories** - Check GitHub Security tab

### Code Security

1. **Input validation** - Validate all user inputs
2. **Output encoding** - Prevent XSS attacks
3. **SQL parameterization** - Use PostgreSQL parameterized queries ($1, $2, etc.)
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
- [ ] Configure alert service (Telegram/Webhook)
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
