# PCI-DSS Compliance

## Cardholder Data Storage

| Data | Storage | Compliance |
|------|---------|------------|
| PAN | Encrypted | Req 3.4 ✅ |
| CVV | Never | Req 3.2.2 ✅ |
| PIN | Never | Req 3.2.3 ✅ |

## Encryption
- Algorithm: Fernet (AES-128 + HMAC)
- Key storage: Environment variable
- CVV: In-memory only

## Access Control
- JWT authentication
- Bcrypt passwords
- Admin-only payment ops

## Monitoring
- Sentry error tracking
- Sensitive data filtering
- Audit logging
