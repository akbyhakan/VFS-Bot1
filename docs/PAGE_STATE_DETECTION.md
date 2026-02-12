# Page State Detection System

## Overview

The Page State Detection System enables the VFS bot to intelligently detect which screen/page it's currently on and automatically handle unexpected states with appropriate recovery strategies.

## Problem Solved

**Before**: The bot performed "blind navigation" - it didn't verify if pages were what it expected. If VFS added new screens (CAPTCHA, 2FA, maintenance page, session expired, etc.), the bot would break.

**After**: The bot now:
1. Detects which screen it's on
2. Knows what to do on each screen
3. Automatically recovers from unexpected states
4. Logs all state transitions for debugging
5. Captures forensic evidence for unknown states

## Architecture

### Components

1. **`PageState` Enum** (`src/resilience/page_state_detector.py`)
   - Defines all known VFS page/screen states
   - 21 states categorized into:
     - Normal flow states (LOGIN_PAGE, DASHBOARD, APPOINTMENT_SELECTION, etc.)
     - Waitlist states (WAITLIST_MODE, WAITLIST_SUCCESS)
     - Authentication states (CAPTCHA_PAGE, OTP_VERIFICATION)
     - Challenge states (CLOUDFLARE_CHALLENGE, SESSION_EXPIRED, MAINTENANCE_PAGE)
     - Error states (ERROR_PAGE, RATE_LIMITED)
     - Fallback (UNKNOWN)

2. **`PageStateDetector` Class** (`src/resilience/page_state_detector.py`)
   - Main detection and recovery engine
   - Methods:
     - `detect(page)` - Detects current page state
     - `assert_state(page, expected)` - Asserts page is in expected state
     - `handle_state(page, state, context)` - Handles detected state with recovery
     - `handle_unexpected_state(page, actual, expected)` - Handles unexpected transitions

3. **`StateHandlerResult` Dataclass** (`src/resilience/page_state_detector.py`)
   - Result of state handling with:
     - `success` - Whether handling succeeded
     - `state` - The state that was handled
     - `next_state` - Expected next state (optional)
     - `action_taken` - Description of action
     - `should_retry` - Whether to retry the operation
     - `should_abort` - Whether to abort the flow

4. **Configuration** (`config/page_states.yaml`)
   - Defines page indicators for each state:
     - URL patterns
     - Text indicators
     - CSS selectors
     - Title patterns
     - HTTP status codes
   - Expected state transitions
   - Recovery strategies per state

### Integration Points

1. **ResilienceManager** (`src/resilience/manager.py`)
   - Optionally creates `PageStateDetector` when `enable_page_state_detection=True`
   - Provides it to dependent services
   - Parameters:
     - `enable_page_state_detection` - Enable/disable feature (default: False)
     - `page_states_file` - Path to config (default: "config/page_states.yaml")
     - `auth_service` - For re-login recovery
     - `cloudflare_handler` - For challenge handling
     - `notifier` - For alerts

2. **BookingWorkflow** (`src/services/bot/booking_workflow.py`)
   - Uses page state detector in `process_user()` if available
   - New method: `_handle_post_login_state()` for state-aware navigation
   - Falls back to legacy flow if detector disabled (backward compatible)

## Detection Priority

Page state detection follows this priority order:

1. **Cloudflare Challenge** (highest priority)
2. **Maintenance Page**
3. **Session Expired**
4. **CAPTCHA**
5. **OTP Verification**
6. **Waitlist Success**
7. **Waitlist Mode**
8. **Dashboard**
9. **Login Page**
10. **Unknown** (fallback)

This ensures critical blocking states are detected first.

## Recovery Strategies

Each state has a defined recovery strategy:

| State | Strategy | Actions |
|-------|----------|---------|
| SESSION_EXPIRED | re_login | Automatically re-login with saved credentials |
| CLOUDFLARE_CHALLENGE | cloudflare_handler | Call CloudflareHandler.handle_challenge() |
| CAPTCHA_PAGE | captcha_solver | Attempt automatic solving, notify if fails |
| MAINTENANCE_PAGE | wait_and_retry | Wait 5 minutes, then retry |
| RATE_LIMITED | exponential_backoff | Wait with increasing delays |
| UNKNOWN | forensic_capture_and_notify | Capture evidence + alert user |

## Usage

### Enabling Page State Detection

```python
from src.resilience import ResilienceManager

# Initialize with page state detection enabled
resilience_manager = ResilienceManager(
    enable_page_state_detection=True,
    auth_service=auth_service,
    cloudflare_handler=cloudflare_handler,
    notifier=notifier,
)

await resilience_manager.start()

# Access the detector
detector = resilience_manager.page_state_detector
```

### Detecting Page State

```python
# Detect current state
state = await detector.detect(page)
logger.info(f"Current state: {state.value}")

# Assert expected state
is_dashboard = await detector.assert_state(page, PageState.DASHBOARD)
if not is_dashboard:
    logger.warning("Not on dashboard!")
```

### Handling States with Recovery

```python
# Detect and handle
state = await detector.detect(page)
context = {
    "email": "user@example.com",
    "password": "password",
    "user_id": 123,
}

result = await detector.handle_state(page, state, context)

if result.should_abort:
    raise VFSBotError(f"Cannot continue: {result.action_taken}")

if result.should_retry:
    # Retry the operation
    pass
```

### In BookingWorkflow

The integration is automatic when `resilience_manager` has page state detection enabled:

```python
workflow = BookingWorkflow(
    config=config,
    db=db,
    resilience_manager=resilience_manager,  # Must have detector enabled
    # ... other dependencies
)

# The workflow will automatically:
# 1. Detect post-login state
# 2. Handle unexpected states (session expired, CAPTCHA, etc.)
# 3. Recover automatically when possible
# 4. Abort with clear errors when recovery fails
await workflow.process_user(page, user)
```

## Configuration

### Page Indicators (`config/page_states.yaml`)

Each state can be detected using multiple indicators:

```yaml
states:
  login_page:
    description: "Login/signin page"
    url_patterns:
      - "/login"
      - "/signin"
    text_indicators:
      - "Email"
      - "Password"
      - "Login"
    css_selectors:
      - "input[type='email']"
      - "input[type='password']"
    expected_transitions:
      - dashboard
      - otp_verification
    recovery_strategy: "none"
```

### Recovery Strategy Configuration

```yaml
recovery_strategies:
  re_login:
    description: "Automatically re-login with saved credentials"
    timeout: 30000
    retry_count: 2
  
  wait_and_retry:
    description: "Wait for maintenance to complete"
    wait_time: 300  # 5 minutes
    retry_count: 3
```

## State Transition Logging

All state transitions are logged for debugging:

```
📍 State transition: login_page
🔍 Page state detected: DASHBOARD
📍 State transition: dashboard
```

Transition history is stored in `detector.transition_history`:

```python
[
  {
    "timestamp": 1707766534.123,
    "state": "login_page",
    "context": {"user_id": 123}
  },
  {
    "timestamp": 1707766545.456,
    "state": "dashboard",
    "context": {"user_id": 123}
  }
]
```

## Error Handling

### Forensic Capture for Unknown States

When an unknown state is detected:

1. Screenshot captured
2. HTML source saved
3. Network logs saved (if available)
4. Notification sent to user
5. Operation aborted with clear error

```
❌ Unknown page state detected
📸 Forensic evidence captured
⚠️ Unknown page state encountered - URL: https://...
```

### Recovery Failures

If recovery fails:

```
⚠️ Session expired detected - triggering re-login
❌ Re-login failed
Action taken: Re-login failed
Should abort: True
```

## Testing

Comprehensive test suite in `tests/unit/test_page_state_detector.py`:

- **Initialization Tests**: Default config, custom config, service dependencies
- **Detection Tests**: Each state type, priority order, unknown states
- **Assertion Tests**: Success, failure, timeout behavior
- **Handler Tests**: Each recovery strategy, error cases, notifications
- **Transition Tests**: History tracking, context capture

Run tests:
```bash
pytest tests/unit/test_page_state_detector.py -v
```

## Backward Compatibility

The system is **fully backward compatible**:

1. **Default disabled**: `enable_page_state_detection=False` by default
2. **Legacy flow preserved**: When disabled, uses original waitlist detection
3. **Optional parameters**: All new parameters are optional
4. **Graceful degradation**: Missing services (auth_service, etc.) are handled

### Migration Path

1. **Phase 1**: Deploy with detection disabled (default)
2. **Phase 2**: Enable detection in development/staging
3. **Phase 3**: Monitor transition logs and adjust indicators
4. **Phase 4**: Enable in production with alerts
5. **Phase 5**: Tune recovery strategies based on real data

## Security Considerations

1. **Credentials in context**: User email/password passed in context for re-login
   - Only stored in memory during handling
   - Not logged (uses masked_email)

2. **Forensic capture**: Screenshots may contain sensitive data
   - Stored in secure logs directory
   - Access controlled via file permissions

3. **Notifications**: Alerts may contain URL information
   - Should not include credentials or tokens
   - Safe for external notification services

## Performance Impact

Minimal performance impact:

- **Detection**: ~100-500ms (depends on page complexity)
- **State handling**: Varies by strategy (re-login ~3-5s, Cloudflare ~30s)
- **Memory**: ~1KB per transition in history
- **No impact when disabled**: Zero overhead if `enable_page_state_detection=False`

## Future Enhancements

Potential improvements:

1. **ML-based detection**: Use machine learning to detect new states
2. **State prediction**: Predict next state based on history
3. **Auto-tuning**: Adjust wait times based on success rates
4. **Visual comparison**: Screenshot-based state detection
5. **State graph validation**: Validate transitions against expected paths
6. **Analytics dashboard**: Visualize state transitions over time

## Troubleshooting

### Detection not working

1. Check config file exists: `config/page_states.yaml`
2. Verify indicators match actual page elements
3. Check detection priority order
4. Enable debug logging: `logger.setLevel("DEBUG")`

### Recovery failing

1. Verify required services are provided (auth_service, cloudflare_handler)
2. Check credentials in context
3. Increase timeout values in config
4. Review forensic logs for actual error

### Unknown states appearing frequently

1. Review forensic screenshots to identify state
2. Add new state definition to `PageState` enum
3. Add indicators to `config/page_states.yaml`
4. Update detection logic if needed
5. Add tests for new state

## Example Scenarios

### Scenario 1: Session Expires During Booking

```
1. User logs in successfully
2. Bot navigates to appointment page
3. Session expires (timeout)
4. Detector identifies: SESSION_EXPIRED
5. Handler triggers: re_login
6. Auth service logs in again
7. Detector identifies: DASHBOARD
8. Flow continues normally
```

### Scenario 2: Cloudflare Challenge Appears

```
1. User navigates to login page
2. Cloudflare challenge appears
3. Detector identifies: CLOUDFLARE_CHALLENGE
4. Handler triggers: cloudflare_handler
5. CloudflareHandler.handle_challenge() waits for pass
6. Challenge passes
7. Detector identifies: LOGIN_PAGE
8. Flow continues normally
```

### Scenario 3: Maintenance Page

```
1. User attempts to access site
2. Maintenance page appears
3. Detector identifies: MAINTENANCE_PAGE
4. Handler triggers: wait_and_retry
5. Bot waits 5 minutes
6. Bot retries navigation
7. If still in maintenance, waits again
8. After max retries, aborts with notification
```

## References

- **Code**: `src/resilience/page_state_detector.py`
- **Config**: `config/page_states.yaml`
- **Tests**: `tests/unit/test_page_state_detector.py`
- **Integration**: `src/services/bot/booking_workflow.py`
- **Manager**: `src/resilience/manager.py`
