# VFS Bot Modular Architecture

This document describes the refactored modular architecture of the VFS Bot, which follows the Single Responsibility Principle (SRP).

## 📁 Structure

The VFS Bot is now split into focused, maintainable components:

```
src/services/bot/
├── __init__.py                    # Public API exports
├── vfs_bot.py                     # Orchestrator (~415 lines)
├── bot_loop_manager.py            # Main bot loop and loop helpers (~250 lines)
├── booking_dependencies.py        # DI container dataclasses (~69 lines)
├── booking_workflow.py            # Main booking workflow orchestrator
├── booking_executor.py            # Booking execution and confirmation
├── reservation_builder.py         # Reservation data structure builder
├── mission_processor.py           # Individual request processing within missions
├── browser_manager.py             # Browser lifecycle (~159 lines)
├── auth_service.py                # Authentication & OTP (~157 lines)
├── slot_checker.py                # Slot availability (~145 lines)
├── circuit_breaker_service.py     # Fault tolerance (~141 lines)
├── error_handler.py               # Error capture & screenshots (~131 lines)
├── page_state_detector.py         # Page state detection
├── waitlist_handler.py            # Waitlist handling
└── service_context.py             # Service context and dependency factories
```

## 🎯 Component Responsibilities

### 1. **VFSBot** (Orchestrator)
- **File**: `vfs_bot.py`
- **Responsibility**: Coordinate all bot components
- **Lines**: ~415 (down from 668 after BotLoopManager extraction)
- **Key Methods**:
  - `__init__()` - Initialize bot with dependency injection
  - `_wire_booking_dependencies()` - Static factory for BookingDependencies (SRP extraction)
  - `start()` - Initialize and start bot loop (delegates to BotLoopManager)
  - `stop()` - Graceful shutdown (idempotent, delegates to helpers)
  - `_cancel_health_checker()` - Cancel health checker task
  - `_shutdown_active_bookings()` - Wait for active bookings with grace period
  - `_force_cancel_bookings()` - Force-cancel after timeout
  - `_save_shutdown_checkpoint()` - Save state before cancellation
  - `_notify_stopped()` - Send stopped notification
  - `book_appointment_for_request()` - API booking delegation
  - `trigger_immediate_check()` - Trigger immediate slot check
  - `cleanup()` - Browser resource cleanup (idempotent)

#### stop() Decomposition

`stop()` is decomposed into small focused helpers for clarity and testability:

```
stop()
├── _cancel_health_checker()       # Cancel health checker asyncio task
├── _shutdown_active_bookings()    # Wait for bookings with grace period
│   └── _force_cancel_bookings()   # Force-cancel after timeout
│       └── _save_shutdown_checkpoint()  # Save state before cancellation
├── cleanup()                      # Close browser resources
└── _notify_stopped()              # Send stopped notification
```

### 2. **BotLoopManager** (Loop Manager)
- **File**: `bot_loop_manager.py`
- **Responsibility**: Manage the main bot processing loop and associated helpers
- **Lines**: ~250
- **Key Methods**:
  - `run_bot_loop()` - Main processing loop using SessionOrchestrator
  - `_wait_or_shutdown()` - Event-based wait (no polling)
  - `_handle_circuit_breaker_open()` - Handle CB open state with alerting
  - `_wait_adaptive_interval()` - Adaptive interval scheduling
  - `_ensure_db_connection()` - Database health check and reconnection
  - `_record_circuit_breaker_trip()` - Metrics recording

### 4. **BookingDependencies** (DI Container)
- **File**: `booking_dependencies.py`
- **Responsibility**: Dependency injection container dataclasses grouping all services required by BookingWorkflow
- **Lines**: ~69
- **Dataclasses**:
  - `WorkflowServices` — Core workflow services (auth, slots, booking, waitlist, error handling, page state, slot analysis, session recovery, alerts)
  - `InfraServices` — Infrastructure services (browser, proxy, headers, anti-detection, error capture)
  - `RepositoryServices` — Data access repositories (appointment, appointment request)
  - `BookingDependencies` — Top-level container grouping `WorkflowServices`, `InfraServices`, and `RepositoryServices`

### 5. **BookingWorkflow** (Workflow Orchestrator)
- **File**: `booking_workflow.py`
- **Responsibility**: Orchestrate the end-to-end booking workflow for a mission (country)
- **Constructor**: `__init__(config, notifier, deps)` — repositories are injected via `deps.repositories` (no `db` parameter)
- **Composes**: `ReservationBuilder`, `BookingExecutor`, `MissionProcessor`
- **Key Methods**:
  - `process_mission()` - Process a mission (country) using a pooled account
  - `_login_and_stabilize()` - Login + page state detection + waitlist check
  - `_process_mission_requests()` - Process requests with `@retry` for recoverable errors
  - `process_waitlist_flow()` - Handle waitlist flow
  - `_handle_workflow_exception()` - Consistent exception handling
  - `_capture_error_safe()` - Safe error capture with screenshots

### 6. **BookingExecutor**
- **File**: `booking_executor.py`
- **Responsibility**: Execute booking flows and confirm appointments
- **Key Methods**:
  - `execute_and_confirm_booking()` - Execute booking and confirm appointment

### 7. **ReservationBuilder**
- **File**: `reservation_builder.py`
- **Responsibility**: Build reservation data structures for appointment bookings
- **Key Methods**:
  - `build_reservation_for_user()` - Build reservation for user using appropriate strategy
  - `build_reservation()` - Build reservation from provided data

### 8. **MissionProcessor**
- **File**: `mission_processor.py`
- **Responsibility**: Process individual appointment requests within a mission
- **Key Methods**:
  - `process_single_request()` - Process a single appointment request

### 9. **BrowserManager**
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

### 10. **AuthService**
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

### 11. **SlotChecker**
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

### 12. **CircuitBreakerService**
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
- **Note**: Thin wrapper around `src.core.circuit_breaker.CircuitBreaker`
- **Features**:
  - Thread-safe operation
  - Consecutive error tracking
  - Time-windowed error tracking
  - Exponential backoff
  - Metrics integration

### 13. **ErrorHandler**
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
| **Files** | 1 | 15 | Better organization |
| **Main Class Lines** | 860 | 415 | 52% reduction |
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

### Using the DI Container (BookingDependencies)

```python
from src.services.bot.booking_dependencies import (
    BookingDependencies,
    WorkflowServices,
    InfraServices,
    RepositoryServices,
)
from src.services.bot.booking_workflow import BookingWorkflow
from src.repositories import (
    AppointmentRepository,
    AppointmentRequestRepository,
)

# Repositories are injected, not created internally
deps = BookingDependencies(
    workflow=workflow_services,
    infra=infra_services,
    repositories=RepositoryServices(
        appointment_repo=AppointmentRepository(db),
        appointment_request_repo=AppointmentRequestRepository(db),
    ),
)
workflow = BookingWorkflow(config=config, notifier=notifier, deps=deps)
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
