# Page State Detection - Usage Examples

## Quick Start

### Basic Setup

```python
from src.resilience import ResilienceManager, PageState, PageStateDetector

# Create resilience manager with page state detection
resilience_manager = ResilienceManager(
    enable_page_state_detection=True,
    page_states_file="config/page_states.yaml",
)

# Start the manager
await resilience_manager.start()

# Get the detector
detector = resilience_manager.page_state_detector
```

### With Full Services Integration

```python
from src.resilience import ResilienceManager
from src.services.bot.auth_service import AuthService
from src.utils.anti_detection.cloudflare_handler import CloudflareHandler
from src.services.notification import NotificationService

# Initialize services
auth_service = AuthService(config)
cloudflare_handler = CloudflareHandler(config.get("cloudflare", {}))
notifier = NotificationService(config)

# Create resilience manager with all recovery services
resilience_manager = ResilienceManager(
    enable_page_state_detection=True,
    auth_service=auth_service,
    cloudflare_handler=cloudflare_handler,
    notifier=notifier,
)

await resilience_manager.start()
```

## Detection Examples

### Simple State Detection

```python
from playwright.async_api import async_playwright

async def check_page_state():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        await page.goto("https://visa.vfsglobal.com/login")
        
        # Detect current state
        state = await detector.detect(page)
        print(f"Current page state: {state.value}")
        
        await browser.close()

# Output: Current page state: login_page
```

### State Detection with Assertion

```python
async def login_and_verify():
    # ... browser setup ...
    
    await page.goto("https://visa.vfsglobal.com/login")
    
    # Fill login form
    await page.fill("input[type='email']", "user@example.com")
    await page.fill("input[type='password']", "password")
    await page.click("button[type='submit']")
    
    # Wait and verify we're on dashboard
    success = await detector.assert_state(
        page, 
        PageState.DASHBOARD, 
        timeout=10000  # 10 seconds
    )
    
    if success:
        print("✓ Successfully logged in")
    else:
        actual = await detector.detect(page)
        print(f"✗ Login failed - on {actual.value} instead")
```

### Detect and Log All State Changes

```python
async def monitor_navigation():
    # ... browser setup ...
    
    pages_to_visit = [
        "https://visa.vfsglobal.com/login",
        "https://visa.vfsglobal.com/dashboard",
        "https://visa.vfsglobal.com/appointment",
    ]
    
    for url in pages_to_visit:
        await page.goto(url)
        state = await detector.detect(page)
        print(f"URL: {url} → State: {state.value}")
```

## Recovery Examples

### Handle Session Expiry

```python
async def handle_expired_session(page, user_credentials):
    # Detect state
    state = await detector.detect(page)
    
    if state == PageState.SESSION_EXPIRED:
        print("⚠️ Session expired - attempting recovery...")
        
        context = {
            "email": user_credentials["email"],
            "password": user_credentials["password"],
        }
        
        result = await detector.handle_state(page, state, context)
        
        if result.success and result.should_retry:
            print("✓ Re-login successful - retrying operation")
            return True
        else:
            print(f"✗ Recovery failed: {result.action_taken}")
            return False
    
    return True  # Not expired
```

### Handle Cloudflare Challenge

```python
async def bypass_cloudflare(page):
    state = await detector.detect(page)
    
    if state == PageState.CLOUDFLARE_CHALLENGE:
        print("🔒 Cloudflare challenge detected")
        
        result = await detector.handle_state(page, state)
        
        if result.success:
            print(f"✓ Challenge bypassed: {result.action_taken}")
            return True
        else:
            print(f"✗ Failed to bypass: {result.action_taken}")
            return False
    
    return True  # No challenge
```

### Handle Maintenance Page

```python
async def wait_for_maintenance(page):
    state = await detector.detect(page)
    
    if state == PageState.MAINTENANCE_PAGE:
        print("🔧 Site under maintenance")
        
        # Custom wait time (default is 300s / 5 min)
        context = {"maintenance_wait_time": 60}  # 1 minute for testing
        
        result = await detector.handle_state(page, state, context)
        
        if result.should_retry:
            print(f"✓ Maintenance wait complete - retrying")
            return True
        else:
            print(f"✗ Maintenance timeout")
            return False
    
    return True  # No maintenance
```

### Handle CAPTCHA

```python
async def solve_captcha_if_present(page):
    state = await detector.detect(page)
    
    if state == PageState.CAPTCHA_PAGE:
        print("🔐 CAPTCHA detected")
        
        result = await detector.handle_state(page, state)
        
        if result.success:
            print("✓ CAPTCHA solved")
            return True
        else:
            # CAPTCHA solver failed - may need manual intervention
            print(f"⚠️ {result.action_taken}")
            return False
    
    return True  # No CAPTCHA
```

## Complete Workflow Example

### Full Booking Flow with State Detection

```python
async def complete_booking_flow(page, user):
    """Complete booking flow with automatic state recovery."""
    
    # Step 1: Navigate to login
    await page.goto("https://visa.vfsglobal.com/login")
    
    # Step 2: Detect and handle any challenges
    state = await detector.detect(page)
    if state == PageState.CLOUDFLARE_CHALLENGE:
        result = await detector.handle_state(page, state)
        if not result.success:
            raise Exception("Failed to bypass Cloudflare")
    
    # Step 3: Login
    await page.fill("input[type='email']", user["email"])
    await page.fill("input[type='password']", user["password"])
    await page.click("button[type='submit']")
    
    # Step 4: Verify post-login state
    state = await detector.detect(page)
    
    if state == PageState.SESSION_EXPIRED:
        # Handle session expiry
        context = {"email": user["email"], "password": user["password"]}
        result = await detector.handle_state(page, state, context)
        if not result.success:
            raise Exception("Session recovery failed")
        state = await detector.detect(page)
    
    if state == PageState.CAPTCHA_PAGE:
        # Handle CAPTCHA
        result = await detector.handle_state(page, state)
        if not result.success:
            raise Exception("CAPTCHA solving failed")
        state = await detector.detect(page)
    
    if state == PageState.OTP_VERIFICATION:
        # Wait for OTP (would integrate with OTP service)
        print("Waiting for OTP...")
        # ... OTP handling logic ...
        state = await detector.detect(page)
    
    # Step 5: Proceed based on state
    if state == PageState.DASHBOARD:
        print("✓ On dashboard - proceeding with normal flow")
        # ... normal booking flow ...
    
    elif state == PageState.WAITLIST_MODE:
        print("✓ Waitlist mode detected - using waitlist flow")
        # ... waitlist flow ...
    
    elif state == PageState.UNKNOWN:
        # Unknown state - capture and abort
        result = await detector.handle_state(page, state)
        raise Exception(f"Unknown state: {result.action_taken}")
    
    else:
        print(f"⚠️ Unexpected state: {state.value}")
        # Try to handle unexpected state
        result = await detector.handle_unexpected_state(
            page, state, PageState.DASHBOARD
        )
        if result.should_abort:
            raise Exception(f"Cannot proceed: {result.action_taken}")
```

## Advanced Usage

### Custom State Detection Loop

```python
async def wait_for_specific_state(page, expected_state, max_attempts=10):
    """Wait for page to reach expected state with retries."""
    
    for attempt in range(max_attempts):
        state = await detector.detect(page)
        
        if state == expected_state:
            return True
        
        # Handle recoverable states
        if state in [
            PageState.SESSION_EXPIRED,
            PageState.CLOUDFLARE_CHALLENGE,
            PageState.MAINTENANCE_PAGE,
        ]:
            result = await detector.handle_state(page, state)
            if result.should_abort:
                return False
            # Retry detection after recovery
            continue
        
        # Wait before next attempt
        await asyncio.sleep(2)
    
    return False
```

### State Transition Validation

```python
async def validate_state_transition(page, from_state, to_state, action_fn):
    """Validate that an action causes expected state transition."""
    
    # Verify starting state
    current = await detector.detect(page)
    if current != from_state:
        print(f"⚠️ Warning: Expected {from_state.value}, got {current.value}")
    
    # Perform action
    await action_fn(page)
    
    # Verify ending state
    result = await detector.assert_state(page, to_state, timeout=5000)
    
    if result:
        print(f"✓ Transition successful: {from_state.value} → {to_state.value}")
        return True
    else:
        actual = await detector.detect(page)
        print(f"✗ Unexpected transition: {from_state.value} → {actual.value}")
        print(f"   Expected: {to_state.value}")
        return False
```

### Review Transition History

```python
def analyze_user_journey():
    """Analyze the user's journey through different states."""
    
    history = detector.transition_history
    
    print(f"\n📊 User Journey Analysis ({len(history)} transitions):")
    print("=" * 60)
    
    for i, transition in enumerate(history, 1):
        state = transition["state"]
        timestamp = transition.get("timestamp", 0)
        context = transition.get("context", {})
        
        print(f"{i}. {state}")
        print(f"   Time: {timestamp}")
        if context:
            print(f"   Context: {context}")
        print()
    
    # Calculate state distribution
    from collections import Counter
    state_counts = Counter(t["state"] for t in history)
    
    print("\n📈 State Distribution:")
    for state, count in state_counts.most_common():
        print(f"   {state}: {count} times")
```

## Integration with BookingWorkflow

### Enable in BookingWorkflow

```python
from src.services.bot.booking_workflow import BookingWorkflow

# Create workflow with state detection enabled
workflow = BookingWorkflow(
    config=config,
    db=db,
    notifier=notifier,
    auth_service=auth_service,
    slot_checker=slot_checker,
    booking_service=booking_service,
    waitlist_handler=waitlist_handler,
    error_handler=error_handler,
    slot_analyzer=slot_analyzer,
    session_recovery=session_recovery,
    resilience_manager=resilience_manager,  # Must have detector enabled
)

# The workflow will automatically use page state detection
await workflow.process_user(page, user)
```

### Disable State Detection (Legacy Mode)

```python
# Create resilience manager WITHOUT state detection
resilience_manager = ResilienceManager(
    enable_page_state_detection=False,  # Disabled
)

workflow = BookingWorkflow(
    # ... all parameters ...
    resilience_manager=resilience_manager,
)

# Will use legacy waitlist detection instead
await workflow.process_user(page, user)
```

## Testing Examples

### Unit Test Example

```python
import pytest
from unittest.mock import AsyncMock
from src.resilience import PageState, PageStateDetector

@pytest.mark.asyncio
async def test_detect_login_page():
    # Mock page
    page = AsyncMock()
    page.url = "https://example.com/login"
    page.title = AsyncMock(return_value="Login")
    
    # Create detector
    detector = PageStateDetector()
    
    # Detect state
    state = await detector.detect(page)
    
    # Assert
    assert state == PageState.LOGIN_PAGE
```

### Integration Test Example

```python
@pytest.mark.asyncio
async def test_session_expiry_recovery():
    # Setup
    page = AsyncMock()
    auth_service = AsyncMock()
    auth_service.login = AsyncMock(return_value=True)
    
    detector = PageStateDetector(auth_service=auth_service)
    
    # Mock session expired page
    page.url = "https://example.com/login"
    page.title = AsyncMock(return_value="Session Expired")
    locator = AsyncMock()
    locator.count = AsyncMock(return_value=1)
    page.locator = lambda x: locator
    
    # Detect and handle
    state = await detector.detect(page)
    assert state == PageState.SESSION_EXPIRED
    
    context = {"email": "test@example.com", "password": "password"}
    result = await detector.handle_state(page, state, context)
    
    # Verify recovery
    assert result.success is True
    assert result.should_retry is True
    auth_service.login.assert_called_once()
```

## Troubleshooting Examples

### Debug Detection Issues

```python
async def debug_detection(page):
    """Debug why detection isn't working."""
    
    # Get page info
    url = page.url
    title = await page.title()
    content = await page.content()
    
    print(f"URL: {url}")
    print(f"Title: {title}")
    print(f"Content length: {len(content)} chars")
    
    # Try detection
    state = await detector.detect(page)
    print(f"\nDetected state: {state.value}")
    
    # Show which indicators matched
    for state_key, indicators in detector.indicators.items():
        matches = []
        
        # Check URL patterns
        for pattern in indicators.get("url_patterns", []):
            if pattern.lower() in url.lower():
                matches.append(f"URL: {pattern}")
        
        # Check title patterns
        for pattern in indicators.get("title_patterns", []):
            if pattern.lower() in title.lower():
                matches.append(f"Title: {pattern}")
        
        if matches:
            print(f"\n{state_key} matched:")
            for match in matches:
                print(f"  - {match}")
```

### Monitor Real-Time State Changes

```python
async def monitor_states(page, duration=60):
    """Monitor page state changes in real-time."""
    
    import asyncio
    from datetime import datetime
    
    last_state = None
    start_time = asyncio.get_event_loop().time()
    
    while asyncio.get_event_loop().time() - start_time < duration:
        current_state = await detector.detect(page)
        
        if current_state != last_state:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] State changed: {current_state.value}")
            last_state = current_state
        
        await asyncio.sleep(1)  # Check every second
```
