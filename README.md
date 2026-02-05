# 🤖 VFS-Bot - Automated VFS Appointment Booking

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Playwright](https://img.shields.io/badge/automation-Playwright-green.svg)](https://playwright.dev/)
[![CI](https://github.com/akbyhakan/VFS-Bot1/workflows/CI/badge.svg)](https://github.com/akbyhakan/VFS-Bot1/actions)
[![codecov](https://codecov.io/gh/akbyhakan/VFS-Bot1/branch/main/graph/badge.svg)](https://codecov.io/gh/akbyhakan/VFS-Bot1)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)

An advanced, modern automated bot for checking and booking VFS Global visa appointment slots. Built with **Python 3.12+**, **Playwright**, and **FastAPI** for a robust, efficient, and user-friendly experience.

## ✨ Features

- 🎯 **Automated Slot Checking** - Continuously monitors available appointment slots
- 🚀 **Playwright Automation** - Faster and more reliable than Selenium with stealth mode
- 📊 **Web Dashboard** - Real-time monitoring and control via browser
- 🔔 **Multi-Channel Notifications** - Telegram and Email alerts
- 🧩 **Multiple Captcha Solvers** - Support for 2captcha, anticaptcha, nopecha, and manual solving
- 👥 **Multi-User Support** - Handle multiple users and centres simultaneously
- 🗄️ **SQLite Database** - Track users, appointments, and logs
- 🐳 **Docker Support** - Easy deployment with Docker and Docker Compose
- ⚙️ **YAML Configuration** - Simple configuration with environment variable support
- 🔒 **Secure** - Credentials stored in environment variables

## 🛡️ Anti-Detection Features

### TLS Fingerprinting Bypass
- Uses curl-cffi to mimic real Chrome TLS handshake
- Bypasses JA3 fingerprint detection
- Playwright stealth mode enabled

### Browser Fingerprinting Protection
- **Canvas**: Noise injection to randomize fingerprint
- **WebGL**: Vendor/renderer spoofing
- **Audio Context**: Timing randomization
- **Navigator**: WebDriver flag hidden

### Human Behavior Simulation
- **Mouse**: Bézier curve movements (15-30 steps)
- **Typing**: Variable speed (40-80 WPM)
- **Clicking**: Random delays (0.1-0.5s) and position variance
- **Scrolling**: Natural chunked scrolling

### Cloudflare Bypass
- Automatic Waiting Room handling (max 30s)
- Turnstile challenge support
- Browser check auto-pass
- 403/503 error recovery with exponential backoff

### Session & Token Management
- JWT token auto-capture and refresh
- Session persistence (data/session.json)
- Token expiry prediction (5-min buffer)

### Proxy Support (Optional)
- Multi-proxy rotation from file
- Automatic failover on errors
- Supports http/socks5 with auth

## 🧠 Adaptive Selector Strategy

VFS-Bot uses a multi-layered approach to find elements on the page, making it highly resilient to website changes:

### 1. Semantic Locators (Priority 1)
- Uses Playwright's user-facing locators (role, label, text, placeholder)
- More resilient than CSS selectors (IDs can change, but button text rarely does)
- Multi-language support (Turkish/English)
- Example: Finding login button by role="button" and text="Giriş Yap"

### 2. Adaptive Learning (Priority 2)
- Automatically tracks which selectors succeed/fail
- Auto-promotes fallback selectors after 5 consecutive successes
- Demotes primary selectors after 3 consecutive failures
- Reorders selectors based on performance data
- Metrics stored in `data/selector_metrics.json`

### 3. CSS Selectors (Priority 3)
- Traditional CSS selectors with primary/fallback system
- Multiple fallback options for each element
- Optimized order based on learning system

### 4. AI Auto-Repair (Optional)
- LLM-powered selector recovery using Google Gemini
- Activates when all selectors fail
- Auto-updates `config/selectors.yaml` with successful suggestions
- Graceful degradation when API key not provided

### Configuration

#### Enable AI Auto-Repair
```bash
# Get API key from: https://ai.google.dev/
export GEMINI_API_KEY="your_api_key"
```

#### View Selector Performance
```bash
cat data/selector_metrics.json
```

### How It Works

When a selector fails:
1. ✅ Try semantic locators (role, label, text)
2. ✅ Try CSS selectors in optimized order (learning-based)
3. 🤖 If all fail, ask Gemini AI to find new selector
4. 💾 Auto-update config and continue

The system learns over time which selectors work best and automatically promotes them, reducing timeout delays and improving reliability.

## 📋 Requirements

- Python 3.12 or higher
- Modern web browser (Chromium installed automatically by Playwright)
- Internet connection
- VFS Global account

## 🚀 Quick Start

### Option 1: Using pip (Local Installation)

1. **Clone the repository**
   ```bash
   git clone https://github.com/akbyhakan/VFS-Bot1.git
   cd VFS-Bot1
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

4. **Configure the bot**
   ```bash
   cp config/config.example.yaml config/config.yaml
   cp .env.example .env
   ```
   
   Edit `config/config.yaml` and `.env` with your details.

5. **Run the bot**
   ```bash
   # Run with web dashboard (recommended)
   python main.py --mode web
   
   # Run in automated mode only
   python main.py --mode bot
   
   # Run both
   python main.py --mode both
   ```

6. **Access the dashboard**
   
   Open your browser and navigate to: `http://localhost:8000`

### Option 2: Using Docker

1. **Clone and configure**
   ```bash
   git clone https://github.com/akbyhakan/VFS-Bot1.git
   cd VFS-Bot1
   cp .env.example .env
   ```
   
   Edit `.env` with your credentials.

2. **Run with Docker Compose**
   ```bash
   docker-compose up -d
   ```

3. **Access the dashboard**
   
   Open your browser: `http://localhost:8000`

4. **View logs**
   ```bash
   docker-compose logs -f vfs-bot
   ```

## ⚙️ Configuration

### 🔐 Security Best Practices

**IMPORTANT:** Follow these security guidelines before deploying:

1. **Encryption Keys:**
   - Generate a secure `ENCRYPTION_KEY` for password encryption:
     ```bash
     python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
     ```
   - Generate a secure `VFS_ENCRYPTION_KEY` for VFS API authentication:
     ```bash
     python -c "import secrets; print(secrets.token_urlsafe(32))"
     ```
   - **Never** commit encryption keys to version control
   - Store keys securely in environment variables or secret managers

2. **API Keys & Secrets:**
   - Generate a strong `API_SECRET_KEY` (minimum 32 characters):
     ```bash
     python -c "import secrets; print(secrets.token_urlsafe(32))"
     ```
   - Change default `ADMIN_PASSWORD` immediately
   - Use hashed passwords for production deployments

3. **Environment Variables:**
   - Always use `.env` files (included in `.gitignore`)
   - Never hardcode sensitive data in source code
   - Use different keys for development and production

4. **Database Security:**
   - Configure `DB_POOL_SIZE` based on your workload (default: 10)
   - Regularly backup your database
   - Passwords are encrypted, not hashed (required for VFS authentication)

5. **Token Management:**
   - Tokens auto-refresh with `TOKEN_REFRESH_BUFFER_MINUTES` (default: 5 minutes)
   - Sessions expire and refresh automatically
   - Invalid sessions trigger re-authentication

### Environment Variables (.env)

```env
# VFS Credentials
VFS_EMAIL=your_email@example.com
VFS_PASSWORD=your_password

# Password Encryption Key (CRITICAL)
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your-base64-encoded-encryption-key-here

# VFS API Encryption Key (CRITICAL)
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
VFS_ENCRYPTION_KEY=your-32-byte-encryption-key-here

# Database Configuration
DB_POOL_SIZE=10

# Token Management
TOKEN_REFRESH_BUFFER_MINUTES=5

# Telegram Notifications (optional)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Email Notifications (optional)
EMAIL_SENDER=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_RECEIVER=receiver@example.com

# Captcha Service (optional)
CAPTCHA_API_KEY=your_captcha_api_key
```

### Configuration File (config/config.yaml)

```yaml
vfs:
  base_url: "https://visa.vfsglobal.com"
  country: "tur"  # Country code
  mission: "deu"  # Mission code
  centres:
    - "Istanbul"
    - "Ankara"
  category: "Schengen Visa"
  subcategory: "Tourism"

bot:
  check_interval: 30  # Seconds between checks
  headless: false     # Run browser in background
  screenshot_on_error: true
  max_retries: 3

captcha:
  provider: "manual"  # Options: 2captcha, anticaptcha, nopecha, manual
  manual_timeout: 120

notifications:
  telegram:
    enabled: true
  email:
    enabled: false

anti_detection:
  enabled: true  # Master switch
  tls_bypass: true
  fingerprint_bypass: true
  human_simulation: true

cloudflare:
  enabled: true
  max_wait_time: 30  # seconds
  
proxy:
  enabled: false  # Set true to use proxies
  file: "config/proxies.txt"
```

All anti-detection features are configurable via `config/config.yaml`:

```yaml
anti_detection:
  enabled: true  # Master switch
  tls_bypass: true
  fingerprint_bypass: true
  human_simulation: true
  stealth_mode: true

cloudflare:
  enabled: true
  max_wait_time: 30
  max_retries: 3
  manual_captcha: false

proxy:
  enabled: false
  file: "config/proxies.txt"
  rotate_on_error: true

human_behavior:
  mouse_movement_steps: 20
  typing_wpm_range: [40, 80]
  click_delay_range: [0.1, 0.5]
  random_actions: true

session:
  save_file: "data/session.json"
  token_refresh_buffer: 5
```

### User CSV Upload Format

When uploading users via CSV, use the following format:

| Column | Required | Description |
|--------|----------|-------------|
| email | Yes | VFS account email |
| password | Yes | VFS account password |
| phone | Yes | Phone number for notifications |

Example CSV structure:
```csv
email,password,phone
your-email@example.com,your-password,5551234567
```

**Important Security Notes:**
- Never commit CSV files with real credentials to version control
- Passwords are automatically encrypted when imported
- Keep your CSV files in a secure location
- Delete CSV files after importing users

## 📊 Web Dashboard

The web dashboard provides:

- **Real-time Status** - See bot running status
- **Statistics** - Slots found, appointments booked
- **Live Logs** - Monitor bot activity in real-time
- **Controls** - Start/Stop bot with one click

## 🔧 Usage Examples

### Using the Command Line

```bash
# Run with web dashboard on custom port
python main.py --mode web

# Run in bot-only mode with debug logging
python main.py --mode bot --log-level DEBUG

# Use custom config file
python main.py --config /path/to/config.yaml
```

### Using the API

The web dashboard exposes a REST API:

- `GET /api/status` - Get current bot status
- `POST /api/bot/start` - Start the bot
- `POST /api/bot/stop` - Stop the bot
- `GET /api/logs` - Get recent logs
- `WebSocket /ws` - Real-time updates

Example:
```bash
# Get status
curl http://localhost:8000/api/status

# Start bot
curl -X POST http://localhost:8000/api/bot/start

# Stop bot
curl -X POST http://localhost:8000/api/bot/stop
```

## 🏥 Health & Monitoring

### Health Check
The web dashboard exposes a health check endpoint for container orchestration:

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2026-01-09T15:30:00Z",
  "version": "2.0.0",
  "components": {
    "database": true,
    "bot": true,
    "notifications": true
  }
}
```

### Metrics
Monitor bot performance via metrics endpoint:

```bash
curl http://localhost:8000/metrics
```

### Structured Logging
Enable JSON logging for production:

```bash
export JSON_LOGGING=true
python main.py
```

Logs are written to `logs/vfs_bot.jsonl` in JSON format for easy parsing.

### Rate Limiting
Global rate limiting prevents overloading VFS servers:
- Default: 60 requests per 60 seconds
- Automatic backoff when limit reached
- Configurable via `RateLimiter` class
```

## 🧪 Testing

Run the test suite:

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_bot.py -v
```

## 📁 Project Structure

```
VFS-Bot1/
├── src/
│   ├── core/                 # Core modules
│   │   ├── config_loader.py  # YAML config loader
│   │   ├── config_validator.py
│   │   ├── env_validator.py  # Environment validation
│   │   ├── logger.py         # Structured logging (Loguru)
│   │   ├── monitoring.py     # Sentry integration
│   │   └── exceptions.py
│   ├── models/               # Data models
│   │   └── database.py       # SQLite operations
│   ├── services/             # Business logic
│   │   ├── bot/              # Main bot logic (modular)
│   │   ├── captcha_solver.py # Captcha solving
│   │   ├── centre_fetcher.py # Auto-fetch centres
│   │   └── notification.py   # Telegram & Email
│   ├── utils/                # Utilities
│   ├── middleware/           # Middleware components
│   └── repositories/         # Data repositories
├── web/                      # Web dashboard
│   ├── app.py               # FastAPI application
│   ├── static/              # CSS, JavaScript
│   └── templates/           # HTML templates
├── config/                   # Configuration files
├── tests/                    # Test suite
├── logs/                     # Log files (gitignored)
├── screenshots/             # Screenshots (gitignored)
├── docs/                    # Documentation
├── scripts/                 # Helper scripts
├── main.py                  # Entry point
├── requirements.txt         # Python dependencies
├── Dockerfile               # Docker configuration
└── docker-compose.yml       # Docker Compose setup
```

## 💳 Payment Security (PCI-DSS Compliant)

### What We Store:
- ✅ Card holder name (plain text)
- ✅ Card number (Fernet encrypted)
- ✅ Expiry date (plain text)

### What We DO NOT Store (PCI-DSS Requirement):
- ❌ CVV/CVC (never stored, requested at payment time)
- ❌ PIN code
- ❌ Magnetic stripe data

### Payment Flow:
1. Save card via dashboard (no CVV)
2. Bot finds appointment
3. CVV requested (SMS/Email/Dashboard)
4. CVV used in-memory only
5. CVV cleared after payment

---

## 📊 Monitoring

### Sentry Setup:

```bash
# Add to .env
SENTRY_DSN=https://your-key@sentry.io/project
SENTRY_TRACES_SAMPLE_RATE=0.1
```

Features:
- Automatic error capturing
- Performance monitoring (10% sample)
- Sensitive data filtering (CVV, passwords)
- Screenshot attachments

---

## 🔐 Security Best Practices

1. **Never commit credentials** - Use `.env` file (gitignored)
2. **Use app passwords** - For Gmail, generate an app-specific password
3. **Secure your API keys** - Don't share captcha API keys
4. **Run in Docker** - Isolate the bot environment
5. **Update regularly** - Keep dependencies up to date

## 🔒 Security Best Practices

### Password Encryption

VFS-Bot v2.1.0+ uses **Fernet symmetric encryption** for storing VFS account passwords. This is critical because:

- ❌ **Hashing doesn't work** - The bot needs the actual password to log into VFS
- ✅ **Encryption is secure** - Passwords are encrypted at rest with AES-128 in CBC mode
- 🔑 **Key management** - The encryption key must be kept secure

#### Generating an Encryption Key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Add the generated key to your `.env` file:

```env
ENCRYPTION_KEY=your-generated-key-here
```

#### Key Security Guidelines

- ⚠️ **Never commit** the encryption key to version control
- 🔒 **Rotate keys** periodically (requires re-encrypting all passwords)
- 💾 **Backup safely** - Store the key in a secure password manager or vault
- 🏢 **Production** - Use environment variables or secrets management (AWS Secrets Manager, Azure Key Vault, etc.)

### Environment Variable Validation

The bot validates all required environment variables on startup with enhanced security checks:

#### Required Variables:
- **VFS_EMAIL** - Must be a valid email address format
- **VFS_PASSWORD** - Must be at least 8 characters
- **ENCRYPTION_KEY** - Must be a valid 44-character Fernet key

#### Optional Variables (with validation):
- **API_SECRET_KEY** - JWT secret key (minimum 32 characters for security)
- **VFS_ENCRYPTION_KEY** - VFS API encryption key (minimum 32 bytes for AES-256)
- **ADMIN_PASSWORD** - Must be bcrypt hashed in production (starts with `$2b$`)
- **SMS_WEBHOOK_SECRET** - Webhook signature secret (minimum 32 characters)
- **CAPTCHA_API_KEY** - Minimum 16 characters

#### Validation Features:
- **Format validation** - Email, encryption keys checked for proper format
- **Security requirements** - Password strength, key length enforced
- **Production mode** - Stricter validation in production environment
- **Error messages** - Clear instructions for fixing validation errors

If validation fails in strict mode, the bot will not start.

### Database Security

- **Connection pooling** - Prevents race conditions with concurrent operations
- **Encrypted passwords** - All VFS passwords are encrypted before storage
- **SQL injection protection** - Uses parameterized queries throughout
- **Thread-safe operations** - Connection pool with proper resource management
- **Persistent storage** - User data persists across server restarts

### 💳 Payment Card Security (PCI-DSS Compliant)

VFS-Bot implements **PCI-DSS Level 1** compliant payment card storage:

#### What is Stored:
- ✅ **Card holder name** (plain text - not sensitive per PCI-DSS)
- ✅ **Card number** (Fernet encrypted with AES-128)
- ✅ **Expiry date** (plain text - not sensitive per PCI-DSS)

#### What is NOT Stored:
- ❌ **CVV/CVC** (PCI-DSS violation to store CVV - NEVER stored)
- ❌ **3D Secure OTP codes** (one-time use only)

#### Payment Flow:
1. Save card details (without CVV) via dashboard
2. When payment is needed, CVV must be entered at transaction time
3. CVV is used only in-memory for the transaction
4. CVV is immediately cleared after payment completion

#### Security Features:
- **No CVV persistence** - CVV never touches disk storage
- **Encrypted card numbers** - AES-128 encryption at rest
- **TLS 1.2+** - All network communication is encrypted
- **Webhook signature validation** - SMS OTP webhooks are cryptographically verified
- **Runtime CVV input** - CVV requested only when needed for payment

#### 3D Secure Support:
- OTP codes received via SMS webhook
- Automatically entered during payment
- Configurable timeout (default 120 seconds)
- Secure webhook signature validation

⚠️ **Production Note**: For full PCI-DSS compliance in production, consider:
- External PCI audit (required for Level 1 compliance)
- Hardware Security Module (HSM) for key storage
- Payment gateway tokenization
- Network segmentation
- Regular security audits

### Rate Limiting

- **Global rate limiter** - 60 requests per 60 seconds (default)
- **Per-endpoint limits** - Web API endpoints have additional rate limits
- **Circuit breaker** - Prevents infinite error loops

## 🧪 Testing

VFS-Bot includes a comprehensive test suite with >70% code coverage.

### Running Tests

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with coverage report
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_encryption.py

# Run tests matching pattern
pytest -k "test_encrypt"

# Run only unit tests
pytest -m unit

# Run with verbose output
pytest -v
```

### Test Coverage

```bash
# Generate coverage report
pytest --cov=src --cov-report=term-missing

# View HTML coverage report
pytest --cov=src --cov-report=html
open htmlcov/index.html  # macOS/Linux
start htmlcov/index.html  # Windows
```

### Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_database.py         # Database with encryption tests
├── test_encryption.py       # Password encryption tests
├── test_validators.py       # Environment validation tests
├── test_bot.py             # Bot logic tests
├── test_rate_limiter.py    # Rate limiting tests
└── ...
```

### Writing Tests

```python
import pytest
from src.models.database import Database

@pytest.mark.asyncio
async def test_add_user(test_db):
    """Test adding a user with encrypted password."""
    user_id = await test_db.add_user(
        email="test@example.com",
        password="secure_password",
        centre="Istanbul",
        category="Tourism",
        subcategory="Short Stay"
    )
    assert user_id > 0
```

## 📊 Monitoring & Metrics

VFS-Bot v2.1.0 includes comprehensive metrics tracking and monitoring.

### Metrics Endpoints

#### `/api/metrics` - Detailed Metrics

```bash
curl http://localhost:8000/api/metrics
```

Response:
```json
{
  "current": {
    "timestamp": "2025-01-12T02:00:00Z",
    "uptime_seconds": 3600.5,
    "total_checks": 120,
    "slots_found": 5,
    "appointments_booked": 2,
    "total_errors": 3,
    "success_rate": 97.5,
    "requests_per_minute": 2.0,
    "avg_response_time_ms": 1250.5,
    "circuit_breaker_trips": 0,
    "active_users": 5
  },
  "status": "running",
  "errors": {
    "by_type": {"LoginError": 2, "NetworkError": 1},
    "by_user": {"1": 1, "2": 2}
  }
}
```

#### `/metrics/prometheus` - Prometheus Format

```bash
curl http://localhost:8000/metrics/prometheus
```

Response (Prometheus text format):
```
# HELP vfs_bot_uptime_seconds Bot uptime in seconds
# TYPE vfs_bot_uptime_seconds gauge
vfs_bot_uptime_seconds 3600.5

# HELP vfs_bot_checks_total Total slot checks performed
# TYPE vfs_bot_checks_total counter
vfs_bot_checks_total 120
...
```

#### `/health` - Enhanced Health Check

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2025-01-12T02:00:00Z",
  "version": "2.1.0",
  "uptime_seconds": 3600.5,
  "components": {
    "database": {"status": "healthy"},
    "bot": {
      "status": "healthy",
      "running": true,
      "success_rate": 97.5
    },
    "circuit_breaker": {
      "status": "healthy",
      "trips": 0
    },
    "notifications": {"status": "healthy"}
  },
  "metrics": {
    "total_checks": 120,
    "slots_found": 5,
    "appointments_booked": 2,
    "active_users": 5
  }
}
```

### Prometheus Integration

Add to `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'vfs-bot'
    scrape_interval: 30s
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics/prometheus'
```

### Grafana Dashboard

Import metrics into Grafana:

1. Add Prometheus as data source
2. Create dashboard with panels for:
   - Uptime and success rate
   - Slots found vs. appointments booked
   - Circuit breaker trips
   - Error rates by type
   - Response time trends

### Circuit Breaker Monitoring

The circuit breaker prevents infinite error loops:

- **Opens when:**
  - 5 consecutive errors, OR
  - 20 total errors in 1 hour
- **Exponential backoff:**
  - Wait time: `min(60 * 2^(errors-1), 600)` seconds
  - Max wait: 10 minutes
- **Auto-recovery:**
  - Circuit closes after successful operation

Monitor via `/health` endpoint - status will be "degraded" when circuit is open.

## 🔄 Migration Guide (v2.0.0 → v2.1.0)

### Breaking Changes

1. **Password Storage** - Passwords are now encrypted instead of hashed

### Migration Steps

1. **Update dependencies:**

```bash
pip install -r requirements.txt --upgrade
```

2. **Generate encryption key:**

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

3. **Add to `.env`:**

```env
ENCRYPTION_KEY=<generated-key>
```

4. **Re-add users** - Existing users must be re-registered:

```python
# The old hashed passwords cannot be decrypted
# Users need to update their passwords through the dashboard
# Or use a migration script (see below)
```

5. **Optional: Migration script for existing users:**

If you have users and know their original passwords:

```python
import asyncio
from src.models.database import Database
from src.utils.encryption import encrypt_password

async def migrate_user(db, user_id, plaintext_password):
    """Migrate a single user to encrypted password."""
    encrypted = encrypt_password(plaintext_password)
    # Update user password directly
    async with db.conn.cursor() as cursor:
        await cursor.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (encrypted, user_id)
        )
    await db.conn.commit()

# Run migration
async def main():
    db = Database()
    await db.connect()
    # Update each user with their original password
    await migrate_user(db, user_id=1, plaintext_password="original_password")
    await db.close()

asyncio.run(main())
```

⚠️ **Important:** Without the original plaintext passwords, users must re-register.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

```
MIT License

Copyright (c) 2025 akbyhakan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

## 📧 Contact & Support

- **Author**: akbyhakan
- **GitHub**: [akbyhakan/VFS-Bot1](https://github.com/akbyhakan/VFS-Bot1)
- **Issues**: [Report a bug](https://github.com/akbyhakan/VFS-Bot1/issues)

## ⚠️ Disclaimer

This bot is for educational purposes only. Use at your own risk. The authors are not responsible for any misuse or damage caused by this program. Always comply with VFS Global's terms of service.

## 🙏 Acknowledgments

- [Playwright](https://playwright.dev/) - Modern browser automation
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram API wrapper

---

**Star ⭐ this repository if you find it helpful!**
