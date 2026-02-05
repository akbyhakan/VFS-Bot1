# VFS-Bot Maintenance-Free Automation Features

## Overview

This document describes the new maintenance-free automation features added to VFS-Bot. These features significantly reduce the need for manual configuration and monitoring, making the bot more intelligent and self-managing.

## Features

### 1. 🌐 Country-Based Automatic Configuration

**File:** `config/country_profiles.yaml`  
**Service:** `src/services/country_profile_loader.py`

Automatically configures bot behavior based on the target country. Each country has a profile with:

- **Name**: Turkish and English country names
- **Timezone**: Local timezone for accurate scheduling
- **Language**: Primary language code
- **Retry Multiplier**: How aggressive the bot should be (higher = more frequent checks)

**Supported Countries:** 21 European countries including Netherlands, Germany, France, UK, Italy, and more.

**Usage Example:**
```python
from src.services.country_profile_loader import CountryProfileLoader

loader = CountryProfileLoader()
profile = loader.get_profile('nld')  # Get Netherlands profile
timezone = loader.get_timezone('nld')
multiplier = loader.get_retry_multiplier('nld')
```

**Benefits:**
- No need to manually configure timezone or retry settings
- Country-specific optimizations (e.g., Netherlands has 1.5x multiplier for faster checks)
- Easy to add new countries by editing the YAML file

---

### 2. ⏰ Adaptive Scheduler

**Service:** `src/services/adaptive_scheduler.py`

Automatically adjusts check intervals based on time of day to optimize resource usage and appointment availability patterns.

**Schedule Modes:**

| Mode   | Hours (Turkey Time) | Interval Range | Description |
|--------|---------------------|----------------|-------------|
| Peak   | 8-9, 14-15         | 15-30 sec      | Aggressive mode for high-activity hours |
| Normal | 10-13, 16-18       | 45-60 sec      | Standard checking frequency |
| Low    | 19-23, 00          | 90-120 sec     | Reduced activity hours |
| Sleep  | 1-7                | 10-15 min      | Minimal checks during night |

**Features:**
- Timezone-aware scheduling
- Country multiplier support (faster checks for high-demand countries)
- Randomized intervals to avoid detection
- Minimum 10-second interval enforced

**Usage Example:**
```python
from src.services.adaptive_scheduler import AdaptiveScheduler

scheduler = AdaptiveScheduler(
    timezone="Europe/Amsterdam",
    country_multiplier=1.5
)

# Get optimal interval based on current time
interval = scheduler.get_optimal_interval()

# Check current mode
if scheduler.is_sleep_mode():
    print("Bot is in sleep mode")
```

**Integration:**
The scheduler is automatically integrated into the bot's main loop in `vfs_bot.py`:
```python
check_interval = self.scheduler.get_optimal_interval()
await asyncio.sleep(check_interval)
```

---

### 3. 📅 Slot Pattern Analyzer

**Service:** `src/services/slot_analyzer.py`  
**Data File:** `data/slot_patterns.json` (auto-created)

Tracks and analyzes when appointment slots become available to identify patterns.

**Features:**
- Records every found slot with metadata (time, date, centre, category)
- Analyzes patterns over configurable time periods
- Generates weekly reports for Telegram notifications
- Identifies best hours, best days, and most active centres

**Tracked Metrics:**
- Hour of day when slots are found
- Day of week patterns
- Centre-specific availability
- Average slots per day

**Usage Example:**
```python
from src.services.slot_analyzer import SlotPatternAnalyzer

analyzer = SlotPatternAnalyzer()

# Record a found slot
analyzer.record_slot_found(
    country="nld",
    centre="Amsterdam",
    category="Tourism",
    date="2024-02-15",
    time="10:00"
)

# Generate weekly report
report = analyzer.generate_weekly_report()
# Send report via Telegram
```

**Sample Report:**
```
📊 **VFS-Bot Haftalık Slot Raporu**

📈 **Son 7 Günde:**
• Toplam slot bulundu: 42
• Günlük ortalama: 6.0

⏰ **En İyi Saatler:**
  • 9:00 - 15 slot
  • 14:00 - 12 slot
  • 8:00 - 10 slot

📅 **En İyi Günler:**
  • Monday - 18 slot
  • Wednesday - 14 slot
  • Friday - 10 slot

🏢 **En Aktif Merkezler:**
  • Amsterdam - 20 slot
  • Rotterdam - 15 slot
  • The Hague - 7 slot
```

---

### 4. 🔄 Session Recovery

**Service:** `src/services/session_recovery.py`  
**Checkpoint File:** `data/session_checkpoint.json` (auto-created)

Allows the bot to recover and continue from the last successful step if it crashes or is interrupted.

**Checkpoint Steps:**
1. initialized
2. logged_in
3. centre_selected
4. category_selected
5. date_selected
6. waitlist_detected
7. waitlist_joined
8. personal_info_filled
9. review_page
10. checkboxes_accepted
11. payment_started
12. payment_completed
13. completed

**Features:**
- Automatic checkpoint saving at each major step
- 1-hour expiration for stale checkpoints
- Context preservation (user data, selected options)
- Resume capability checking

**Usage Example:**
```python
from src.services.session_recovery import SessionRecovery

recovery = SessionRecovery()

# Save checkpoint after login
recovery.save_checkpoint(
    step="logged_in",
    user_id=123,
    context={"email": "user@example.com"}
)

# On bot restart, check if we can resume
if recovery.can_resume_from("logged_in"):
    checkpoint = recovery.load_checkpoint()
    # Resume from checkpoint
    context = recovery.get_resume_context()
    
# Clear checkpoint after successful completion
recovery.clear_checkpoint()
```

**Benefits:**
- No need to restart from scratch after crashes
- Saves time and reduces duplicate login attempts
- Preserves user selections and form data

---

### 5. 🧠 Selector Self-Healing

**Service:** `src/services/selector_self_healing.py`  
**Log File:** `data/selector_healing_log.json` (auto-created)

Automatically detects and fixes broken CSS/XPath selectors when website structure changes.

**How It Works:**
1. Detects when a selector fails
2. Generates alternative selector candidates based on element description
3. Scores each candidate using confidence metrics (0.0 - 1.0)
4. Selects candidate with score ≥ 80% confidence
5. Updates `config/selectors.yaml` with new fallback selector
6. Logs the healing operation for review

**Confidence Scoring:**
- Single element: +0.4
- Multiple elements (2-3): +0.2
- Visible: +0.3
- Enabled: +0.2
- Text match: +0.1

**Selector Strategies:**
- Text content matching
- Email input: `input[type='email']`, `input[name*='email']`, etc.
- Password input: `input[type='password']`, `input[name*='password']`, etc.
- Buttons: `button[type='submit']`, `button:has-text('Submit')`, etc.

**Usage Example:**
```python
from src.services.selector_self_healing import SelectorSelfHealing

healing = SelectorSelfHealing()

# Attempt to heal a broken selector
new_selector = await healing.attempt_heal(
    page=playwright_page,
    selector_path="login.email_input",
    failed_selector="input#old-email-id",
    element_description="email input field"
)

if new_selector:
    # Use the healed selector
    await page.fill(new_selector, email)
```

**Benefits:**
- Reduces maintenance when VFS website changes
- Automatic fallback selector generation
- Audit trail of all selector changes
- No manual intervention required for minor UI changes

---

## Integration

All services are automatically initialized in `VFSBot.__init__()` through the `_init_automation_services()` method:

```python
def _init_automation_services(self) -> None:
    """Initialize maintenance-free automation services."""
    # Country profile loader
    self.country_profiles = CountryProfileLoader()
    
    # Get country from config
    country_code = self.config.get("vfs", {}).get("country", "tur")
    
    # Adaptive scheduler with country-specific settings
    self.scheduler = AdaptiveScheduler(
        timezone=self.country_profiles.get_timezone(country_code),
        country_multiplier=self.country_profiles.get_retry_multiplier(country_code)
    )
    
    # Slot pattern analyzer
    self.slot_analyzer = SlotPatternAnalyzer()
    
    # Selector self-healing
    self.self_healing = SelectorSelfHealing()
    
    # Session recovery
    self.session_recovery = SessionRecovery()
```

## Data Files

All data files are automatically created in the `data/` directory (which is gitignored):

- `data/slot_patterns.json` - Slot availability patterns
- `data/session_checkpoint.json` - Session recovery checkpoint
- `data/selector_healing_log.json` - Self-healing audit log

## Testing

Comprehensive tests are provided for all services:

- `tests/test_country_profile_loader.py` - Country profile loading
- `tests/test_adaptive_scheduler.py` - Scheduling logic
- `tests/test_slot_analyzer.py` - Pattern analysis
- `tests/test_session_recovery.py` - Checkpoint management
- `tests/test_selector_self_healing.py` - Selector healing

Run tests with:
```bash
pytest tests/test_country_profile_loader.py -v
pytest tests/test_adaptive_scheduler.py -v
pytest tests/test_slot_analyzer.py -v
pytest tests/test_session_recovery.py -v
pytest tests/test_selector_self_healing.py -v
```

## Benefits Summary

✅ **Reduced Manual Configuration**
- Country-specific settings loaded automatically
- No need to manually tune retry intervals

✅ **Intelligent Resource Management**
- Adaptive scheduling reduces unnecessary checks
- Optimizes for peak appointment release times

✅ **Better Insights**
- Pattern analysis reveals best times to check
- Weekly reports help users understand slot availability

✅ **Improved Reliability**
- Session recovery reduces wasted work
- Self-healing selectors adapt to website changes

✅ **Lower Maintenance**
- Bot adapts to time zones and country differences
- Automatic selector fallback reduces downtime

## Future Enhancements

Potential improvements for future versions:

1. **Machine Learning Integration**
   - Predict slot release times based on historical patterns
   - Dynamic retry multiplier adjustment

2. **Multi-Country Support**
   - Run bot for multiple countries simultaneously
   - Cross-country pattern comparison

3. **Advanced Self-Healing**
   - AI-powered selector generation (already supports Google Gemini)
   - Visual element matching

4. **Enhanced Analytics**
   - Success rate tracking per centre
   - Performance metrics dashboard

---

**Last Updated:** 2024-02-05  
**Version:** 1.0
