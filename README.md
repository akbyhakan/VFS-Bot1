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
- 🧩 **Captcha Solver** - Integrated 2Captcha support for automated solving
- 👥 **Multi-User Support** - Handle multiple users and centres simultaneously
- 🗄️ **PostgreSQL Database** - Scalable, production-ready database with connection pooling
- 🐳 **Docker Support** - Easy deployment with Docker and Docker Compose
- ⚙️ **YAML Configuration** - Simple configuration with environment variable support
- 🔒 **Secure** - Credentials stored in environment variables
- 🏦 **Account Pool** - Multi-account VFS pool with cooldown/quarantine management
- 📱 **OTP Manager** - Centralized OTP management (Email IMAP + SMS Webhook support)
- 📨 **SMS Webhook** - SMS Forwarder app integration for OTP retrieval
- 📧 **Email OTP** - Microsoft 365 catch-all mailbox for OTP retrieval
- 🔄 **Dropdown Sync** - Automatic synchronization of VFS dropdown data (weekly)
- 🛡️ **Appointment Deduplication** - Prevents duplicate appointment bookings
- 💳 **Payment Service** - Payment processing support (manual mode)
- ⚙️ **Runtime Config API** - Runtime configuration management API
- 📋 **Audit Logging** - Detailed audit trail and logging
- 🌐 **Proxy Management** - Dashboard-based proxy addition and management
- 🔑 **API Versioning** - Versioned API with `/api/v1/` prefix
- 📊 **Grafana/Prometheus Monitoring** - Integrated monitoring via `docker-compose.monitoring.yml`
- 🗄️ **Alembic Migrations** - Database schema migrations
- 📈 **Slot Pattern Analysis** - Availability pattern analysis

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
- LLM-powered selector recovery using Google GenAI SDK
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
3. 🤖 If all fail, ask Gemini AI (gemini-2.5-flash) to find new selector
4. 💾 Auto-update config and continue

The system learns over time which selectors work best and automatically promotes them, reducing timeout delays and improving reliability.

## 📋 Requirements

- Python 3.12 or higher
- **PostgreSQL 16+** (or 9.6+ minimum for basic features)
- Modern web browser (Chromium installed automatically by Playwright)
- Internet connection
- VFS Global account

## 🚀 Quick Start

### Option 1: Using pip (Local Installation)

1. **Install PostgreSQL**
   ```bash
   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install postgresql postgresql-contrib
   
   # macOS
   brew install postgresql@16
   
   # Start PostgreSQL service
   sudo systemctl start postgresql  # Linux
   brew services start postgresql@16  # macOS
   ```

2. **Create database**
   ```bash
   # Create user and database
   sudo -u postgres psql
   -- ⚠️ CRITICAL: Replace with a secure password before deploying!
   -- Generate with: python -c "import secrets; print(secrets.token_urlsafe(24))"
   CREATE USER vfs_bot WITH PASSWORD 'CHANGE_ME_TO_SECURE_PASSWORD';
   CREATE DATABASE vfs_bot OWNER vfs_bot;
   GRANT ALL PRIVILEGES ON DATABASE vfs_bot TO vfs_bot;
   \q
   ```

3. **Clone the repository**
   ```bash
   git clone https://github.com/akbyhakan/VFS-Bot1.git
   cd VFS-Bot1
   ```

4. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

5. **Install dependencies**
   ```bash
   pip install -e ".[dev]"
   playwright install chromium
   ```

6. **Configure the bot**
   ```bash
   cp config/config.example.yaml config/config.yaml
   cp .env.example .env
   ```
   
   Edit `config/config.yaml` and `.env` with your details.

7. **Run the bot**
   ```bash
   # Run with web dashboard (recommended)
   python main.py --mode web
   
   # Run in automated mode only
   python main.py --mode bot
   
   # Run both
   python main.py --mode both
   ```

8. **Access the dashboard**
   
   Open your browser and navigate to: `http://localhost:8000`

### Option 2: Using Docker

**Note:** Docker Compose automatically sets up PostgreSQL and Redis for you.

1. **Clone and configure**
   ```bash
   git clone https://github.com/akbyhakan/VFS-Bot1.git
   cd VFS-Bot1
   cp .env.example .env
   ```
   
   Edit `.env` with your credentials. **Important**: Set both `POSTGRES_PASSWORD` and `REDIS_PASSWORD` for security.
   
   ```bash
   # Generate secure passwords
   echo "POSTGRES_PASSWORD=$(python -c 'import secrets; print(secrets.token_urlsafe(24))')" >> .env
   echo "REDIS_PASSWORD=$(python -c 'import secrets; print(secrets.token_urlsafe(24))')" >> .env
   ```

2. **Run with Docker Compose**
   ```bash
   docker-compose up -d
   ```
   
   This will start:
   - PostgreSQL database server (with password authentication)
   - Redis server (with password authentication)
   - VFS-Bot application

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
   - Set `DATABASE_URL` to point to your PostgreSQL instance
   - Configure `DB_POOL_SIZE` based on your workload (default: 10)
   - Regularly backup your database using `pg_dump`
   - Passwords are encrypted, not hashed (required for VFS authentication)

5. **Token Management:**
   - Tokens auto-refresh with `TOKEN_REFRESH_BUFFER_MINUTES` (default: 5 minutes)
   - Sessions expire and refresh automatically
   - Invalid sessions trigger re-authentication

### Environment Variables (.env)

Key variables needed for configuration (see `.env.example` for complete list):

```env
# VFS Credentials
VFS_EMAIL=your_email@example.com
VFS_PASSWORD=your_password
VFS_PASSWORD_ENCRYPTED=false  # Set to true if password is Fernet-encrypted

# Encryption Keys (CRITICAL)
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your-base64-encoded-encryption-key-here
# Backup encryption key (uses ENCRYPTION_KEY if not set)
BACKUP_ENCRYPTION_KEY=your-backup-encryption-key

# VFS API Encryption Key (CRITICAL)
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
VFS_ENCRYPTION_KEY=your-32-byte-encryption-key-here

# VFS API URLs (REQUIRED)
VFS_API_BASE=https://your-vfs-api-base-url
VFS_ASSETS_BASE=https://your-vfs-assets-base-url
CONTENTFUL_BASE=https://your-contentful-base-url

# Database Configuration
# PostgreSQL connection URL
# ⚠️ CRITICAL: Replace CHANGE_ME_TO_SECURE_PASSWORD with a secure password!
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(24))"
DATABASE_URL=postgresql://vfs_bot:CHANGE_ME_TO_SECURE_PASSWORD@localhost:5432/vfs_bot
POSTGRES_PASSWORD=CHANGE_ME_TO_SECURE_PASSWORD
DB_POOL_SIZE=10
DB_CONNECTION_TIMEOUT=30.0
# Multi-worker configuration
DB_MAX_CONNECTIONS=100
DB_WORKER_COUNT=4

# Backup Configuration
BACKUP_INTERVAL_HOURS=6
BACKUP_RETENTION_DAYS=7

# Token Management
TOKEN_REFRESH_BUFFER_MINUTES=5

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=text  # text or json

# Environment
ENV=production  # production or development

# Telegram Notifications (optional)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Email Notifications (optional)
EMAIL_SENDER=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_RECEIVER=receiver@example.com

# Captcha Service (optional)
CAPTCHA_API_KEY=your_captcha_api_key

# SMS OTP Webhook
SMS_WEBHOOK_SECRET=your-webhook-secret
OTP_TIMEOUT_SECONDS=300

# Microsoft 365 Email OTP
M365_EMAIL=admin@yourdomain.com
M365_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx

# OTP Manager (Centralized)
OTP_MANAGER_EMAIL=your-catchall-email@yourdomain.com
OTP_MANAGER_APP_PASSWORD=your-app-specific-password
OTP_MANAGER_TIMEOUT=120
OTP_MANAGER_SESSION_TIMEOUT=600

# SMS Webhook Token
WEBHOOK_BASE_URL=https://your-api-domain.example.com
WEBHOOK_TOKEN_PREFIX=tk_
WEBHOOK_RATE_LIMIT=60
WEBHOOK_SIGNATURE_SECRET=

# Dashboard Security
DASHBOARD_API_KEY=your-secure-api-key-here
ADMIN_SECRET=one-time-secret-for-key-generation

# API Authentication (JWT)
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(48))"
API_SECRET_KEY=your-secret-key-here-must-be-at-least-64-characters-long
JWT_ALGORITHM=HS384
JWT_EXPIRY_HOURS=24

# Admin Credentials
ADMIN_USERNAME=your_unique_admin_name
ADMIN_PASSWORD=YOUR_SECURE_HASHED_PASSWORD_HERE

# API Key Auth (alternative to JWT)
API_KEY=your-api-key-here
API_KEY_SALT=your-32-character-minimum-salt-here
API_KEY_VERSION=1

# Trusted Proxies
TRUSTED_PROXIES=

# Health Check
BOT_HEALTH_THRESHOLD=50.0

# Cache Configuration
USERS_CACHE_TTL=300
CACHE_TTL_SECONDS=3600

# Rate Limiting
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_WINDOW=60
AUTH_RATE_LIMIT_ATTEMPTS=5
AUTH_RATE_LIMIT_WINDOW=60

# Redis (for distributed rate limiting)
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=CHANGE_ME_generate_secure_password_here

# Monitoring (Grafana/Prometheus)
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=CHANGE_ME_generate_secure_grafana_password

# AI-Powered Selector Auto-Repair (optional)
# Get API key from: https://ai.google.dev/
GEMINI_API_KEY=your_gemini_api_key_here
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
  provider: "2captcha"  # Only 2captcha is supported
  api_key: "${CAPTCHA_API_KEY}"

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

The web dashboard exposes a REST API with versioned endpoints:

#### Versioned Endpoints (`/api/v1/`)

**Authentication:**
- `POST /api/v1/auth/login` - User login (creates HttpOnly cookie)
- `POST /api/v1/auth/logout` - User logout (clears HttpOnly cookie)
- `POST /api/v1/auth/refresh` - Refresh JWT token (issues new HttpOnly cookie)
- `POST /api/v1/auth/generate-key` - Generate API key (one-time use)

**VFS Account Management:**
- `GET /api/v1/vfs-accounts` - List all VFS accounts
- `POST /api/v1/vfs-accounts` - Create new VFS account
- `PUT /api/v1/vfs-accounts/{id}` - Update VFS account
- `PATCH /api/v1/vfs-accounts/{id}` - Toggle VFS account active status
- `DELETE /api/v1/vfs-accounts/{id}` - Delete VFS account
- `POST /api/v1/vfs-accounts/import` - Bulk upload VFS accounts from CSV

**Bot Control:**
- `POST /api/v1/bot/start` - Start the bot
- `POST /api/v1/bot/stop` - Stop the bot
- `POST /api/v1/bot/restart` - Restart the bot
- `POST /api/v1/bot/check-now` - Trigger manual check
- `GET /api/v1/bot/logs` - Fetch bot logs
- `GET /api/v1/bot/settings` - Get bot settings
- `PUT /api/v1/bot/settings` - Update bot settings
- `GET /api/v1/bot/selector-health` - Get adaptive selector health status
- `GET /api/v1/bot/errors` - List recent bot errors with captures
- `GET /api/v1/bot/errors/{id}` - Get specific bot error details
- `GET /api/v1/bot/errors/{id}/screenshot` - Get error screenshot capture
- `GET /api/v1/bot/errors/{id}/html-snapshot` - Get error HTML page snapshot

**Appointments:**
- `GET /api/v1/appointments/appointment-requests` - List appointment requests
- `GET /api/v1/appointments/appointment-requests/{id}` - Get specific appointment request
- `POST /api/v1/appointments/appointment-requests` - Create appointment request
- `DELETE /api/v1/appointments/appointment-requests/{id}` - Delete appointment request
- `PATCH /api/v1/appointments/appointment-requests/{id}/status` - Update request status
- `GET /api/v1/appointments/countries` - List available countries
- `GET /api/v1/appointments/countries/{code}/centres` - List centres for country
- `GET /api/v1/appointments/countries/{code}/centres/{name}/categories` - List visa categories
- `GET /api/v1/appointments/countries/{code}/centres/{name}/categories/{cat}/subcategories` - List subcategories

**Audit:**
- `GET /api/v1/audit/logs` - Get audit logs
- `GET /api/v1/audit/stats` - Get audit statistics
- `GET /api/v1/audit/logs/{id}` - Get specific audit log entry

**Payment:**
- `POST /api/v1/payment/payment-card` - Save payment card
- `GET /api/v1/payment/payment-card` - Get payment card
- `DELETE /api/v1/payment/payment-card` - Delete payment card

**Proxy Management:**
- `POST /api/v1/proxy/add` - Add proxy
- `GET /api/v1/proxy/list` - List proxies
- `GET /api/v1/proxy/stats` - Get proxy statistics
- `DELETE /api/v1/proxy/clear-all` - Clear all proxies
- `POST /api/v1/proxy/upload` - Upload proxy file

**Runtime Configuration:**
- `GET /api/v1/config/runtime` - Get runtime configuration
- `PUT /api/v1/config/runtime` - Update runtime configuration

**Dropdown Sync:**
- `POST /api/v1/dropdown-sync/{country_code}` - Trigger dropdown sync for a specific country
- `POST /api/v1/dropdown-sync/all` - Trigger dropdown sync for all countries
- `GET /api/v1/dropdown-sync/status` - Get sync status for all countries
- `GET /api/v1/dropdown-sync/{country_code}/status` - Get sync status for specific country

#### Non-Versioned Endpoints

**Health & Status:**
- `GET /health` - Health check
- `GET /api/status` - Bot status
- `GET /metrics` - Bot metrics (JSON)
- `GET /api/metrics` - Detailed bot metrics
- `GET /metrics/prometheus` - Prometheus text format metrics

**WebSocket:**
- `WS /ws` - Real-time updates (logs, status, stats) — requires authentication via HttpOnly cookie or legacy message-based token

**OTP Webhooks:**
- `POST /api/v1/webhook/users/{user_id}/create` - Create webhook for user
- `GET /api/v1/webhook/users/{user_id}` - Get webhook info
- `POST /webhook/sms/{token}` - SMS OTP receiver endpoint

#### Example Usage

```bash
# Login and get session cookie
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}' \
  -c cookies.txt

# Get bot status (non-versioned endpoint)
curl http://localhost:8000/api/status -b cookies.txt

# Start bot (versioned endpoint)
curl -X POST http://localhost:8000/api/v1/bot/start -b cookies.txt

# Stop bot (versioned endpoint)
curl -X POST http://localhost:8000/api/v1/bot/stop -b cookies.txt

# Get logs (versioned endpoint)
curl http://localhost:8000/api/v1/bot/logs -b cookies.txt
```

## 📁 Project Structure

```
VFS-Bot1/
├── main.py                          # Main entry point (3-phase startup)
├── pyproject.toml                   # Project configuration and dependencies
├── Dockerfile / Dockerfile.dev      # Docker configurations
├── docker-compose.yml               # Production compose
├── docker-compose.dev.yml           # Development compose
├── docker-compose.monitoring.yml    # Monitoring (Grafana/Prometheus)
├── Makefile                         # Shortcut commands
├── alembic.ini                      # Database migration configuration
├── alembic/                         # Migration files
├── config/
│   ├── config.example.yaml          # Example configuration
│   └── selectors.yaml               # Element selector configuration
├── src/
│   ├── __init__.py                  # Lazy-loading module structure
│   ├── constants.py                 # Constants
│   ├── core/                        # Core infrastructure
│   │   ├── auth/                    # JWT token, encryption
│   │   ├── config/                  # Configuration loading, validation
│   │   ├── infra/                   # Startup, shutdown, retry logic
│   │   ├── bot_controller.py        # Bot lifecycle management
│   │   ├── exceptions.py            # Custom exception classes
│   │   ├── environment.py           # Environment detection
│   │   ├── logger.py                # Loguru configuration
│   │   └── security.py              # API key management
│   ├── models/                      # Database models
│   │   ├── database.py              # PostgreSQL connection management
│   │   └── db_factory.py            # Database factory pattern
│   ├── repositories/                # Repository pattern
│   │   ├── base.py                  # Base CRUD operations
│   │   ├── account_pool_repository.py  # Account pool
│   │   ├── appointment_repository.py   # Appointment operations
│   │   ├── appointment_request_repository.py  # Appointment request operations
│   │   ├── appointment_history_repository.py  # Appointment history tracking
│   │   ├── audit_log_repository.py  # Audit logs
│   │   ├── dropdown_cache_repository.py  # Dropdown cache management
│   │   ├── log_repository.py        # Log operations
│   │   ├── payment_repository.py    # Payment card management
│   │   ├── proxy_repository.py      # Proxy management
│   │   ├── token_blacklist_repository.py  # Token blacklist management
│   │   └── webhook_repository.py    # Webhook management
│   ├── selector/                    # Adaptive selector system
│   ├── services/
│   │   ├── bot/                     # VFS bot core logic
│   │   │   ├── vfs_bot.py           # Main bot orchestrator
│   │   │   ├── browser_manager.py   # Browser lifecycle management
│   │   │   ├── auth_service.py      # Authentication & OTP
│   │   │   ├── slot_checker.py      # Slot availability checking
│   │   │   ├── circuit_breaker_service.py  # Fault tolerance
│   │   │   ├── error_handler.py     # Error capture & screenshots
│   │   │   ├── booking_workflow.py  # Main booking workflow orchestrator
│   │   │   ├── booking_executor.py  # Booking execution and confirmation
│   │   │   ├── reservation_builder.py  # Reservation data structure builder
│   │   │   ├── mission_processor.py # Multi-mission appointment processing
│   │   │   ├── page_state_detector.py  # Page state detection service
│   │   │   ├── waitlist_handler.py  # Waitlist management service
│   │   │   └── service_context.py   # Service dependency injection contexts
│   │   ├── booking/                 # Booking orchestration
│   │   │   ├── booking_orchestrator.py  # Booking flow coordinator
│   │   │   ├── form_filler.py       # Form filling automation
│   │   │   ├── slot_selector.py     # Slot selection logic
│   │   │   ├── payment_handler.py   # Payment processing
│   │   │   ├── booking_validator.py # Booking validation
│   │   │   └── selector_utils.py    # Selector utilities
│   │   ├── session/                 # Session management & recovery
│   │   ├── scheduling/              # Scheduling & cleanup
│   │   │   ├── adaptive_scheduler.py  # Adaptive scheduling
│   │   │   └── cleanup_service.py   # Cleanup service
│   │   ├── notification/            # Telegram/Email notifications
│   │   ├── data_sync/               # Dropdown synchronization
│   │   ├── otp_manager/             # OTP management (Email/SMS)
│   │   ├── captcha_solver.py        # 2Captcha integration
│   │   ├── payment_service.py       # Payment processing
│   │   ├── slot_analyzer.py         # Slot pattern analysis
│   │   └── appointment_deduplication.py  # Duplicate prevention
│   ├── middleware/                  # Request tracking & correlation
│   ├── types/                       # TypedDict definitions
│   ├── constants/                   # Application constants
│   └── utils/                       # Utility modules
│       ├── anti_detection/          # TLS, fingerprint, human simulation
│       ├── security/                # Rate limiting, session, proxy
│       ├── encryption.py            # Fernet encryption
│       └── validators.py            # Input validation
├── web/                             # FastAPI web application
│   ├── app.py                       # FastAPI application factory
│   ├── api_versioning.py            # /api/v1 versioning
│   ├── routes/                      # API endpoints
│   │   ├── auth.py                  # Authentication
│   │   ├── vfs_accounts.py          # VFS account management
│   │   ├── bot.py                   # Bot control
│   │   ├── appointments.py          # Appointments
│   │   ├── audit.py                 # Audit logs
│   │   ├── payment.py               # Payment card
│   │   ├── proxy.py                 # Proxy management
│   │   ├── config.py                # Runtime configuration
│   │   ├── dropdown_sync.py         # Dropdown synchronization
│   │   ├── health.py                # Health check
│   │   ├── webhook_accounts.py      # Webhook token CRUD
│   │   ├── webhook_otp.py           # Per-user OTP receiver
│   │   └── sms_webhook.py           # SMS Forwarder webhooks
│   ├── middleware/                  # Security, CORS, error handling
│   ├── models/                      # Pydantic models
│   ├── state/                       # Thread-safe bot state
│   ├── websocket/                   # WebSocket handler
│   └── templates/                   # HTML templates
├── frontend/                        # React + TypeScript dashboard
├── tests/                           # Test suite (unit, integration, e2e, load)
├── docs/                            # Additional documentation (23+ files)
│   ├── ACCOUNT_POOL_MIGRATION.md
│   ├── API_AUTHENTICATION.md
│   ├── AUTOMATION_FEATURES.md
│   ├── COUNTRY_SELECTOR_SYSTEM.md
│   ├── EMAIL_OTP_SETUP.md
│   ├── OTP_MANAGER_GUIDE.md
│   ├── SECURITY.md
│   ├── SMS_WEBHOOK_SETUP.md
│   └── ... (and more)
├── monitoring/                      # Grafana/Prometheus configuration
├── scripts/                         # Helper scripts
└── screenshots/                     # Screenshots
```

## 🔧 CLI Parameters

The bot supports various command-line options:

```bash
# Run modes
python main.py --mode both      # Run both bot and web dashboard (default)
python main.py --mode web       # Run web dashboard only
python main.py --mode bot       # Run bot automation only

# Read-only mode (degraded mode when database migration fails)
python main.py --mode both --read-only

# Custom configuration file
python main.py --config /path/to/config.yaml

# Logging level
python main.py --log-level DEBUG
```

### 3-Phase Startup Process

The bot uses a 3-phase startup process:

1. **Pre-flight Checks** - Validates critical dependencies and environment
2. **Config Loading** - Loads and validates configuration
3. **Run Mode** - Starts bot/web/both based on `--mode` flag

The `--read-only` flag enables degraded operation when database migrations fail, allowing limited functionality without full database access.

### Read-Only Mode Details

When `--read-only` is active, the following applies:

| Feature | Status | Notes |
|---------|--------|-------|
| Web Dashboard | ✅ View-only | Controls disabled, ReadOnlyBanner displayed |
| `/api/status` endpoint | ✅ Active | Returns `read_only: true` |
| `/health`, `/metrics` | ✅ Active | Monitoring endpoints remain operational |
| Bot automation (start/stop) | ❌ Disabled | No booking attempts |
| User management (CRUD) | ❌ Disabled | Database writes blocked |
| Webhook processing | ❌ Disabled | SMS/OTP webhooks inactive |
| Appointment booking | ❌ Disabled | Full booking pipeline offline |

## 📚 Documentation

Comprehensive documentation is available in the `docs/` directory:

### Setup & Configuration
- [Environment Setup](docs/ENVIRONMENT_SETUP.md) - Environment configuration guide
- [API Authentication](docs/API_AUTHENTICATION.md) - API authentication details
- [Security Guide](docs/SECURITY.md) - Security policies and best practices

### OTP & Webhooks
- [OTP Manager Guide](docs/OTP_MANAGER_GUIDE.md) - Centralized OTP management
- [Email OTP Setup](docs/EMAIL_OTP_SETUP.md) - Microsoft 365 email OTP configuration
- [SMS Webhook Setup](docs/SMS_WEBHOOK_SETUP.md) - SMS webhook integration

### Advanced Features
- [Account Pool Migration](docs/ACCOUNT_POOL_MIGRATION.md) - Multi-account pool setup
- [Automation Features](docs/AUTOMATION_FEATURES.md) - Automation capabilities
- [Country Selector System](docs/COUNTRY_SELECTOR_SYSTEM.md) - Adaptive selector system
- [VFS Dropdown Sync](docs/VFS_DROPDOWN_SYNC.md) - Dropdown data synchronization
- [Waitlist Implementation](docs/WAITLIST_IMPLEMENTATION.md) - Waitlist features
- [Token Sync Implementation](docs/TOKEN_SYNC_IMPLEMENTATION.md) - Token synchronization

### Architecture & Development
- [Modular Architecture](docs/MODULAR_ARCHITECTURE.md) - System architecture overview
- [Middleware](docs/MIDDLEWARE.md) - Middleware structure and usage
- [Frontend UI Guide](docs/FRONTEND_UI_GUIDE.md) - Frontend development guide
- [Payment Security](docs/PAYMENT_SECURITY.md) - Payment card security documentation


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
  "version": "2.2.0",
  "components": {
    "database": true,
    "redis": {"status": "healthy"},
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

### Graceful Degradation & Cache Strategy

VFS-Bot implements a multi-tier caching strategy for resilience when the database becomes unavailable:

| Scenario | Behavior |
|----------|----------|
| Database healthy | Fresh data fetched, cache updated |
| Database down, cache fresh (< `USERS_CACHE_TTL` seconds) | Cached data used, warning logged |
| Database down, cache expired | Empty user list returned, error logged, bot waits for recovery |

**Configuration:**
- `USERS_CACHE_TTL=300` — Cache validity period in seconds (default: 5 minutes)
- The bot automatically attempts database reconnection when in DEGRADED state
- Circuit breaker prevents cascading failures

**Cache Invalidation:**
- Cache is refreshed on every successful database query
- Cache expires automatically after `USERS_CACHE_TTL` seconds
- No manual invalidation needed — the system is self-healing

**Backup Encryption:**
- Database backups are automatically encrypted at rest using Fernet (symmetric encryption)
- Backups use `.sql.enc` extension for encrypted files
- Both `BACKUP_ENCRYPTION_KEY` and `ENCRYPTION_KEY` environment variables are supported
- Restores transparently decrypt backup files before feeding to `psql`
- Legacy unencrypted `.sql` backups remain compatible for cleanup and listing
```

## 🧪 Testing

Run the test suite:

```bash
# Install test dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_bot.py -v
```

## 💳 Payment Security

### What We Store:
- ✅ Card holder name (Fernet encrypted)
- ✅ Card number (Fernet encrypted)
- ✅ Expiry date (Fernet encrypted)
- ✅ CVV (Fernet encrypted — for automated payments, personal use only)

### Payment Flow:
1. Save card via dashboard (including optional CVV)
2. Bot finds appointment
3. Bot uses stored card data for automated payment
4. 3D Secure OTP handled automatically

---

## 📊 Monitoring

### Quick Start: Prometheus + Grafana Monitoring

The bot includes built-in Prometheus metrics and a ready-to-use Grafana dashboard. To start the monitoring stack:

```bash
# Start Prometheus and Grafana
docker-compose -f docker-compose.monitoring.yml up -d

# Access Grafana dashboard
# URL: http://localhost:3000
# ⚠️ Set GRAFANA_ADMIN_PASSWORD in .env file before starting
# Default username: admin
# Password: Use value from GRAFANA_ADMIN_PASSWORD environment variable
```

The dashboard includes:
- **Bot Uptime** - How long the bot has been running
- **Slot Check Rate** - Requests per second to VFS API
- **Active Users** - Number of users being monitored
- **Bookings** - Success vs failure metrics
- **Response Time P95** - 95th percentile API response time
- **Circuit Breaker State** - Bot health and error protection
- **Error Rate by Type** - Categorized error tracking
- **DB Query Duration** - Database performance

Metrics are exposed at `http://localhost:8000/metrics/prometheus` when the bot is running.

---

## 🔐 Security Best Practices

1. **Never commit credentials** - Use `.env` file (gitignored)
2. **Use app passwords** - For Gmail, generate an app-specific password
3. **Secure your API keys** - Don't share captcha API keys
4. **Run in Docker** - Isolate the bot environment
5. **Update regularly** - Keep dependencies up to date

## 🔒 Security Best Practices

### Password Encryption

VFS-Bot v2.2.0+ uses **Fernet symmetric encryption** for storing VFS account passwords. This is critical because:

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

### 💳 Payment Card Security

VFS-Bot implements encrypted payment card storage for personal automated use:

#### What is Stored:
- ✅ **Card holder name** (Fernet encrypted)
- ✅ **Card number** (Fernet encrypted with AES-128)
- ✅ **Expiry date** (Fernet encrypted)
- ✅ **CVV** (Fernet encrypted — optional, for automated payments)

#### Payment Flow:
1. Save card details (including optional CVV) via dashboard
2. Bot finds appointment and retrieves card from encrypted storage
3. Payment is processed automatically
4. 3D Secure OTP handled automatically

#### Security Features:
- **Encrypted card data** - All sensitive fields use Fernet (AES-128) encryption at rest
- **TLS 1.2+** - All network communication is encrypted
- **Webhook signature validation** - SMS OTP webhooks are cryptographically verified

#### 3D Secure Support:
- OTP codes received via SMS webhook
- Automatically entered during payment
- Configurable timeout (default 120 seconds)
- Secure webhook signature validation

### Rate Limiting

- **Global rate limiter** - 60 requests per 60 seconds (default)
- **Per-endpoint limits** - Web API endpoints have additional rate limits
- **Circuit breaker** - Prevents infinite error loops

## 🧪 Testing

VFS-Bot includes a comprehensive test suite with >70% code coverage.

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

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

VFS-Bot v2.2.0 includes comprehensive metrics tracking and monitoring.

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
  "version": "2.2.0",
  "uptime_seconds": 3600.5,
  "components": {
    "database": {"status": "healthy"},
    "redis": {"status": "healthy"},
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
