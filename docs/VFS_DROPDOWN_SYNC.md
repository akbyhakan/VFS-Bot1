# VFS Dropdown Synchronization Feature

## Overview

This feature dynamically fetches and caches VFS dropdown data (centres, visa categories, and subcategories) from the VFS website, eliminating hardcoded values and ensuring the frontend always displays accurate, up-to-date options.

## Architecture

### Database Schema

A new table `vfs_dropdown_cache` stores dropdown data for all supported countries:

```sql
CREATE TABLE vfs_dropdown_cache (
    id SERIAL PRIMARY KEY,
    country_code VARCHAR(3) NOT NULL UNIQUE,
    dropdown_data JSONB NOT NULL,
    last_synced_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

The `dropdown_data` JSONB field stores the complete hierarchy:
```json
{
  "Istanbul": {
    "Tourism": ["Short Stay", "Long Stay"],
    "Business": ["Single Entry", "Multiple Entry"]
  },
  "Ankara": {
    "Tourism": ["Short Stay"],
    "Business": ["Single Entry"]
  }
}
```

### Backend Components

#### 1. DropdownCacheRepository (`src/repositories/dropdown_cache_repository.py`)

Repository for CRUD operations on the cache table:
- `get_dropdown_data(country_code)` - Fetch all dropdown data for a country
- `upsert_dropdown_data(country_code, data)` - Store/update dropdown data
- `get_centres(country_code)` - Get list of centres
- `get_categories(country_code, centre_name)` - Get categories for a centre
- `get_subcategories(country_code, centre_name, category_name)` - Get subcategories

#### 2. DropdownSyncService (`src/services/dropdown_sync.py`)

Service to sync dropdown data from VFS website:
- Uses existing `CentreFetcher` to fetch data
- `sync_country_dropdowns(page, country_code)` - Sync single country
- `sync_all_countries(browser, email, password)` - Sync all supported countries
- Handles login, navigation, and data extraction

#### 3. API Endpoints (`web/routes/appointments.py`)

New/updated endpoints:
- `GET /api/countries/{country_code}/centres` - Get centres (updated to use cache)
- `GET /api/countries/{country_code}/centres/{centre_name}/categories` - Get categories
- `GET /api/countries/{country_code}/centres/{centre_name}/categories/{category_name}/subcategories` - Get subcategories

### Frontend Components

#### 1. Hooks (`frontend/src/hooks/useAppointmentRequest.ts`)

New React Query hooks:
```typescript
useCategories(countryCode, centreName)
useSubcategories(countryCode, centreName, categoryName)
```

#### 2. UI Updates (`frontend/src/pages/AppointmentRequest.tsx`)

Added two new dropdown fields:
- **Visa Category**: Appears after selecting centre(s)
- **Visa Subcategory**: Appears after selecting category

Features:
- Cascading dependencies (changing country resets centres, categories, subcategories)
- Form validation for required fields
- Loading states while fetching data

## Usage

### Manual Sync (Admin)

To manually sync dropdown data for all countries:

```python
from src.services.dropdown_sync import DropdownSyncService
from src.models.database import Database

async def sync_dropdowns():
    db = Database()
    await db.connect()
    
    service = DropdownSyncService(db)
    
    # Use Playwright to sync all countries
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        results = await service.sync_all_countries(
            browser,
            account_email="your_vfs_email",
            account_password="your_password"
        )
        await browser.close()
    
    print(f"Sync results: {results}")
```

### Automated Sync (Startup)

Add to application startup (in `main.py` or similar):

```python
from src.services.dropdown_sync import DropdownSyncService
import asyncio

@app.on_event("startup")
async def startup_sync():
    # Run sync in background task
    asyncio.create_task(sync_dropdowns_background())

async def sync_dropdowns_background():
    # Check if cache is stale (e.g., older than 24 hours)
    # If stale, run sync_dropdowns()
    pass
```

## Migration

Run the migration to create the cache table:

```bash
make db-upgrade
# or
alembic upgrade head
```

## Benefits

1. **Accuracy**: Always shows current VFS dropdown options
2. **Performance**: Cached data reduces API calls to VFS
3. **Flexibility**: Easy to add new countries or update existing ones
4. **User Experience**: Cascading dropdowns guide users through the selection process
5. **Maintainability**: No hardcoded lists to update manually

## Limitations

1. **Initial Sync Required**: Cache must be populated before frontend can use it
2. **VFS Account Needed**: Sync requires valid VFS credentials
3. **Rate Limiting**: Syncing all countries may trigger rate limits (use delays)
4. **SPA Constraint**: CentreFetcher requires page to be on appointment page already

## Future Enhancements

1. Add background job to auto-sync daily
2. Add admin API endpoint to trigger manual sync
3. Add cache invalidation/refresh mechanism
4. Add monitoring for stale cache entries
5. Add fallback to VFS API if cache is empty
