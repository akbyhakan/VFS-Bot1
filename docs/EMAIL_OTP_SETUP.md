# Microsoft 365 Email OTP Setup Guide

This guide explains how to configure Microsoft 365 App Password for the Email OTP Handler.

## Overview

The Email OTP Handler uses IMAP to monitor a catch-all email mailbox for OTP codes sent to various bot email addresses. Since all emails are routed to a single mailbox (e.g., `admin@yourdomain.com`), the system analyzes email headers to determine the intended recipient.

## Prerequisites

- Microsoft 365 Business or Enterprise account
- Admin access to configure mail flow rules
- Domain with MX records pointing to Microsoft 365

## Step 1: Configure Catch-All Email (Internal Relay)

### 1.1 Configure Domain as Internal Relay

1. Go to **Microsoft 365 Admin Center** → **Exchange admin center**
2. Navigate to **Mail flow** → **Accepted domains**
3. Select your domain (e.g., `yourdomain.com`)
4. Change domain type to **Internal relay**
5. Save changes

### 1.2 Create Mail Flow Rule

1. In Exchange admin center, go to **Mail flow** → **Rules**
2. Click **Add a rule** → **Create a new rule**
3. Configure the rule:
   - **Name**: "Catch-all to Main Mailbox"
   - **Apply this rule if**: The recipient domain is `yourdomain.com`
   - **AND**: The recipient address includes any of these words: `bot`, `vize-` (customize as needed)
   - **Do the following**: Redirect the message to `admin@yourdomain.com` (your catch-all mailbox)
4. Save the rule

> **Note**: This configuration routes all emails sent to undefined addresses (like `bot1@yourdomain.com`, `bot2@yourdomain.com`) to the main catch-all mailbox.

## Step 2: Generate App Password

Microsoft 365 requires App Passwords for applications using basic authentication (IMAP).

### 2.1 Enable Multi-Factor Authentication (if not enabled)

1. Go to **Microsoft 365 Admin Center**
2. Navigate to **Users** → **Active users**
3. Select the user (`akby.hakan@vizecep.com`)
4. Click **Manage multi-factor authentication**
5. Enable MFA for the user

### 2.2 Create App Password

1. Visit [Microsoft Account Security](https://account.microsoft.com/security)
2. Sign in with your Microsoft 365 account
3. Navigate to **Security** → **Advanced security options**
4. Under **App passwords**, click **Create a new app password**
5. Enter a name (e.g., "VFS Bot IMAP")
6. Click **Create**
7. **Copy the generated password** (format: `xxxx-xxxx-xxxx-xxxx`)

> ⚠️ **Important**: Save this password immediately. You cannot view it again after closing the dialog.

### 2.3 Verify IMAP is Enabled

1. Go to **Exchange admin center**
2. Navigate to **Recipients** → **Mailboxes**
3. Select your catch-all mailbox (e.g., `admin@yourdomain.com`)
4. Click **Manage email apps settings**
5. Ensure **IMAP** is checked/enabled
6. Save changes

## Step 3: Configure Environment Variables

Add the following variables to your `.env` file:

```bash
# Microsoft 365 Email OTP Configuration
M365_EMAIL=admin@yourdomain.com
M365_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx  # Replace with your actual app password
```

## Step 4: Test Configuration

### 4.1 Basic Connection Test

```python
from src.services.otp_manager.email_otp_handler import EmailOTPHandler

# Initialize handler
handler = EmailOTPHandler(
    email="admin@yourdomain.com",
    app_password="your-app-password-here"
)

# Test will connect to IMAP server
print("✓ IMAP connection successful")
handler.close()
```

### 4.2 Test OTP Reception

1. Send a test email to one of your bot addresses:
   ```
   To: bot1@yourdomain.com
   Subject: Test OTP
   Body: Your verification code is: 123456
   ```

2. Wait for OTP using the handler:
   ```python
   otp = handler.wait_for_otp("bot1@yourdomain.com", timeout=120)
   if otp:
       print(f"✓ OTP received: {otp}")
   else:
       print("✗ OTP not received within timeout")
   ```

## Step 5: Usage in Bot Sessions

### Single Bot Session

```python
from src.services.otp_manager.email_otp_handler import EmailOTPHandler
import os

handler = EmailOTPHandler(
    email=os.getenv("M365_EMAIL"),
    app_password=os.getenv("M365_APP_PASSWORD")
)

# Wait for OTP for specific bot
otp = handler.wait_for_otp("bot1@yourdomain.com", timeout=120)
if otp:
    # Use OTP for authentication
    print(f"Received OTP: {otp}")
```

### Multiple Concurrent Bot Sessions

```python
from src.services.otp_manager.email_otp_handler import get_email_otp_handler
import threading
import os

# Initialize global handler once
handler = get_email_otp_handler(
    email=os.getenv("M365_EMAIL"),
    app_password=os.getenv("M365_APP_PASSWORD")
)

def bot_session(bot_id):
    bot_email = f"bot{bot_id}@yourdomain.com"
    print(f"Bot {bot_id} waiting for OTP...")
    
    otp = handler.wait_for_otp(bot_email, timeout=120)
    if otp:
        print(f"Bot {bot_id} received OTP")
    else:
        print(f"Bot {bot_id} OTP timeout")

# Start multiple bot sessions
threads = []
for i in range(1, 6):
    t = threading.Thread(target=bot_session, args=(i,))
    threads.append(t)
    t.start()

# Wait for all bots
for t in threads:
    t.join()
```

## Troubleshooting

### Issue: IMAP Authentication Failed

**Solution**:
- Verify app password is correct
- Ensure IMAP is enabled for the mailbox
- Check that MFA is enabled for the account

### Issue: No Emails Received

**Solution**:
- Verify mail flow rule is active
- Check Exchange message trace to see if emails are being delivered
- Ensure domain is configured as Internal Relay

### Issue: Wrong OTP Returned

**Solution**:
- Check that target email filtering is working correctly
- Verify email headers contain proper "To", "Delivered-To", or "X-Original-To" fields
- Review logs for header parsing issues

### Issue: Timeout Errors

**Solution**:
- Increase `otp_timeout_seconds` parameter
- Decrease `poll_interval_seconds` for more frequent checks
- Verify network connectivity to `outlook.office365.com:993`

### Issue: SSL/TLS Errors

**Solution**:
- Ensure Python SSL certificates are up to date
- Check firewall rules allow outbound IMAP/SSL (port 993)
- Verify system date/time is correct

## Advanced Configuration

### Custom IMAP Server

If using a different IMAP server:

```python
from src.services.otp_manager.email_otp_handler import EmailOTPHandler, IMAPConfig

config = IMAPConfig(
    host="imap.custom.com",
    port=993,
    use_ssl=True,
    folder="INBOX"
)

handler = EmailOTPHandler(
    email="user@custom.com",
    app_password="password",
    imap_config=config
)
```

### Custom OTP Patterns

If OTP format is different:

```python
custom_patterns = [
    r"Your PIN is (\d{6})",
    r"Verification: (\d{6})"
]

handler = EmailOTPHandler(
    email=os.getenv("M365_EMAIL"),
    app_password=os.getenv("M365_APP_PASSWORD"),
    custom_patterns=custom_patterns
)
```

### Adjust Timeouts

```python
handler = EmailOTPHandler(
    email=os.getenv("M365_EMAIL"),
    app_password=os.getenv("M365_APP_PASSWORD"),
    otp_timeout_seconds=180,      # Wait up to 3 minutes
    poll_interval_seconds=3,       # Check every 3 seconds
    max_email_age_seconds=600      # Only consider emails from last 10 minutes
)
```

## Security Considerations

1. **Never commit app passwords** to source control
2. **Store app passwords** in environment variables or secure vaults
3. **Rotate app passwords** periodically
4. **Use separate mailbox** for OTP handling (don't use personal mailbox)
5. **Monitor access logs** for unusual activity
6. **Enable audit logging** in Microsoft 365 admin center

## Reference

- [Microsoft 365 App Passwords](https://support.microsoft.com/en-us/account-billing/using-app-passwords-with-apps-that-don-t-support-two-step-verification-5896ed9b-4263-e681-128a-a6f2979a7944)
- [Exchange Mail Flow Rules](https://learn.microsoft.com/en-us/exchange/security-and-compliance/mail-flow-rules/mail-flow-rules)
- [IMAP Protocol](https://www.rfc-editor.org/rfc/rfc3501.html)
