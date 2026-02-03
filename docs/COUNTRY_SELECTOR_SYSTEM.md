# Country-Aware Selector System

## Overview

The VFS Bot now supports country-specific CSS selectors, allowing different selector configurations for different VFS Global country websites. This is particularly useful because VFS Global's websites can have different HTML structures across different countries.

## Features

- **Country-Specific Overrides**: Define selectors specific to each country
- **Automatic Fallback**: Falls back to global defaults when no country-specific selector exists
- **Combined Fallbacks**: Merges country-specific and global fallback selectors (no duplicates)
- **Separate Metrics**: Each country tracks selector performance independently
- **Factory Pattern**: Efficient instance caching per country
- **Backward Compatible**: Existing code works without modification

## Configuration

### YAML Structure

The `config/selectors.yaml` file now has a hierarchical structure:

```yaml
version: "2024.02"
last_updated: "2026-01-24"

# Global default selectors (used by all countries)
defaults:
  login:
    email_input:
      primary: "input#mat-input-0"
      fallbacks:
        - "input[type='email']"
        - "input[name='email']"
      semantic:
        role: "textbox"
        label_en: "Email"
  # ... more default selectors

# Country-specific overrides
countries:
  fra:  # France
    login:
      email_input:
        primary: "input#fra-specific-email"
        fallbacks:
          - "input.france-email"
  nld:  # Netherlands
    appointment:
      centre_dropdown:
        primary: "select#nld-centres"
  # ... more countries
```

### Supported Countries

The system supports all 21 VFS Global Schengen countries:
- `fra` (France)
- `nld` (Netherlands)
- `aut` (Austria)
- `bel` (Belgium)
- `cze` (Czech Republic)
- `pol` (Poland)
- `swe` (Sweden)
- `che` (Switzerland)
- `fin` (Finland)
- `est` (Estonia)
- `lva` (Latvia)
- `ltu` (Lithuania)
- `lux` (Luxembourg)
- `mlt` (Malta)
- `nor` (Norway)
- `dnk` (Denmark)
- `isl` (Iceland)
- `svn` (Slovenia)
- `hrv` (Croatia)
- `bgr` (Bulgaria)
- `svk` (Slovakia)

## Usage

### Basic Usage

```python
from src.utils.selectors import get_selector_manager

# Get selector manager for France
manager = get_selector_manager("fra")

# Get a selector (country-specific if available, otherwise default)
email_selector = manager.get("login.email_input")

# Get selector with all fallbacks
all_selectors = manager.get_with_fallback("login.email_input")
```

### Integration with VFS Service

```python
from src.utils.selectors import get_selector_manager

class VFSService:
    def __init__(self, config: Dict[str, Any]):
        # Get country code from config
        self.country_code = config.get("vfs", {}).get("mission", "default")
        
        # Get country-specific selector manager
        self.selector_manager = get_selector_manager(self.country_code)
```

### Backward Compatibility

The old API still works:

```python
from src.utils.selectors import SelectorManager

# This still works (uses default country)
manager = SelectorManager()
selector = manager.get("login.email_input")

# This also works (loads from custom file)
manager = SelectorManager("path/to/selectors.yaml")
```

## Selector Priority

When retrieving a selector, the system follows this priority order:

1. **Country-Specific Primary**: `countries.{country}.{path}.primary`
2. **Country-Specific Fallbacks**: `countries.{country}.{path}.fallbacks`
3. **Global Default Primary**: `defaults.{path}.primary`
4. **Global Default Fallbacks**: `defaults.{path}.fallbacks`
5. **Provided Default**: The default parameter passed to `get()`

## Metrics Tracking

Each country maintains its own metrics file for learning selector performance:

```
data/
├── selector_metrics_default.json
├── selector_metrics_fra.json
├── selector_metrics_nld.json
└── ...
```

This allows the learning system to:
- Track which selectors work best for each country independently
- Auto-promote successful fallbacks per country
- Avoid cross-country interference in performance metrics

## Example: Adding France-Specific Selectors

If the France VFS website has different selectors, add them to the YAML:

```yaml
countries:
  fra:
    login:
      email_input:
        primary: "input#email-fr"
        fallbacks:
          - "input[name='courriel']"
          - "input.email-francais"
      submit_button:
        primary: "button#connexion"
```

Now when using `get_selector_manager("fra")`, these France-specific selectors will be used first, with automatic fallback to defaults if they fail.

## Benefits

### For Different Country Websites
- **Flexibility**: Each country can have completely different selectors
- **Resilience**: Falls back to global defaults if country-specific fails
- **Maintenance**: Only override what's different per country

### For Learning System
- **Accurate Tracking**: Each country's selector performance tracked separately
- **Better Optimization**: Learning adapts to each country's specific HTML structure
- **No Interference**: Changes in one country don't affect others

### For Development
- **Easy Testing**: Test with different countries easily
- **Gradual Migration**: Add country overrides as needed, not all at once
- **Backward Compatible**: No breaking changes to existing code

## Migration Guide

### For Existing Code

No changes needed! The system is fully backward compatible:

```python
# Old code still works
from src.utils.selectors import SelectorManager
manager = SelectorManager()
```

### To Use Country-Specific Selectors

Update your service initialization:

```python
# Old
manager = get_selector_manager()

# New
country = config["vfs"]["mission"]  # e.g., "fra", "nld"
manager = get_selector_manager(country)
```

### To Add Country Overrides

1. Identify which selectors differ for a specific country
2. Add them under `countries.{country_code}` in `selectors.yaml`
3. Test with the country-specific bot configuration
4. The learning system will automatically track performance

## Testing

Run the test suite:

```bash
pytest tests/test_selectors.py -v
```

All 23 tests should pass, including:
- 10 country-aware specific tests
- 13 backward compatibility tests

## Performance

- **Caching**: Selector manager instances are cached per country
- **No Overhead**: Default country has same performance as before
- **Efficient Lookups**: Dictionary-based selector resolution
- **Lazy Loading**: Metrics loaded only when needed

## Troubleshooting

### Selector Not Found

If a selector fails:
1. Check if country override exists in YAML
2. Check if default selector exists
3. Review metrics file for that country to see performance history
4. Consider adding more fallbacks

### Wrong Country Being Used

Verify the country code:
```python
manager = get_selector_manager(country)
print(f"Using country: {manager.country_code}")
```

### Metrics Not Saving

Check that the `data/` directory exists and is writable. The system will create country-specific metric files automatically.

## Future Enhancements

Potential improvements:
- AI-powered selector suggestion per country
- Web scraping to detect selector changes per country
- Automatic country detection from URL
- Selector health monitoring dashboard per country
