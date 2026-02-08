# Environment Setup

## Quick Start

### Automated Setup (Recommended)

The easiest way to set up your environment is to use the interactive setup script:

```bash
python scripts/setup_environment.py
```

This script will:
- Generate secure encryption keys automatically
- Hash your admin password with bcrypt
- **Encrypt your VFS password with Fernet** for additional security
- Create a `.env` file with proper permissions
- Set `VFS_PASSWORD_ENCRYPTED=true` to indicate the password is encrypted

### Manual Setup

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
| VFS_PASSWORD | ≥8 characters (Fernet-encrypted when using setup script) |
| VFS_PASSWORD_ENCRYPTED | true if password is encrypted, false otherwise |
