# Environment Setup

## Quick Start

### 1. Generate Keys

```bash
# Encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# API secret (32+ chars)
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. Hash Password

```bash
python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('your-password'))"
```

### 3. Validate

```bash
python -c "from src.core.env_validator import EnvValidator; EnvValidator.validate(strict=True)"
```

## Required Variables

| Variable | Validation |
|----------|------------|
| ADMIN_PASSWORD | Bcrypt in production |
| API_SECRET_KEY | ≥32 characters |
| VFS_PASSWORD | ≥8 characters |
