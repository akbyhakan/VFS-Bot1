# VFS Global Integration - Browser-First with Test User API Mode

This document describes the dual-mode architecture for VFS Global integration.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        VFS-Bot Architecture                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  👤 NORMAL USER                                                 │
│     └── All operations via Playwright browser                   │
│         ├── Login & Cloudflare Turnstile                        │
│         ├── Slot checking                                       │
│         ├── Appointment booking                                 │
│         └── Human simulation (anti-detection)                   │
│                                                                  │
│  🧪 TEST USER (role: "tester")                                  │
│     └── All operations via direct API                           │
│         ├── Fast slot checking                                  │
│         ├── Fast appointment booking                            │
│         └── Frontend shows "⚡ API Mode" badge                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 🔑 Key Components

### 1. User Model (`src/models/user.py`)

Defines three user roles:
- **`admin`**: Administrative users
- **`user`**: Normal users (use browser automation)
- **`tester`**: Test users (use direct API)

```python
from src.models.user import User, UserRole

# Check if user uses direct API
if user.uses_direct_api:
    # Use VFSApiClient
else:
    # Use VFSBot (browser)
```

### 2. Countries Configuration (`src/core/countries.py`)

Supports all 21 Schengen countries:
- France (fra), Netherlands (nld), Austria (aut), Belgium (bel)
- Czech Republic (cze), Poland (pol), Sweden (swe), Switzerland (che)
- Finland (fin), Estonia (est), Latvia (lva), Lithuania (ltu)
- Luxembourg (lux), Malta (mlt), Norway (nor), Denmark (dnk)
- Iceland (isl), Slovenia (svn), Croatia (hrv), Bulgaria (bgr), Slovakia (svk)

```python
from src.core.countries import validate_mission_code, get_route

validate_mission_code("nld")  # Raises ValueError if invalid
route = get_route("fra")      # Returns "turkey/france"
```

### 3. VFS API Client (`src/services/vfs_api_client.py`)

Direct API client for test users only. Bypasses browser automation.

```python
from src.services.vfs_api_client import VFSApiClient

async with VFSApiClient(mission_code="nld", captcha_solver=solver) as client:
    await client.login(email, password, turnstile_token)
    slots = await client.check_slot_availability(centre_id, cat_id, subcat_id)
```

⚠️ **Warning**: Only test users should use this client!

### 4. Service Factory (`src/services/vfs_service_factory.py`)

Automatically selects the appropriate service based on user role:

```python
from src.services.vfs_service_factory import VFSServiceFactory

service = await VFSServiceFactory.create_service(
    user=user,
    config=config,
    captcha_solver=captcha_solver,
    db=db,              # Required for browser mode
    notifier=notifier   # Required for browser mode
)

# Returns VFSBot or VFSApiClient based on user.uses_direct_api
```

## 📊 Database Schema

The `users` table now includes a `role` column:

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    centre TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT NOT NULL,
    role TEXT DEFAULT 'user',           -- NEW: admin, user, or tester
    active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

The migration runs automatically when the database connects.

## 🛡️ Admin Routes

### Create Test User

**POST** `/admin/users/create-tester`

```bash
curl -X POST http://localhost:8000/admin/users/create-tester \
  -H "Content-Type: application/json" \
  -d '{
    "email": "tester@example.com",
    "password": "SecurePassword123",
    "centre": "Istanbul",
    "category": "National Visa",
    "subcategory": "Work"
  }'
```

Response:
```json
{
  "id": 42,
  "email": "tester@example.com",
  "role": "tester",
  "created_at": "2026-01-14T22:00:00"
}
```

### List Test Users

**GET** `/admin/users/testers`

```bash
curl http://localhost:8000/admin/users/testers
```

### Revoke Tester Role

**DELETE** `/admin/users/{user_id}/revoke-tester`

```bash
curl -X DELETE http://localhost:8000/admin/users/42/revoke-tester
```

## 🎨 Frontend Integration

The dashboard template (`web/templates/dashboard.html`) shows:

### API Mode Badge
```html
{% if user.is_tester %}
<span class="badge badge-api">⚡ API MODE</span>
{% else %}
<span class="badge badge-browser">🌐 Browser Mode</span>
{% endif %}
```

### Warning Banner
```html
{% if user.is_tester %}
<div class="test-warning-banner">
    ⚠️ <strong>TEST USER:</strong> This account uses direct API.
    All queries and bookings are done without browser.
    <em>For testing purposes only.</em>
</div>
{% endif %}
```

## 🔒 Security Considerations

1. **Test users can only be created by admins**
   - Regular users cannot elevate themselves to tester role
   - Admin authentication required for all admin endpoints

2. **Clear visual indicators**
   - API mode badge clearly shows when direct API is used
   - Warning banner reminds user of test mode

3. **Normal users always use browser**
   - Browser mode provides anti-detection features
   - Human simulation prevents bot detection
   - Cloudflare Turnstile handling

## 📝 Usage Examples

### Example 1: Check Slots with Factory

```python
from src.models.user import User, UserRole
from src.services.vfs_service_factory import VFSServiceFactory

# Normal user - uses browser
normal_user = User(
    id="1",
    email="user@example.com",
    password_hash="hash",
    role=UserRole.USER
)

service = await VFSServiceFactory.create_service(
    user=normal_user,
    config=config,
    captcha_solver=captcha_solver,
    db=db,
    notifier=notifier
)
# Returns VFSBot instance

# Test user - uses API
test_user = User(
    id="2",
    email="tester@example.com",
    password_hash="hash",
    role=UserRole.TESTER
)

service = await VFSServiceFactory.create_service(
    user=test_user,
    config=config,
    captcha_solver=captcha_solver
)
# Returns VFSApiClient instance
```

### Example 2: Multi-Country Check (Test Users Only)

```python
async with VFSApiClient(mission_code="nld", captcha_solver=solver) as client:
    # Check all 21 countries
    results = await client.check_all_countries(
        email="tester@example.com",
        password="password",
        turnstile_token="token"
    )
    
    for result in results:
        if result.available:
            print(f"{result.mission_code}: {len(result.dates)} slots available")
```

## ✅ Testing

Run tests:
```bash
pytest tests/test_countries.py -v
pytest tests/test_user_model.py -v
pytest tests/test_vfs_service_factory.py -v
```

All tests should pass with 100% coverage for new modules.

## 🚀 Migration Guide

If you have existing users in the database:

1. **Automatic migration**: The `role` column is added automatically with default value `'user'`
2. **No action needed**: Existing users continue working as normal users
3. **Create test users**: Use admin endpoint to create test users as needed

## 📚 API Reference

### UserRole Enum
- `UserRole.ADMIN = "admin"`
- `UserRole.USER = "user"`
- `UserRole.TESTER = "tester"`

### User Properties
- `user.is_tester` - Returns `True` if role is TESTER
- `user.uses_direct_api` - Returns `True` if should use direct API

### Factory Methods
- `VFSServiceFactory.create_service(...)` - Create appropriate service
- `VFSServiceFactory.get_service_type(user)` - Get "api" or "browser"

### Countries Functions
- `validate_mission_code(code)` - Validate mission code
- `get_route(code)` - Get VFS route for country
- `get_country_info(code)` - Get full country information
- `get_all_mission_codes()` - Get list of all supported countries
