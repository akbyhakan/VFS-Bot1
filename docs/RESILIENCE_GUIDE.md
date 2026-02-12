# Resilience System Guide

The VFS Bot resilience system transforms the bot into an **anti-fragile** system that benefits from VFS Global frontend changes rather than breaking. When self-healing fails, it provides forensic-grade incident reports for debugging.

## 🎯 Overview

The resilience module (`src/resilience/`) provides:

1. **3-Stage Selector Resolution**: Semantic → CSS (with learning) → AI repair
2. **Hot-Reload**: File-polling based selector updates without bot restart
3. **Forensic Logging**: Country-aware black box logging with screenshots and masked data
4. **AI-Powered Repair**: Structured output using Pydantic models
5. **Country-Aware**: All features respect country-specific configurations

## 📦 Architecture

```
src/resilience/
├── manager.py          # ResilienceManager - central orchestrator
├── smart_wait.py       # SmartWait - 3-stage pipeline
├── hot_reload.py       # HotReloadableSelectorManager
├── forensic_logger.py  # ForensicLogger - black box logging
└── ai_repair_v2.py     # AIRepairV2 - structured AI repair
```

## 🚀 Quick Start

### Basic Usage

```python
from src.resilience import ResilienceManager

# Initialize for a specific country
resilience = ResilienceManager(
    country_code="fra",
    enable_ai_repair=True,
    enable_hot_reload=True,
)

# Start lifecycle (starts hot-reload watcher)
await resilience.start()

# Find elements with full resilience
locator = await resilience.find_element(
    page, 
    "login.email_input",
    timeout=10000,
    action_context="filling email during login"
)

# Convenience methods
await resilience.safe_click(page, "login.submit_button")
await resilience.safe_fill(page, "login.email", "user@example.com")
await resilience.safe_select(page, "appointment.centre", "London")

# Manual reload if needed
resilience.reload_selectors()

# Check status
status = resilience.get_status()
print(f"Reload count: {status['selector_manager']['reload_count']}")
print(f"Total incidents: {status['forensic_logger']['total_incidents']}")

# Stop lifecycle (stops hot-reload watcher)
await resilience.stop()
```

### Integration with BookingWorkflow

```python
from src.resilience import ResilienceManager
from src.services.bot import BookingWorkflow

# Create resilience manager
resilience = ResilienceManager(country_code="fra")
await resilience.start()

# Pass to BookingWorkflow
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
    resilience_manager=resilience,  # ← New parameter
)
```

## 🔍 Component Details

### 1. ResilienceManager

Central orchestrator for all resilience features.

```python
from src.resilience import ResilienceManager

manager = ResilienceManager(
    selectors_file="config/selectors.yaml",  # Path to selectors
    country_code="fra",                       # Country code
    logs_dir="logs/errors",                   # Forensic logs base dir
    enable_ai_repair=True,                    # Enable AI repair
    enable_hot_reload=True,                   # Enable hot-reload
    hot_reload_interval=5.0,                  # Poll interval (seconds)
)
```

**Key Methods:**
- `start()` - Start hot-reload watcher
- `stop()` - Stop hot-reload watcher
- `find_element()` - Full 3-stage pipeline
- `safe_click()`, `safe_fill()`, `safe_select()` - Convenience methods
- `reload_selectors()` - Manual reload trigger
- `get_status()` - Comprehensive status

### 2. SmartWait (3-Stage Pipeline)

Intelligent selector resolution with automatic fallback.

**Stage 1: Semantic Locators** (Most Resilient)
```yaml
# config/selectors.yaml
defaults:
  login:
    submit_button:
      semantic:
        role: button
        text: "Continue"
      primary: "#login-submit"
      fallbacks:
        - "button[type='submit']"
```

Playwright semantic locators are tested first:
- `role` - ARIA role (button, link, textbox, etc.)
- `text` - Visible text content
- `label` - Associated label text
- `placeholder` - Placeholder attribute

**Stage 2: CSS Selectors with Learning**

Tries CSS selectors with:
- Learning-based ordering (most successful selectors first)
- Exponential backoff retry (3 attempts by default)
- Success/failure tracking

**Stage 3: AI Repair**

When all CSS selectors fail:
1. Captures current page HTML
2. Sanitizes sensitive data (scripts, values, tokens)
3. Sends to Gemini AI with structured output
4. Validates AI suggestion
5. Auto-updates `selectors.yaml`
6. Reloads selectors

### 3. HotReloadableSelectorManager

File-polling based hot-reload without bot restart.

```python
from src.resilience import HotReloadableSelectorManager

manager = HotReloadableSelectorManager(
    country_code="fra",
    selectors_file="config/selectors.yaml",
    poll_interval=5.0,  # Check every 5 seconds
)

# Start watching
await manager.start_watching()

# File changes are detected automatically
# Selectors are reloaded when mtime or size changes

# Check status
status = manager.get_status()
print(f"Reload count: {status['reload_count']}")
print(f"Watching: {status['is_watching']}")

# Stop watching
await manager.stop_watching()
```

**Change Detection:**
- Monitors file modification time (mtime)
- Monitors file size
- Reloads when either changes
- Thread-safe async implementation

### 4. ForensicLogger (Black Box)

Country-aware incident capture with comprehensive diagnostics.

```python
from src.resilience import ForensicLogger

logger = ForensicLogger(
    base_dir="logs/errors",
    country_code="fra",
    max_incidents=500,           # Max incidents to retain
    max_html_size=5_000_000,     # Max HTML dump size (5MB)
)

# Capture incident
incident = await logger.capture_incident(
    page=page,
    error=exception,
    context={"step": "login", "action": "click_submit"},
    tried_selectors=["#submit", "button[type='submit']"],
)
```

**Incident Structure:**
```
logs/errors/fra/2024-02-15/
├── 20240215_143022_123456_screenshot.png  # Full-page screenshot
├── 20240215_143022_123456_dom.html        # Raw DOM dump
└── 20240215_143022_123456_context.json    # Masked context
```

**Context JSON Contents:**
```json
{
  "id": "20240215_143022_123456",
  "timestamp": "2024-02-15T14:30:22.123456+00:00",
  "country_code": "fra",
  "error_type": "SelectorNotFoundError",
  "error_message": "Element not found",
  "tried_selectors": ["#submit", "button[type='submit']"],
  "page_context": {
    "url": "https://example.com",
    "title": "Login Page",
    "viewport": {"width": 1920, "height": 1080},
    "cookies": [
      {"name": "session", "value": "[MASKED]", "domain": ".example.com"}
    ],
    "localStorage": {
      "token": "[MASKED]"
    },
    "sessionStorage": {
      "user_data": "[MASKED]"
    },
    "traceback": ["..full traceback.."]
  }
}
```

**Retrieval:**
```python
# Get recent incidents
recent = logger.get_recent_incidents(limit=10)

# Get specific incident
incident = logger.get_incident_by_id("20240215_143022_123456")

# Get status
status = logger.get_status()
```

### 5. AIRepairV2 (Structured Output)

AI-powered selector repair with Pydantic validation.

```python
from src.resilience import AIRepairV2, RepairResult

# Initialize (requires GEMINI_API_KEY environment variable)
repair = AIRepairV2(
    selectors_file="config/selectors.yaml",
    model_name="gemini-2.0-flash-exp",
    temperature=0.1,  # Deterministic output
)

# Repair selector
result = await repair.repair_selector(
    html_content="<html>...",
    broken_selector="#old-email",
    element_description="Email input field",
)

if result and result.is_found:
    print(f"Suggested: {result.new_selector}")
    print(f"Confidence: {result.confidence}")
    print(f"Reason: {result.reason}")
    
    # Auto-update YAML
    repair.persist_to_yaml("login.email_input", result.new_selector)
```

**RepairResult Model:**
```python
class RepairResult(BaseModel):
    is_found: bool              # Was selector found?
    new_selector: str           # CSS selector
    confidence: float           # 0.0-1.0
    reason: str                 # Explanation
```

**Structured Output:**
- Uses JSON schema for deterministic responses
- Filters by confidence threshold (default: 0.7)
- Sanitizes HTML before sending to LLM
- Graceful degradation when API unavailable

## 🌍 Country-Aware Features

All resilience features respect country configuration:

```python
# France configuration
resilience_fra = ResilienceManager(country_code="fra")

# Netherlands configuration
resilience_nld = ResilienceManager(country_code="nld")
```

**Country-Aware Aspects:**
1. **Selector Resolution**: Country-specific selectors override defaults
2. **Forensic Logs**: `logs/errors/fra/` vs `logs/errors/nld/`
3. **Learning Metrics**: `data/selector_metrics_fra.json` vs `data/selector_metrics_nld.json`
4. **Status Reporting**: Country code in all status responses

## ⚙️ Configuration

### Constants (`src/constants.py`)

```python
class Resilience:
    HOT_RELOAD_INTERVAL: Final[float] = 5.0
    SMART_WAIT_MAX_RETRIES: Final[int] = 3
    SMART_WAIT_BACKOFF_FACTOR: Final[float] = 1.5
    AI_REPAIR_CONFIDENCE_THRESHOLD: Final[float] = 0.7
    AI_REPAIR_MAX_HTML_SIZE: Final[int] = 50_000
    FORENSIC_MAX_INCIDENTS: Final[int] = 500
    FORENSIC_MAX_HTML_SIZE: Final[int] = 5_000_000
```

### Environment Variables

```bash
# Required for AI repair
GEMINI_API_KEY=your_api_key_here
```

### Selectors YAML

```yaml
version: "2024.02"

defaults:
  login:
    email_input:
      semantic:                  # Stage 1
        role: textbox
        label: "Email"
      primary: "#mat-input-0"    # Stage 2 (first try)
      fallbacks:                 # Stage 2 (fallbacks)
        - "input[type='email']"
        - "#email-field"

countries:
  fra:
    login:
      email_input:
        primary: "#email-fra"    # Country-specific override
```

## 📊 Monitoring & Debugging

### Status Monitoring

```python
status = resilience.get_status()

# Overall status
print(f"Country: {status['country_code']}")
print(f"AI Repair: {status['ai_repair_enabled']}")
print(f"Hot Reload: {status['enable_hot_reload']}")

# Selector manager
sm = status['selector_manager']
print(f"Watching: {sm['is_watching']}")
print(f"Reload count: {sm['reload_count']}")
print(f"File exists: {sm['file_exists']}")

# Forensic logger
fl = status['forensic_logger']
print(f"Total incidents: {fl['total_incidents']}")
print(f"Max incidents: {fl['max_incidents']}")
```

### Incident Analysis

```python
# Get recent failures
incidents = resilience.forensic_logger.get_recent_incidents(limit=5)

for incident in incidents:
    print(f"ID: {incident['id']}")
    print(f"Error: {incident['error_type']}")
    print(f"Tried: {incident['tried_selectors']}")
    print(f"Screenshot: {incident['captures']['screenshot']}")
    print(f"DOM: {incident['captures']['dom']}")
    print(f"Context: {incident['captures']['context']}")
```

## 🧪 Testing

```python
import pytest
from src.resilience import ResilienceManager

@pytest.mark.asyncio
async def test_resilience_manager():
    manager = ResilienceManager(country_code="fra")
    
    # Test lifecycle
    await manager.start()
    assert manager.selector_manager.is_watching
    
    await manager.stop()
    assert not manager.selector_manager.is_watching
    
    # Test status
    status = manager.get_status()
    assert status['country_code'] == 'fra'
```

## 🚨 Error Handling

```python
from src.core.exceptions import SelectorNotFoundError

try:
    locator = await resilience.find_element(page, "login.email")
except SelectorNotFoundError as e:
    # Error already logged to forensic logger
    print(f"Selector not found: {e.selector_name}")
    print(f"Tried selectors: {e.tried_selectors}")
    
    # Get forensic incident
    incidents = resilience.forensic_logger.get_recent_incidents(limit=1)
    incident = incidents[0]
    
    # Analyze failure
    print(f"Screenshot: {incident['captures']['screenshot']}")
    print(f"DOM: {incident['captures']['dom']}")
```

## 🎯 Best Practices

1. **Always use country codes**: Initialize ResilienceManager with correct country
2. **Enable hot-reload in production**: Allows fixes without bot restart
3. **Monitor forensic logs**: Regular review helps identify UI change patterns
4. **Set GEMINI_API_KEY**: Enables Stage 3 AI repair
5. **Use semantic locators**: Add `semantic` to frequently failing selectors
6. **Clean up old incidents**: ForensicLogger auto-cleans, but monitor disk usage
7. **Test with manual reload**: Verify hot-reload works with `reload_selectors()`
8. **Check confidence scores**: AI suggestions below 0.7 are rejected

## 📚 Related Documentation

- [MODULAR_ARCHITECTURE.md](./MODULAR_ARCHITECTURE.md) - Overall architecture
- [COUNTRY_SELECTOR_SYSTEM.md](./COUNTRY_SELECTOR_SYSTEM.md) - Country-aware selectors
- [Pydantic Documentation](https://docs.pydantic.dev/) - Structured output validation
- [Gemini API Documentation](https://ai.google.dev/docs) - AI repair backend

## 🔮 Future Enhancements

- [ ] Webhook notifications for incidents
- [ ] Dashboard for incident visualization
- [ ] ML-based selector prediction
- [ ] Multi-model AI repair (GPT-4, Claude)
- [ ] Automated issue creation on GitHub
- [ ] Selector versioning and rollback
- [ ] Performance metrics (Stage 1/2/3 success rates)
