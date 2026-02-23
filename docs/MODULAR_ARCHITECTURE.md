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

## 📊 Metrics

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Files** | 1 | 7 | Better organization |
| **Main Class Lines** | 860 | 460 | 46.5% reduction |
| **Responsibilities** | 7 in 1 class | 1 per class | SRP compliant |
| **Test Isolation** | Low | High | Easy mocking |
| **Coupling** | Tight | Loose | Independent components |

## 🔄 Migration Guide

### Recommended Way
```python
from src.services.bot import VFSBot

# Same interface, modular implementation
bot = VFSBot(config, db, notifier)
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

## 📚 Related Documentation

- [SOLID Principles](https://en.wikipedia.org/wiki/SOLID)
- [Single Responsibility Principle](https://en.wikipedia.org/wiki/Single-responsibility_principle)
- [God Object Anti-Pattern](https://en.wikipedia.org/wiki/God_object)
