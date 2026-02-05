# Waitlist Automation Implementation

## Overview
This implementation adds automated waitlist handling to the VFS-Bot. When a country uses a waitlist system instead of direct appointments, the bot now automatically detects this and processes the waitlist registration flow.

## Features Implemented

### 1. Automatic Waitlist Detection
- **File**: `src/services/bot/waitlist_handler.py`
- **Function**: `detect_waitlist_mode()`
- Automatically detects if the current page is a waitlist page by searching for "Bekleme Listesi" or "Waitlist" text
- No manual configuration needed

### 2. Waitlist Registration Flow
The bot handles the complete waitlist registration flow:

1. **Application Details Screen**
   - Automatically checks the waitlist checkbox
   - Handles both Turkish and English labels
   - Validates checkbox state before clicking

2. **Review and Pay Screen**
   - Checks all three required checkboxes:
     - Terms and Conditions
     - Marketing consent
     - Waitlist consent
   - Uses robust selector fallback system

3. **Confirmation**
   - Clicks the "Onayla" (Confirm) button
   - Waits for success screen to load

4. **Success Screen Handling**
   - Takes full-page screenshot (saved to `screenshots/` folder)
   - Extracts key information:
     - Reference number
     - Person names
     - Country
     - Centre
     - Category
     - Subcategory
     - Total amount

### 3. Telegram Notifications
- **File**: `src/services/notification.py`
- **Function**: `notify_waitlist_success()`
- Sends comprehensive notification with:
  - Login email address
  - Reference number
  - List of all registered people
  - Full booking details
  - Screenshot attachment
  - Timestamp

**Sample Notification Format:**
```
✅ BEKLEME LİSTESİNE KAYIT BAŞARILI!

📧 Giriş Yapılan Hesap: user@example.com
📋 Referans: ABC123456

👥 Kayıt Yapılan Kişiler:
   1. John Doe
   2. Jane Doe

🌍 Ülke: Türkiye
📍 Merkez: Istanbul
📂 Kategori: Turist Vizesi
📁 Alt Kategori: 90 Gün

💰 Toplam Ücret: 200 EUR

📅 Tarih: 05.02.2026 15:15:08

ℹ️ Bekleme listesi durumunuz güncellendiğinde bilgilendirileceksiniz.

📸 [Ekran görüntüsü ekte]
```

## Files Modified/Created

### New Files
- `src/services/bot/waitlist_handler.py` - Complete waitlist flow handler
- `tests/test_waitlist.py` - Comprehensive test suite

### Modified Files
- `src/services/appointment_booking_service.py` - Added waitlist selectors to VFS_SELECTORS
- `src/services/notification.py` - Added waitlist notification methods
- `src/services/bot/vfs_bot.py` - Integrated waitlist detection and flow

## Selectors Added

```python
VFS_SELECTORS.update({
    # Waitlist checkbox (Application Details)
    "waitlist_checkbox": [
        "//mat-checkbox[.//span[contains(text(), 'Waitlist')]]",
        "//mat-checkbox[.//span[contains(text(), 'Bekleme Listesi')]]",
        "mat-checkbox:has-text('Waitlist')",
        "mat-checkbox:has-text('Bekleme Listesi')",
    ],
    
    # Review and Pay checkboxes
    "terms_consent_checkbox": [
        'input[value="consent.checkbox_value.vas_term_condition"]',
    ],
    "marketing_consent_checkbox": [
        'input[value="consent.checkbox_value.receive_mkt_info"]',
    ],
    "waitlist_consent_checkbox": [
        "mat-checkbox:has-text('bekleme listesi') input",
        "mat-checkbox:has-text('waitlist') input",
    ],
    
    # Confirm button
    "confirm_button": [
        'button:has(span.mdc-button__label:text("Onayla"))',
        'button:has-text("Onayla")',
        'button:has-text("Confirm")',
    ],
    
    # Success indicators
    "waitlist_success_indicator": [
        "text=Bekleme Listesinde",
        "text=İşlem Özeti",
        "text=Waitlist",
    ],
})
```

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User Login (Email stored for notification)              │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Detect Waitlist Mode                                    │
│    - Search for "Waitlist" or "Bekleme Listesi" text       │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
        ▼ YES                       ▼ NO
┌───────────────────┐         ┌──────────────────┐
│ WAITLIST FLOW     │         │ NORMAL FLOW      │
│                   │         │ (Slot checking)  │
│ 3. Check waitlist │         └──────────────────┘
│    checkbox       │
│                   │
│ 4. Click Continue │
│                   │
│ 5. Accept 3       │
│    checkboxes:    │
│    - Terms        │
│    - Marketing    │
│    - Waitlist     │
│                   │
│ 6. Click Confirm  │
│                   │
│ 7. Success Screen │
│    - Screenshot   │
│    - Extract data │
│                   │
│ 8. Send Telegram  │
│    notification   │
│    with screenshot│
└───────────────────┘
```

## Usage

No configuration changes needed! The bot automatically:

1. Detects waitlist mode when navigating to appointment pages
2. Routes to appropriate flow (waitlist vs. normal)
3. Handles the complete registration process
4. Sends notifications with all details

## Testing

Comprehensive test suite included in `tests/test_waitlist.py`:

- ✅ Waitlist mode detection (positive and negative cases)
- ✅ Checkbox selection handling
- ✅ Confirm button clicking
- ✅ Success screen detection
- ✅ Detail extraction from page
- ✅ Notification sending (with and without screenshot)
- ✅ Error handling for all steps

## Security

- ✅ CodeQL security scan passed (0 alerts)
- ✅ No hardcoded credentials
- ✅ Proper error handling
- ✅ Input validation on extracted data

## Known Limitations

1. **Name Extraction**: Uses regex pattern for Western naming conventions (Capitalized First Last). May not work correctly for:
   - Names with prefixes or suffixes
   - Multiple capitalized words
   - Non-Western naming patterns
   - **Workaround**: If name extraction fails, notification shows "(Information unavailable)"

2. **Form Filling**: Current implementation assumes personal details forms are pre-filled or handled by the VFS system. If manual form filling is required, that step needs to be added.

3. **Language Support**: Selectors support both Turkish and English, but notification messages are primarily in Turkish to match the target audience.

## Maintenance

When updating selectors:
1. Add new selectors to `VFS_SELECTORS` in `appointment_booking_service.py`
2. Use fallback arrays for robustness
3. Test with both Turkish and English VFS interfaces
4. Update tests in `test_waitlist.py` accordingly

## Future Enhancements

Potential improvements for future iterations:

1. Add support for form filling in waitlist flow
2. Enhance name extraction with ML-based approach
3. Add email notifications in addition to Telegram
4. Support for multiple screenshot intervals
5. Add retry logic for failed checkbox selections
6. Internationalization (i18n) for notification messages

## Support

For issues or questions about the waitlist feature:
1. Check logs in the bot output for detailed error messages
2. Verify screenshots are being saved to `screenshots/` folder
3. Confirm Telegram credentials are configured correctly
4. Review selector definitions if page structure changes
