# VFS Bot Modular Architecture

This document describes the refactored modular architecture of the VFS Bot, which follows the Single Responsibility Principle (SRP).

## 📁 Structure

The VFS Bot is now split into focused, maintainable components:

```
src/services/bot/
├── __init__.py                    # Public API exports
├── vfs_bot.py                     # Orchestrator (~460 lines)
├── browser_manager.py             # Browser lifecycle (~159 lines)
├── auth_service.py                # Authentication & OTP (~157 lines)
├── slot_checker.py                # Slot availability (~133 lines)
├── circuit_breaker_service.py     # Fault tolerance (~141 lines)
└── error_handler.py               # Error capture & screenshots (~131 lines)

src/resilience/                    # Anti-fragile resilience system
├── __init__.py                    # Resilience exports
├── manager.py                     # ResilienceManager orchestrator
├── hot_reload.py                  # HotReloadableSelectorManager
├── forensic_logger.py             # ForensicLogger (black box)
├── smart_wait.py                  # SmartWait (3-stage pipeline)
└── ai_repair_v2.py                # AIRepairV2 (structured output)
```

## 🎯 Component Responsibilities

### 1. **VFSBot** (Orchestrator)
- **File**: `vfs_bot.py`
- **Responsibility**: Coordinate all bot components
- **Lines**: ~460 (down from 860 in the God Class)
- **Key Methods**:
  - `start()` - Initialize and start bot loop
  - `stop()` - Graceful shutdown
  - `run_bot_loop()` - Main processing loop
  - `process_user()` - User booking workflow
  - `fill_personal_details()` - Form filling
  - `book_appointment()` - Complete booking

### 2. **BrowserManager**
- **File**: `browser_manager.py`
- **Responsibility**: Browser lifecycle and context management
- **Lines**: ~159
- **Key Methods**:
  - `start()` - Launch browser with anti-detection
  - `close()` - Clean up browser resources
  - `new_page()` - Create page with stealth settings
- **Features**:
  - Anti-detection configuration
  - Proxy support
  - Custom user agents
  - Fingerprint bypass

### 3. **AuthService**
- **File**: `auth_service.py`
- **Responsibility**: VFS authentication operations
- **Lines**: ~157
- **Key Methods**:
  - `login()` - Handle VFS login flow
  - `handle_otp_verification()` - OTP verification
- **Features**:
  - Captcha solving integration
  - Cloudflare challenge handling
  - Human-like interactions
  - Error capture

### 4. **SlotChecker**
- **File**: `slot_checker.py`
- **Responsibility**: Check appointment slot availability
- **Lines**: ~133
- **Key Methods**:
  - `check_slots()` - Check for available slots
- **Features**:
  - Rate limiting
  - Cloudflare bypass
  - Human simulation
  - Error context capture

### 5. **CircuitBreakerService**
- **File**: `circuit_breaker_service.py`
- **Responsibility**: Fault tolerance wrapper around core circuit breaker
- **Lines**: ~103
- **Key Methods**:
  - `is_available()` - Check if circuit allows requests
  - `record_success()` - Reset on success
  - `record_failure()` - Track failures
  - `reset()` - Close circuit breaker
  - `get_wait_time()` - Exponential backoff calculation
  - `get_stats()` - Current circuit state
- **Note**: Thin wrapper around `src.core.circuit_breaker.CircuitBreaker` for backward compatibility
- **Features**:
  - Thread-safe operation
  - Consecutive error tracking
  - Time-windowed error tracking
  - Exponential backoff
  - Metrics integration

### 6. **ErrorHandler**
- **File**: `error_handler.py`
- **Responsibility**: Error capture and screenshot management
- **Lines**: ~131
- **Key Methods**:
  - `handle_error()` - Capture error context
  - `take_screenshot()` - Save error screenshots
  - `save_checkpoint()` - Save state for recovery
  - `load_checkpoint()` - Load saved state
- **Features**:
  - Automatic screenshot capture
  - State checkpointing
  - Error context logging

## 🛡️ Resilience Module (`src/resilience/`)

The resilience module provides an anti-fragile system for handling VFS Global frontend changes.

### 7. **ResilienceManager** (Central Orchestrator)
- **File**: `manager.py`
- **Responsibility**: Coordinate all resilience features
- **Lines**: ~200
- **Key Methods**:
  - `start()` / `stop()` - Lifecycle management
  - `find_element()` - 3-stage selector resolution
  - `safe_click()`, `safe_fill()`, `safe_select()` - Convenience methods
  - `reload_selectors()` - Manual selector reload
  - `get_status()` - Status reporting
- **Features**:
  - Country-aware selector management
  - Hot-reload integration
  - Forensic logging on failures
  - AI-powered repair
  - Learning-based optimization

### 8. **HotReloadableSelectorManager**
- **File**: `hot_reload.py`
- **Responsibility**: File-polling based selector hot-reload
- **Lines**: ~150
- **Parent**: Extends `CountryAwareSelectorManager`
- **Key Methods**:
  - `start_watching()` / `stop_watching()` - File watcher lifecycle
  - `_has_file_changed()` - Change detection
  - `get_status()` - Watcher status
- **Features**:
  - File polling (mtime/size change detection)
  - Configurable poll interval (default: 5s)
  - Reload counter for monitoring
  - Country-aware selector inheritance

### 9. **ForensicLogger** (Black Box)
- **File**: `forensic_logger.py`
- **Responsibility**: Country-aware incident capture
- **Lines**: ~300
- **Key Methods**:
  - `capture_incident()` - Comprehensive error capture
  - `get_recent_incidents()` - Retrieve recent errors
  - `get_incident_by_id()` - Specific incident lookup
  - `get_status()` - Logger metrics
- **Features**:
  - Directory structure: `logs/errors/{country}/{date}/{incident_id}_*`
  - Full-page screenshots
  - Raw DOM dumps (with size limits)
  - Masked context JSON (cookies, localStorage, sessionStorage)
  - Automatic cleanup (max incidents limit)
  - Traceback capture

### 10. **SmartWait** (3-Stage Pipeline)
- **File**: `smart_wait.py`
- **Responsibility**: Intelligent selector resolution
- **Lines**: ~250
- **Key Methods**:
  - `find_element()` - Main pipeline entry point
  - `_try_semantic_locator()` - Stage 1 (semantic)
  - `_try_css_selectors()` - Stage 2 (CSS with backoff)
  - `_try_ai_repair()` - Stage 3 (AI-powered)
- **Features**:
  - **Stage 1**: Playwright semantic locators (role, label, text, placeholder)
  - **Stage 2**: CSS selectors with exponential backoff retry
  - **Stage 3**: AI repair with validation
  - Learning integration (success/failure tracking)
  - Forensic logging on total failure

### 11. **AIRepairV2** (Structured Output)
- **File**: `ai_repair_v2.py`
- **Responsibility**: AI-powered selector suggestions
- **Lines**: ~350
- **Key Methods**:
  - `repair_selector()` - Get AI suggestion with structured output
  - `persist_to_yaml()` - Auto-update selectors YAML
  - `_sanitize_html()` - Remove sensitive data
- **Features**:
  - Pydantic `RepairResult` model for structured output
  - JSON schema validation
  - Confidence filtering (threshold: 0.7)
  - HTML sanitization (scripts, values, tokens)
  - Graceful degradation when GenAI unavailable
  - Configurable model and temperature

## 📊 Metrics

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Files** | 1 | 12 | Better organization |
| **Main Class Lines** | 860 | 460 | 46.5% reduction |
| **Responsibilities** | 7 in 1 class | 1 per class | SRP compliant |
| **Test Isolation** | Low | High | Easy mocking |
| **Coupling** | Tight | Loose | Independent components |
| **Resilience** | Partial | Unified | Anti-fragile system |

## 🔄 Migration Guide

### Recommended Way
```python
from src.services.bot import VFSBot

# Same interface, modular implementation
bot = VFSBot(config, db, notifier)
```

### Using Resilience Manager
```python
from src.resilience import ResilienceManager

# Initialize with country-aware configuration
resilience = ResilienceManager(
    country_code="fra",
    enable_ai_repair=True,
    enable_hot_reload=True,
)

# Lifecycle
await resilience.start()

# Use resilience features
locator = await resilience.find_element(page, "login.email_input")
await resilience.safe_click(page, "login.submit_button")
await resilience.safe_fill(page, "login.email", "user@example.com")

# Manual reload
resilience.reload_selectors()

# Cleanup
await resilience.stop()
```

### Using Individual Components
```python
from src.services.bot import (
    BrowserManager,
    AuthService,
    SlotChecker,
    CircuitBreakerService,
    ErrorHandler,
)

# Create and use components independently
browser_mgr = BrowserManager(config)
await browser_mgr.start()

circuit_breaker = CircuitBreakerService()
if await circuit_breaker.is_available():
    # Process request
    pass
```

## ✅ Benefits

1. **Single Responsibility Principle**: Each class has one clear purpose
2. **Easier Testing**: Mock individual components instead of entire bot
3. **Better Maintainability**: Smaller, focused files are easier to understand
4. **Loose Coupling**: Components depend on interfaces, not implementations
5. **Reusability**: Components can be used independently
6. **Backward Compatibility**: Existing code continues to work
7. **Type Safety**: Full type hints throughout
8. **Documentation**: Comprehensive docstrings
9. **Anti-Fragile**: System benefits from UI changes (learning + forensics)
10. **Country-Aware**: All resilience features respect country configuration

## 🧪 Testing

Tests can target individual components:

```python
from src.services.bot import CircuitBreakerService

async def test_circuit_breaker():
    cb = CircuitBreakerService()
    assert await cb.is_available()
    
    await cb.record_failure()
    stats = await cb.get_stats()
    assert stats["consecutive_errors"] == 1
```

Resilience tests:
```python
from src.resilience import ResilienceManager, ForensicLogger

async def test_forensic_capture():
    logger = ForensicLogger(country_code="fra")
    incident = await logger.capture_incident(page, error, context)
    assert "screenshot" in incident["captures"]
```

## 🔧 Deprecation Timeline

- **v2.0**: Modular structure introduced with deprecation warnings
- **v3.0**: Backward compatibility layer removed (completed)
- **v3.1**: Resilience module added (current)

## 📚 Related Documentation

- [SOLID Principles](https://en.wikipedia.org/wiki/SOLID)
- [Single Responsibility Principle](https://en.wikipedia.org/wiki/Single-responsibility_principle)
- [God Object Anti-Pattern](https://en.wikipedia.org/wiki/God_object)
- [RESILIENCE_GUIDE.md](./RESILIENCE_GUIDE.md) - Detailed resilience usage guide
