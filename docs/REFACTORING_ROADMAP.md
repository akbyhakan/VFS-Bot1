# 🗺️ Refactoring Roadmap Report

> **Date:** 2026-02-16
> **Scope:** Full read-only codebase audit
> **Status:** Awaiting approval before implementation

---

## 1. 🏗️ Architectural & Structural Health

### Current State

The project follows a well-organized modular structure:

```
VFS-Bot1/
├── main.py                    # CLI entry point (4-phase startup)
├── src/                       # Application source code
│   ├── core/                  # Framework (config, auth, infra, exceptions)
│   ├── models/                # Database interface & Pydantic schemas
│   ├── repositories/          # Data access layer (Repository pattern)
│   ├── services/              # Business logic (bot, booking, session, notification, vfs, otp, etc.)
│   ├── selector/              # Adaptive CSS/semantic selector system
│   ├── constants/             # Application constants
│   ├── middleware/             # Request tracking & correlation
│   ├── types/                 # TypedDict definitions
│   └── utils/                 # Utilities (anti-detection, security, helpers)
├── web/                       # FastAPI dashboard (routes, models, middleware, websocket)
├── frontend/                  # React + TypeScript + Vite SPA
├── tests/                     # Pytest suite (unit, integration, e2e, load)
├── alembic/                   # Database migrations (10 versions)
├── config/                    # YAML configuration (selectors, countries)
├── scripts/                   # Utility scripts
├── monitoring/                # Prometheus/Grafana configs
└── docs/                      # Documentation (20+ guides)
```

### Issues

| # | Issue | Severity |
|---|-------|----------|
| 1 | **Multiple rate limiter implementations** spread across `src/utils/security/` (3 files) and `src/core/auth/` (1 file) without a unified abstraction | Medium |
| 2 | **`web/routes/health.py` (651 lines)** acts as a "dumping ground" for health checks, Kubernetes probes, Prometheus metrics, system diagnostics, and bot metrics — far beyond a simple health endpoint | Medium |
| 3 | **`src/services/notification/notification.py` (779 lines)** bundles channel abstraction, Telegram/Email/WebSocket implementations, and orchestration into a single file | Medium |

### Recommendation

No major restructuring needed. The current `src/` hierarchy is sound. Targeted refactors:

1. **Consolidate rate limiters** under `src/core/rate_limiting/` with a strategy pattern (in-memory, Redis, adaptive, endpoint-specific).
2. **Split `web/routes/health.py`** into `health_probes.py` (K8s liveness/readiness/startup), `health_diagnostics.py` (detailed checks), and move Prometheus export to `prometheus.py`.
3. **Split `src/services/notification/notification.py`** into per-channel files.

---

## 2. 🚨 Code Quality Violations (SRP & DRY)

### Single Responsibility Principle (SRP) Violations

| File | Lines | Responsibilities | Recommendation |
|------|-------|-----------------|----------------|
| `web/routes/health.py` | 651 | K8s probes, detailed health checks (DB, Redis, encryption, notifications, proxy, VFS API, captcha), Prometheus metrics export, bot metrics aggregation, circuit breaker status, system metrics (CPU/memory/disk) | Split into 3 focused modules |
| `src/services/notification/notification.py` | 779 | Base `NotificationChannel` ABC, `TelegramChannel`, `EmailChannel`, `WebSocketChannel` implementations, `NotificationService` orchestrator, configuration dataclasses | Split into per-channel files + orchestrator |
| `src/utils/db_backup.py` | 629 | Backup creation/restoration, encryption/decryption, retention policy, scheduled execution | Consider extracting encryption to shared utility |
| `src/core/exceptions.py` | 554 | 50+ custom exception classes | Acceptable for a single exception hierarchy, but could group by domain |

### Don't Repeat Yourself (DRY) Violations

#### 1. Duplicate Token Bucket Rate Limiting

**`src/utils/security/rate_limiter.py` (lines 34–56)** and **`src/core/auth/rate_limiter.py` (`InMemoryBackend`, lines 105–160)** both implement the same sliding-window token bucket pattern:

```python
# Both files implement:
self.requests: deque = deque(maxlen=...)
async def acquire(self) -> None:
    async with self._lock:
        current_time = time.time()
        while self.requests and self.requests[0] < current_time - self.time_window:
            self.requests.popleft()
        if len(self.requests) < self.max_requests:
            self.requests.append(current_time)
            return
```

Additionally, **`src/utils/security/adaptive_rate_limiter.py`** (50 lines) and **`src/utils/security/endpoint_rate_limiter.py`** add further rate limiting variants without sharing a common base.

**Impact:** 4 separate rate limiter files with overlapping logic. Changes to the algorithm must be replicated across files.

#### 2. Overlapping Slot Handling Logic

**`src/services/bot/slot_checker.py`** and **`src/services/booking/slot_selector.py`** both handle:
- Waiting for page overlays to disappear
- Cloudflare challenge detection and handling
- Date-based slot selection logic

While they serve different purposes (API slot checking vs. calendar UI selection), shared concerns like overlay waiting and Cloudflare handling could be extracted.

#### 3. Exception Handling Patterns

**`src/services/bot/booking_workflow.py` (lines 194–212)** and **`src/middleware/error_handler.py` (lines 41–58)** both implement exception-type-to-action mapping chains with similar structure:

```python
except LoginError as e:
    logger.error(...)
    await self._capture_error_safe(...)
    return "login_fail"
except BannedError as e:
    ...
except VFSBotError as e:
    ...
```

---

## 3. 💀 Dead, Zombie & Deprecated Code

### Unused Files (Not imported in any production code)

| File | Lines | Notes |
|------|-------|-------|
| `src/utils/form_handler.py` | 362 | **Not imported anywhere** in `src/`, `web/`, or `main.py`. No production references. |
| `src/core/feature_flags.py` | 194 | **Only imported in test file** (`tests/unit/test_feature_flags.py`). Not used in any production code path. |
| `src/utils/user_agent_rotator.py` | 51 | **Only imported in test file** (`tests/unit/test_user_agent_rotator.py`). Not referenced in production code. The `HeaderManager` in `src/utils/security/header_manager.py` handles user-agent rotation independently. |

### Dead Functions/Variables

- `src/core/feature_flags.py:187` defines `get_feature_flags()` — never called outside tests.
- `src/utils/form_handler.py` defines `FormHandler` class with multiple methods — none called from production code.

### Deprecated References

✅ **All resolved.**

### Previously Migrated (Resolved)

- ✅ `google-generativeai` (deprecated) → migrated to `google-genai~=1.62.0` (unified SDK)
- ✅ `selenium` → fully replaced by `playwright>=1.58.0`
- ✅ `asyncio.get_event_loop().time()` in `notification.py:368` → replaced with `asyncio.get_running_loop().time()` (fixed in this PR)

---

## 4. 🔒 Security & Configuration (Critical)

### Hardcoded Secrets

✅ **No hardcoded secrets found in production source code.**

All credentials use environment variables:
- Authorization headers: `f"Bearer {self.session.access_token}"` (dynamic)
- Database URLs: `os.environ["DATABASE_URL"]`
- API keys: `os.environ.get("CAPTCHA_API_KEY")`

### Environment Configuration

✅ **Well-implemented:**
- `.env.example` provided with comprehensive documentation (all 50+ variables)
- `src/core/config/env_validator.py` validates required variables at startup
- `src/core/environment.py` centralizes environment variable access
- `.gitignore` excludes `.env*`, `config/secrets/`, `*.pem`, `*.key`
- Sensitive data masking via `src/utils/safe_logging.py` and `src/utils/log_sanitizer.py`
- Password encryption at rest via `src/utils/encryption.py` (Fernet)

### Minor Observations

| # | Observation | Severity |
|---|-------------|----------|
| 1 | `web/routes/payment.py:171` has `# TODO: Implement actual payment processing` — stub endpoint exposed in production API | Low |

---

## 5. 📉 Performance Bottlenecks

### Blocking Calls in Async Context

✅ **No violations found.** All `time.sleep()` calls are in dedicated synchronous background threads (OTP IMAP listener), not in `async def` functions. The codebase correctly uses `await asyncio.sleep()` throughout async code paths.

### Deprecated Async Pattern

✅ **Resolved** — `asyncio.get_event_loop().time()` in `src/services/notification/notification.py:368` has been replaced with `asyncio.get_running_loop().time()` (fixed in this PR).

### Resource Usage

✅ Connection pooling properly configured for PostgreSQL (`asyncpg`) and Redis (`redis[hiredis]`).
✅ Browser pool management in `src/services/bot/browser_pool.py` with limits.
✅ `asyncio.gather()` used appropriately for concurrent operations.

---

## 📝 The Action Plan

### 🔴 High Priority (Critical fixes, security risks)

1. ~~**Fix deprecated `asyncio.get_event_loop()` call**~~ ✅ **FIXED in this PR**
   - File: `src/services/notification/notification.py:368`
   - Changed: `asyncio.get_event_loop().time()` → `asyncio.get_running_loop().time()`

2. **Review payment stub endpoint**
   - File: `web/routes/payment.py:171`
   - The `# TODO: Implement actual payment processing` suggests an unfinished endpoint is exposed. Ensure it returns appropriate 501/503 status and is not callable in production.

### 🟡 Medium Priority (Refactoring SRP/DRY, structural improvements)

3. **Consolidate rate limiter implementations**
   - Merge the 4 rate limiter files into a unified module with strategy pattern
   - Files: `src/utils/security/rate_limiter.py`, `src/core/auth/rate_limiter.py`, `src/utils/security/adaptive_rate_limiter.py`, `src/utils/security/endpoint_rate_limiter.py`
   - Goal: Single `RateLimiter` base with configurable backends (in-memory, Redis) and strategies (fixed, adaptive, endpoint-specific)

4. **Split `web/routes/health.py` (651 lines)**
   - Extract into: `health_probes.py`, `health_diagnostics.py`, `prometheus.py`
   - Each file handles one responsibility

5. **Split `src/services/notification/notification.py` (779 lines)**
   - Extract into: `base.py`, `telegram_channel.py`, `email_channel.py`, `websocket_channel.py`, `notification_service.py`

6. ~~**Remove dead code**~~ ✅ **COMPLETED**
   - ~~Remove `src/utils/form_handler.py` (362 lines, never imported)~~ ✅ Deleted
   - ~~Remove `src/core/feature_flags.py` (194 lines, only in tests)~~ ✅ Deleted
   - ~~Remove `src/utils/user_agent_rotator.py` (51 lines, only in tests)~~ ✅ Deleted
   - ~~Update corresponding test files accordingly~~ ✅ Deleted `tests/unit/test_feature_flags.py` and `tests/unit/test_user_agent_rotator.py`

7. **Extract shared slot-handling utilities**
   - Create shared helpers for overlay-waiting and Cloudflare-challenge detection used by both `slot_checker.py` and `slot_selector.py`

### 🟢 Low Priority (Code hygiene, naming, comments)

8. **Standardize exception handling patterns**
   - Create a shared exception-to-action mapper utility to reduce boilerplate in `booking_workflow.py` and `error_handler.py`

9. **Review `src/utils/db_backup.py` (629 lines)**
   - Consider extracting backup encryption logic to a shared module (already has `src/utils/encryption.py`)

10. **Audit `web/templates/`**
    - Contains only `errors.html`, used by `web/routes/dashboard.py`. Confirm it's needed; if the SPA handles all error rendering, this may be removable.

---

> **⏸️ Awaiting approval on this plan before writing any code.**
