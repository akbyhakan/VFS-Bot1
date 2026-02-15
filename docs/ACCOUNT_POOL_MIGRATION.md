# Account Pool Migration Guide

## Overview

This guide explains how to migrate from the old 1:1 user-to-VFS-account model to the new shared account pool architecture.

## What Changed

### Before (Old Architecture)
- Each row in the `users` table represented both a VFS login account AND an appointment request
- User's email/password were used to log in to VFS portal
- 1 user = 1 VFS account (tight coupling)

### After (New Architecture)
- VFS login accounts are stored in the `vfs_account_pool` table (decoupled)
- Appointment requests exist independently in `appointment_requests` table
- N accounts can serve M appointment requests with intelligent rotation
- Accounts have cooldown periods and quarantine on failures

## Migration Steps

### 1. Run Database Migration

```bash
# Apply the migration
alembic upgrade head
```

This creates two new tables:
- `vfs_account_pool`: Stores VFS login accounts
- `account_usage_log`: Tracks account usage for monitoring

### 2. Populate Account Pool

You need to populate the account pool with VFS login credentials. You can:

**Option A: Migrate existing user credentials**
```sql
-- Copy active users to account pool (one-time migration)
INSERT INTO vfs_account_pool (email, password, phone)
SELECT DISTINCT email, password, 
       COALESCE(pd.mobile_number, '+1234567890') as phone
FROM users u
LEFT JOIN personal_details pd ON u.id = pd.user_id
WHERE u.active = TRUE
ON CONFLICT (email) DO NOTHING;
```

**Option B: Add accounts manually via SQL**
```sql
-- Add individual accounts (password will be encrypted automatically by repository layer)
-- Note: Use the repository's create_account method to ensure proper encryption
```

**Option C: Use Python script**
```python
from src.repositories.account_pool_repository import AccountPoolRepository
from src.models.database import Database

async def populate_pool():
    db = Database(database_url="postgresql://...")
    await db.connect()
    
    repo = AccountPoolRepository(db)
    
    accounts = [
        {"email": "vfs1@example.com", "password": "pass1", "phone": "+1234567890"},
        {"email": "vfs2@example.com", "password": "pass2", "phone": "+1234567891"},
        # ... more accounts
    ]
    
    for account in accounts:
        await repo.create_account(**account)
    
    await db.close()
```

### 3. Configure Account Pool Settings (Optional)

Edit `src/constants.py` to adjust pool behavior:

```python
class AccountPoolConfig:
    COOLDOWN_SECONDS: Final[int] = 600  # 10 minutes (adjust as needed)
    QUARANTINE_SECONDS: Final[int] = 1800  # 30 minutes
    MAX_FAILURES: Final[int] = 3  # Failures before quarantine
    MAX_CONCURRENT_MISSIONS: Final[int] = 5  # Parallel processing limit
```

### 4. Verify Migration

Check pool status:
```python
from src.services.account_pool import AccountPool
from src.models.database import Database

async def check_pool():
    db = Database(database_url="postgresql://...")
    await db.connect()
    
    pool = AccountPool(db)
    status = await pool.get_pool_status()
    
    print(f"Total active accounts: {status['total_active']}")
    print(f"Available now: {status['available']}")
    print(f"In cooldown: {status['in_cooldown']}")
    print(f"Quarantined: {status['quarantined']}")
    
    await db.close()
```

## How It Works

### Session Flow

1. **Session Start**: SessionOrchestrator groups pending appointment requests by mission (country)
2. **Account Acquisition**: For each mission, acquires an account using LRU + cooldown strategy
3. **Processing**: Uses acquired account to log in and check slots
4. **Account Release**: Returns account to pool with status:
   - Success/No slot → Cooldown (10 min default)
   - Login failure → Increment failures, quarantine if >= 3
   - Banned → Extended quarantine (60 min)

### Account Selection (LRU + Cooldown)

```
Priority order:
1. Filter: status = 'available' AND cooldown_until < NOW()
2. Exclude: quarantine_until > NOW()
3. Sort: last_used_at ASC (least recently used first)
4. Select: First available account
```

### Example: 6 Accounts, 2 Missions

```
Session 1: France→Acc1, Belgium→Acc2 (both no_slot → cooldown)
Session 2: France→Acc3 (SUCCESS!), Belgium→Acc4 (no_slot → cooldown)
Session 3: Belgium→Acc5 (no_slot → cooldown)
Session 4: Belgium→Acc6 (no_slot → cooldown)
Session 5: All in cooldown → WAIT until Acc1 cooldown expires
Session 6: Belgium→Acc1 (LRU, cooldown expired)
```

## Monitoring

### Check Account Pool Status

```bash
# Via database
SELECT status, COUNT(*) 
FROM vfs_account_pool 
WHERE is_active = TRUE 
GROUP BY status;

# Check quarantined accounts
SELECT id, email, consecutive_failures, quarantine_until
FROM vfs_account_pool
WHERE status = 'quarantine' AND quarantine_until > NOW()
ORDER BY quarantine_until;
```

### View Usage History

```bash
SELECT 
    a.email,
    COUNT(*) as total_uses,
    COUNT(CASE WHEN l.result = 'success' THEN 1 END) as successes,
    COUNT(CASE WHEN l.result = 'no_slot' THEN 1 END) as no_slots,
    COUNT(CASE WHEN l.result = 'login_fail' THEN 1 END) as login_fails
FROM account_usage_log l
JOIN vfs_account_pool a ON l.account_id = a.id
WHERE l.created_at > NOW() - INTERVAL '24 hours'
GROUP BY a.email
ORDER BY total_uses DESC;
```

## Backward Compatibility

The old `process_user()` method is still available but NOT used by the main bot loop. If you have custom code that calls `process_user()` directly, it will continue to work.

The `users` table and user management web API are unchanged. Users are now for appointment request management, not VFS login credentials.

## Troubleshooting

### No available accounts
```
Pool status: 0 available, 5 in cooldown, 2 quarantined
```

**Solution**: Wait for cooldowns to expire, or add more accounts to the pool.

### All accounts quarantined
```
Pool status: 0 available, 0 in cooldown, 10 quarantined
```

**Cause**: Too many login failures (check VFS portal for issues, verify passwords)

**Solution**: 
1. Wait for quarantine to expire (default 30 min)
2. Or manually reset: `UPDATE vfs_account_pool SET status='available', consecutive_failures=0, quarantine_until=NULL WHERE status='quarantine'`

### High failure rate
Check `account_usage_log` for patterns:
```sql
SELECT result, COUNT(*) 
FROM account_usage_log 
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY result;
```

Common causes:
- VFS portal issues
- Incorrect credentials
- Rate limiting / IP bans

## Rollback (Emergency)

If you need to rollback:

```bash
# Revert database migration
alembic downgrade -1

# Revert code changes
git revert <commit-hash>
```

Note: This loses account usage history but preserves users and appointment requests.

## FAQ

**Q: Can I use both old and new architecture?**
A: No, choose one. The bot loop uses either user-based (old) or pool-based (new) processing.

**Q: What happens to my existing users?**
A: They remain unchanged. Users are now for appointment requests, not VFS logins.

**Q: How many accounts should I have in the pool?**
A: Minimum: Number of concurrent missions + buffer. Recommended: 2-3x your peak concurrent load.

**Q: Can I manually release a quarantined account?**
A: Yes, via SQL: `UPDATE vfs_account_pool SET status='available', consecutive_failures=0, quarantine_until=NULL WHERE id=<account_id>`

**Q: How do I add new accounts to the pool?**
A: Use `AccountPoolRepository.create_account()` method to ensure proper password encryption.
