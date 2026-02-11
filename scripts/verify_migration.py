#!/usr/bin/env python3
"""Verify logging migration from stdlib to loguru."""

import os
import re
from pathlib import Path

# Files that should be fully migrated
FULLY_MIGRATED = [
    "main.py",
    "src/core/startup.py",
    "src/core/shutdown.py",
    "src/core/runners.py",
    "src/core/config_version_checker.py",
    "src/core/startup_validator.py",
    "src/core/auth.py",
    "src/models/database.py",
    "src/models/db_factory.py",
    "src/utils/token_utils.py",
    "src/utils/secure_memory.py",
    "src/utils/webhook_utils.py",
    "src/utils/idempotency.py",
    "src/utils/ai_selector_repair.py",
    "src/utils/anti_detection/fingerprint_bypass.py",
    "src/utils/security/rate_limiter.py",
    "src/utils/security/adaptive_rate_limiter.py",
    "src/utils/security/endpoint_rate_limiter.py",
    "src/utils/security/session_manager.py",
    "src/services/booking/form_filler.py",
    "src/services/bot/vfs_bot.py",
    "src/utils/metrics.py",
    "src/services/notification.py",
    "src/services/otp_webhook.py",
    "src/services/otp_manager/sms_handler.py",
    "src/services/otp_manager/session_registry.py",
    "src/selector/watcher.py",
    "src/core/config_validator.py",
]

# Files with special handling
SPECIAL_CASES = {
    "src/core/retry.py": "stdlib logging for tenacity",
    "src/core/monitoring.py": "stdlib logging for Sentry",
    "src/utils/request_context.py": "stdlib logging for Filter/Logger classes",
}

def check_file(filepath):
    """Check if a file is properly migrated."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    has_loguru = 'from loguru import logger' in content
    # Match both 'import logging' and 'import logging as ...'
    has_stdlib_import = re.search(r'^import logging(\s|$)', content, re.MULTILINE)
    has_getlogger = 'logging.getLogger' in content
    
    return has_loguru, has_stdlib_import, has_getlogger

print("=" * 70)
print("LOGGING MIGRATION VERIFICATION")
print("=" * 70)

print("\n📋 FULLY MIGRATED FILES (should have loguru, no getLogger):")
print("-" * 70)

issues = []
for filepath in FULLY_MIGRATED:
    if not os.path.exists(filepath):
        print(f"❌ {filepath} - FILE NOT FOUND")
        issues.append(filepath)
        continue
    
    has_loguru, has_stdlib, has_getlogger = check_file(filepath)
    
    status = "✅"
    msg = "OK"
    
    if not has_loguru:
        status = "❌"
        msg = "Missing loguru import"
        issues.append(f"{filepath}: {msg}")
    elif has_stdlib:
        status = "⚠️ "
        msg = "Has stdlib logging import"
        issues.append(f"{filepath}: {msg}")
    elif has_getlogger:
        status = "❌"
        msg = "Still has getLogger calls"
        issues.append(f"{filepath}: {msg}")
    
    print(f"{status} {filepath:60} {msg}")

print("\n📋 SPECIAL CASE FILES (partial migration):")
print("-" * 70)

for filepath, reason in SPECIAL_CASES.items():
    if not os.path.exists(filepath):
        print(f"❌ {filepath} - FILE NOT FOUND")
        issues.append(filepath)
        continue
    
    has_loguru, has_stdlib, has_getlogger = check_file(filepath)
    
    # Special cases should have BOTH loguru and stdlib (except request_context)
    if filepath == "src/utils/request_context.py":
        # This one should NOT have loguru (only stdlib)
        if has_loguru:
            status = "⚠️ "
            msg = f"Unexpectedly has loguru ({reason})"
        else:
            status = "✅"
            msg = f"Correctly kept stdlib only ({reason})"
    else:
        # retry.py and monitoring.py should have BOTH
        if has_loguru and has_stdlib:
            status = "✅"
            msg = f"Correctly has both ({reason})"
        else:
            status = "❌"
            msg = f"Missing loguru or stdlib ({reason})"
            issues.append(f"{filepath}: {msg}")
    
    print(f"{status} {filepath:60} {msg}")

print("\n" + "=" * 70)
if issues:
    print(f"❌ FOUND {len(issues)} ISSUE(S):")
    for issue in issues:
        print(f"   - {issue}")
    print("=" * 70)
    exit(1)
else:
    print("✅ ALL FILES MIGRATED CORRECTLY!")
    print("=" * 70)
    exit(0)
