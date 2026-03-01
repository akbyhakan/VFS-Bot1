# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **FastAPI Upgrade**: Updated FastAPI from `0.128.7` to `0.129.0`
  - Updated `pyproject.toml` FastAPI dependency to `0.129.0`
  - Updated `requirements.lock` with new FastAPI version
  - Verified compatibility with Starlette `0.52.1` (FastAPI 0.129.0 requires `>=0.40.0,<1.0.0`)
  - No breaking changes affecting the codebase (FastAPI 0.129.0 only requires Python 3.10+, project uses 3.12)
  - All middleware, routes, and tests remain fully compatible
- **Dependency Management**: Consolidated to single source of truth (`pyproject.toml`)
  - Updated all CI/CD workflows to use `pip install -e ".[dev]"`
  - Updated Makefile to generate `requirements.lock` from isolated venv
  - Updated Dockerfile.dev to use pyproject.toml, run as non-root user (vfsbot), and removed hardcoded ENCRYPTION_KEY
  - Updated docker-compose.dev.yml volume paths from `/root` to `/home/vfsbot`
  - Added `scripts/verify_version_sync.py` to verify version consistency between `pyproject.toml` and `frontend/package.json`
  - Updated `scripts/verify_lock.py` to verify against `pyproject.toml` directly
  - Updated test suite to verify lock file consistency and version sync
- Database: PostgreSQL with asyncpg connection pooling
- Updated all database operations to use asyncpg patterns
- Migrated from deprecated `google-generativeai` (v0.3.x) to `google-genai` unified SDK (v1.62.0)
- Updated AI model from `gemini-pro` to `gemini-2.5-flash` (stable, production-ready)
- Updated `src/selector/ai_repair.py` to use new Client-based API pattern
- Updated all AI repair tests to match new SDK interface

### Fixed
- Coverage threshold standardized to 80% (was conflicting between 68% in pytest.ini and 80% in pyproject.toml)

### Removed
- Removed `requirements.txt` and `requirements-dev.txt` (superseded by `pyproject.toml`)
- Removed `pytest.ini` (consolidated into `pyproject.toml` `[tool.pytest.ini_options]`)

## [2.2.0] - 2026-01-24

### 🚀 NEW FEATURES

#### Adaptive Selector Learning System
- Auto-promote fallback selectors after 5 consecutive successes
- Track selector performance in `data/selector_metrics.json`
- Reorder selectors dynamically based on success rates
- Reduces timeout delays by trying best-performing selectors first
- Automatic demotion of failing primary selectors after 3 consecutive failures

#### Semantic Locator Support
- Added Playwright's user-facing locators (role, label, text, placeholder)
- More resilient to website changes (IDs can change, text rarely does)
- Multi-language support (Turkish/English)
- Priority given to semantic locators over CSS selectors
- Updated `config/selectors.yaml` with semantic definitions for all login and appointment elements

#### AI-Powered Selector Auto-Repair
- Optional Gemini AI integration for automatic selector recovery
- Activates when all selectors fail
- Auto-updates `config/selectors.yaml` with successful suggestions
- Graceful degradation when API key not provided
- Validates AI suggestions before applying them

### 🐛 BUG FIXES
- Changed `state="attached"` to `state="visible"` in all selector waits
- Fixes issues with VFS loading spinners and animations
- Ensures elements are actually clickable before interaction
- Prevents premature interactions with DOM-attached but invisible elements

### 📦 DEPENDENCIES
- Added `google-genai>=1.62.0` (optional, for AI repair; replaces deprecated `google-generativeai`)

### ⚙️ CONFIGURATION
- New environment variable: `GEMINI_API_KEY` (optional)
- New data file: `data/selector_metrics.json` (auto-created)
- Updated `config/selectors.yaml` structure with `semantic` field

### 📚 DOCUMENTATION
- Added "Adaptive Selector Strategy" section to README.md
- Updated .env.example with GEMINI_API_KEY
- Added comprehensive test coverage for new features

### ⚠️ BREAKING CHANGES
- Existing `config/selectors.yaml` files will continue to work
- New features are opt-in

## [2.1.0] - 2025-01-12

### 🚨 CRITICAL SECURITY FIXES

#### Password Encryption System
- **BREAKING CHANGE:** Passwords now encrypted with Fernet (AES-128) instead of bcrypt hashing
- Added `src/utils/encryption.py` with symmetric encryption
- Updated `src/models/database.py` to use encryption for VFS passwords
- Added `ENCRYPTION_KEY` environment variable (required)
- Added `get_active_users_with_decrypted_passwords()` method

#### Environment Variable Validation
- Enhanced `src/core/env_validator.py` with format validation
- Email format validation using regex
- Encryption key validation (44-char base64 Fernet key)
- API key minimum length validation (16 chars)

#### Database Connection Pooling
- Implemented connection pool (5 connections) in `src/models/database.py`
- Added `get_connection()` context manager for safe concurrent access
- Prevents race conditions with multiple users

### ⚡ CRITICAL LOGIC FIXES

#### Circuit Breaker Pattern
- Maximum consecutive errors: 5
- Maximum total errors per hour: 20
- Exponential backoff: `min(60 * 2^(errors-1), 600)` seconds
- Auto-recovery after successful operation
- Prevents infinite error loops

#### Parallel User Processing
- Process up to 5 users concurrently (configurable)
- Uses `asyncio.Semaphore` for concurrency control
- 5x performance improvement with multiple users
- Better resource utilization

#### Rate Limiter
- Verified existing implementation (60 requests/60 seconds)
- Token bucket algorithm with async locks
- Thread-safe for concurrent operations

### 🎯 NEW FEATURES

#### Payment Processing Service
- Created `src/services/payment_service.py`
- Manual payment mode (wait for user)
- Automated payment framework (PCI-DSS warnings)
- Support for encrypted card details
- Comprehensive logging and error handling

#### Enhanced Error Capture
- Auto-cleanup of old errors (7 days retention)
- Enhanced metadata capture (HTML, console logs, screenshots)
- JSON export for error analysis
- Periodic cleanup (hourly)

#### Metrics and Monitoring
- Created `src/utils/metrics.py` with BotMetrics class
- Track: checks, slots found, appointments, errors, success rate
- New endpoint: `/api/metrics` - Detailed JSON metrics
- New endpoint: `/metrics/prometheus` - Prometheus text format
- Enhanced `/health` endpoint with component status
- Prometheus-compatible metrics export
- Success rate calculation
- Circuit breaker trip tracking

### 🎨 REFACTORING

#### Constants File
- Created `src/constants.py` with all magic numbers
- Classes: Timeouts, Intervals, Retries, RateLimits, CircuitBreaker
- DRY principle applied throughout codebase

#### Helper Utilities
- Created `src/utils/helpers.py` for common operations
- Functions: `smart_fill`, `smart_click`, `wait_for_selector_smart`
- Reduced code duplication by 200+ lines
- Consistent error handling

#### Configuration Validation
- Enhanced `src/core/config_validator.py` with Pydantic models
- Schemas: VFSConfig, BotConfig, NotificationConfig, CaptchaConfig, AppConfig
- HTTPS validation for VFS base_url
- Min/max validation for intervals (10-3600s)
- Minimum centre count (at least 1)

### 🧪 TESTING

#### Comprehensive Test Suite
- Created `tests/test_encryption.py` - 15 password encryption tests
- Created `tests/test_database.py` - 10 database tests with encryption
- Created `tests/test_validators.py` - 15 environment validation tests
- Created `pytest.ini` - Pytest configuration with 68% coverage target
- Added async test support
- Coverage reporting (HTML, term, XML)

### 📝 DOCUMENTATION

#### README Updates
- Added "Security Best Practices" section
- Added "Testing" section with pytest examples
- Added "Monitoring & Metrics" section with endpoint documentation
- Enhanced with Prometheus integration examples
- Circuit breaker monitoring documentation

#### Changelog
- Updated for v2.1.0 release
- Comprehensive breaking changes documentation

### Added
- Health check endpoint (`/health`) for monitoring
- Metrics endpoint (`/metrics`) for performance tracking
- Structured JSON logging for production
- Environment variables validation on startup
- Configuration schema validation
- Global rate limiting (60 req/min default)
- Test coverage reporting with Codecov
- Prometheus-compatible metrics
- TLS fingerprinting bypass using curl-cffi
- Canvas, WebGL, and Audio Context fingerprinting bypass
- Human behavior simulation with Bézier curve mouse movements
- Cloudflare challenge detection and bypass (Waiting Room, Turnstile, Browser Check)
- JWT session management with auto-refresh
- Dynamic header rotation with consistent User-Agent/Sec-CH-UA
- Proxy rotation system with failure tracking
- Anti-detection test suite
- CI/CD pipeline with GitHub Actions
- Security policy (SECURITY.md)
- Contributing guidelines (CONTRIBUTING.md)
- Issue and PR templates
- Pre-commit hooks configuration
- Development requirements (requirements-dev.txt)
- Linting and formatting configuration (pyproject.toml)
- This CHANGELOG file

### Changed
- Logging format supports both human-readable and JSON
- Startup validation enforces required environment variables
- Updated README.md with correct copyright information
- Improved project structure documentation
- Enhanced bot with anti-detection features integration

### Fixed
- Docker health check now uses `/health` endpoint

### Removed
- Removed notes.txt from repository (development notes)

## [1.0.0] - 2025-01-09

### Added
- Initial release
- Automated VFS appointment checking
- Playwright-based browser automation
- Web dashboard with FastAPI
- Multi-channel notifications (Telegram, Email)
- Multiple captcha solver support
- PostgreSQL database for tracking
- Docker support
- Multi-user and multi-centre support

[Unreleased]: https://github.com/akbyhakan/VFS-Bot1/compare/v2.2.0...HEAD
[2.2.0]: https://github.com/akbyhakan/VFS-Bot1/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/akbyhakan/VFS-Bot1/compare/v1.0.0...v2.1.0
[1.0.0]: https://github.com/akbyhakan/VFS-Bot1/releases/tag/v1.0.0
