# Token Synchronization Implementation

## Overview

This implementation addresses three interconnected token management issues in the VFS-Bot codebase:

1. **SessionManager runs idle** - `set_tokens()` was never called in production
2. **Two isolated token systems** - SessionManager and VFSApiClient had no communication
3. **No proactive token refresh** - Tokens were refreshed reactively only when expired

## Solution Architecture

### TokenSyncService

A new service (`src/services/token_sync_service.py`) that bridges SessionManager and VFSApiClient:

```python
# Initialize
token_sync = TokenSyncService(
    session_manager=session_manager,  # Optional, None if anti-detection disabled
    token_refresh_buffer_minutes=5    # Default from TOKEN_REFRESH_BUFFER_MINUTES env var
)

# Sync tokens after login or refresh
token_sync.sync_from_vfs_session(vfs_api_client.session)

# Check if proactive refresh is needed
if token_sync.should_proactive_refresh(vfs_api_client.session):
    # Token will expire within buffer period
    await token_sync.ensure_fresh_token(vfs_api_client)
```

### Key Features

1. **Token Synchronization**
   - Syncs tokens from VFSApiClient.VFSSession to SessionManager
   - Maintains consistency between two token systems
   - Handles cases where SessionManager is None (anti-detection disabled)

2. **Proactive Refresh**
   - Checks if token will expire within configurable buffer (default: 5 minutes)
   - Triggers refresh before expiry to prevent delays at critical moments
   - Uses `should_proactive_refresh()` to determine when refresh is needed

3. **Error Handling**
   - Gracefully handles None values and missing attributes
   - Logs warnings for recoverable errors
   - Returns False on refresh failures for caller to handle

## Integration Points

### Service Context
TokenSyncService is integrated into `AntiDetectionContext`:

```python
# In BotServiceFactory.create_anti_detection()
token_sync = TokenSyncService(
    session_manager=session_manager,
    token_refresh_buffer_minutes=session_config.get("token_refresh_buffer", 5),
)
```

### SessionManager
Added convenience method for direct token sync:

```python
# Direct sync without TokenSyncService
session_manager.sync_from_api_client(vfs_session)
```

### VFSBot
- Removed misleading `is_token_expired()` check that always returned True
- Added `token_sync` property for backward compatibility
- Ready for future VFSApiClient integration

## Usage Examples

### Example 1: Sync after login
```python
# After successful VFSApiClient login
await vfs_api_client.login(email, password, turnstile_token)

# Sync tokens to SessionManager
token_sync.sync_from_vfs_session(vfs_api_client.session)
```

### Example 2: Proactive refresh in bot loop
```python
# Before processing users
if vfs_api_client.session:
    if token_sync.should_proactive_refresh(vfs_api_client.session):
        success = await token_sync.ensure_fresh_token(vfs_api_client)
        if not success:
            logger.error("Failed to refresh token proactively")
```

### Example 3: Anti-detection disabled
```python
# TokenSyncService handles None SessionManager gracefully
token_sync = TokenSyncService(session_manager=None)
token_sync.sync_from_vfs_session(vfs_session)  # Logs debug, does nothing
```

## Configuration

### Environment Variables
- `TOKEN_REFRESH_BUFFER_MINUTES`: Minutes before expiry to trigger proactive refresh (default: 5)

### Bot Configuration
```yaml
session:
  save_file: "data/session.json"
  token_refresh_buffer: 5  # Minutes
```

## Testing

Comprehensive test coverage (23 tests in `tests/test_token_sync_service.py`):

- Token sync from VFSApiClient to SessionManager
- Proactive refresh logic with buffer period
- Error handling for None values and exceptions
- Integration scenarios
- SessionManager sync_from_api_client convenience method (6 tests)

All 118 related tests pass successfully.

## Future Enhancements

1. **VFSApiClient Integration**: When VFSApiClient is integrated into production bot loop:
   - Call `token_sync.sync_from_vfs_session()` after login
   - Use `token_sync.ensure_fresh_token()` before critical operations
   - Monitor token expiry and refresh proactively

2. **Token Refresh Callbacks**: Set up hooks to automatically sync after:
   - `VFSApiClient.login()` succeeds
   - `VFSApiClient._refresh_token()` succeeds

3. **Metrics and Monitoring**:
   - Track proactive vs reactive token refreshes
   - Monitor token sync failures
   - Alert on repeated refresh failures

## Backward Compatibility

All changes are backward compatible:
- Existing code continues to work unchanged
- New features are opt-in
- SessionManager behavior unchanged (except for new sync method)
- VFSBot behavior unchanged (removed useless check, no functional change)

## Security Considerations

- TokenSyncService does not store or log sensitive token data
- All token handling follows existing SessionManager encryption patterns
- Proactive refresh reduces token expiry at critical moments
- No changes to token validation or authentication logic
