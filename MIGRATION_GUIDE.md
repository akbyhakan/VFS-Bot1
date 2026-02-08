# Migration Guide: SQLite to PostgreSQL

## Overview

VFS-Bot has been migrated from SQLite to PostgreSQL for better scalability, concurrency, and production readiness. This guide will help you migrate your existing data and update your deployment.

## Why PostgreSQL?

- **Better Concurrency**: No database-level locks during writes
- **Native Connection Pooling**: asyncpg provides efficient connection management
- **Scalability**: Production-ready for high-traffic applications
- **Advanced Features**: Access to PostgreSQL-specific features (JSONB, arrays, full-text search)
- **Industry Standard**: Widely used and supported in production environments

## Prerequisites

- PostgreSQL 16+ recommended (minimum 9.6 for basic features)
- Python 3.12+
- Existing VFS-Bot installation with SQLite database

## Migration Steps

### 1. Backup Your Current Data

**CRITICAL**: Always backup your PostgreSQL database before migrating:

```bash
# Backup PostgreSQL database using pg_dump
pg_dump postgresql://vfs_bot:password@localhost:5432/vfs_bot > vfs_bot_backup_$(date +%Y%m%d).sql

# Or use environment variable
pg_dump $DATABASE_URL > vfs_bot_backup_$(date +%Y%m%d).sql
```

### 2. Install PostgreSQL

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib libpq-dev
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### macOS
```bash
brew install postgresql@16
brew services start postgresql@16
```

#### Docker
```bash
# Use docker-compose (recommended)
docker-compose up -d postgres
```

### 3. Create Database and User

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create user and database
CREATE USER vfs_bot WITH PASSWORD 'your_secure_password';
CREATE DATABASE vfs_bot OWNER vfs_bot;
GRANT ALL PRIVILEGES ON DATABASE vfs_bot TO vfs_bot;

# Exit psql
\q
```

### 4. Update Configuration

#### Update .env file:
```bash
# Old (SQLite)
# DATABASE_PATH=vfs_bot.db

# New (PostgreSQL)
DATABASE_URL=postgresql://vfs_bot:your_secure_password@localhost:5432/vfs_bot
POSTGRES_PASSWORD=your_secure_password
```

#### Update docker-compose.yml (if using Docker):
The new `docker-compose.yml` includes a PostgreSQL service. Make sure to set `POSTGRES_PASSWORD` in your `.env` file.

### 5. Update Dependencies

```bash
# Activate your virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Update dependencies
pip install -r requirements.txt
```

This will install:
- `asyncpg>=0.29.0` (PostgreSQL driver)
- `alembic>=1.13.0` (database migrations)
- `sqlalchemy[asyncio]>=2.0.0` (ORM support)

### 6. Data Migration (Manual)

Unfortunately, automatic data migration from SQLite to PostgreSQL is not included in this release. You have two options:

#### Option A: Start Fresh (Recommended for New Deployments)
Simply start the application with the new PostgreSQL database. The schema will be created automatically on first run.

```bash
python main.py --mode both
```

#### Option B: Manual Data Export/Import (For Existing Data)

1. **Export data from SQLite**:
```bash
sqlite3 vfs_bot.db
.mode csv
.output users.csv
SELECT * FROM users;
.output personal_details.csv
SELECT * FROM personal_details;
.output appointments.csv
SELECT * FROM appointments;
.quit
```

2. **Import into PostgreSQL**:
```sql
-- Connect to PostgreSQL
psql postgresql://vfs_bot:password@localhost:5432/vfs_bot

-- Import users (adjust column names as needed)
\COPY users FROM 'users.csv' WITH (FORMAT CSV, HEADER);

-- Import personal details
\COPY personal_details FROM 'personal_details.csv' WITH (FORMAT CSV, HEADER);

-- Import appointments
\COPY appointments FROM 'appointments.csv' WITH (FORMAT CSV, HEADER);
```

**Note**: You may need to adjust the import commands based on your schema and data. The auto-increment IDs and timestamps might need special handling.

### 7. Schema Initialization

On first run, VFS-Bot will automatically create all necessary tables in PostgreSQL:

```bash
python main.py --mode both
```

Check the logs to ensure the schema was created successfully:
```
INFO - Database connected with pool size 10: postgresql://vfs_bot@localhost:5432/vfs_bot
INFO - Created users table
INFO - Created personal_details table
...
```

### 8. Verify Migration

1. **Check database connection**:
```bash
curl http://localhost:8000/health
```

2. **Verify data (if imported)**:
```bash
# Connect to PostgreSQL
psql postgresql://vfs_bot:password@localhost:5432/vfs_bot

# Check tables
\dt

# Check row counts
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM personal_details;
SELECT COUNT(*) FROM appointments;
```

3. **Test functionality**:
- Access the web dashboard: `http://localhost:8000`
- Try adding a new user
- Run a test appointment check

## Key Differences

### Connection Management
- **SQLite**: File-based, single-writer limitation
- **PostgreSQL**: Client-server, supports multiple concurrent connections

### Connection Pooling
- **SQLite**: Custom queue-based pool
- **PostgreSQL**: Native asyncpg connection pool (more efficient)

### SQL Syntax Changes
- Placeholders: `?` → `$1, $2, $3`
- Auto-increment: `INTEGER PRIMARY KEY AUTOINCREMENT` → `BIGSERIAL PRIMARY KEY`
- Booleans: `1/0` → `TRUE/FALSE`
- Timestamps: `CURRENT_TIMESTAMP` → `NOW()`
- Arrays: `IN (?, ?, ?)` → `= ANY($1::bigint[])`

### Backup Strategy
- **SQLite**: File copy or SQLite backup API
- **PostgreSQL**: `pg_dump` and `pg_restore`

```bash
# Backup PostgreSQL database
pg_dump postgresql://vfs_bot:password@localhost:5432/vfs_bot > backup_$(date +%Y%m%d).sql

# Restore PostgreSQL database
psql postgresql://vfs_bot:password@localhost:5432/vfs_bot < backup_20240207.sql
```

## Troubleshooting

### Connection Issues

**Problem**: `asyncpg.exceptions.InvalidPasswordError`
```
Solution: Check DATABASE_URL credentials in .env file
```

**Problem**: `asyncpg.exceptions.InvalidCatalogNameError: database "vfs_bot" does not exist`
```
Solution: Create the database first (see step 3)
```

**Problem**: Connection timeout
```
Solution: 
1. Check if PostgreSQL is running: sudo systemctl status postgresql
2. Check if PostgreSQL is listening: netstat -an | grep 5432
3. Verify DATABASE_URL is correct
```

### Performance Tuning

For production deployments, consider tuning these PostgreSQL settings in `postgresql.conf`:

```conf
# Connection settings
max_connections = 100
shared_buffers = 256MB

# Performance
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
```

Adjust `DB_POOL_SIZE` in your `.env` based on your workload:
```env
# Conservative (low traffic)
DB_POOL_SIZE=5

# Default (moderate traffic)
DB_POOL_SIZE=10

# High traffic
DB_POOL_SIZE=20
```

### Test Environment

For testing, you can use a separate test database:

```bash
# Create test database
sudo -u postgres psql -c "CREATE DATABASE vfs_bot_test OWNER vfs_bot;"

# Set test database URL
export TEST_DATABASE_URL=postgresql://vfs_bot:password@localhost:5432/vfs_bot_test
```

## Rolling Back

If you need to roll back to SQLite (not recommended for production):

1. Restore your SQLite backup:
```bash
cp vfs_bot_backup_20240207.db vfs_bot.db
```

2. Revert to previous version:
```bash
git checkout <previous-commit>
pip install -r requirements.txt
```

3. Update .env:
```env
DATABASE_PATH=vfs_bot.db
```

## Getting Help

If you encounter issues during migration:

1. Check the [GitHub Issues](https://github.com/akbyhakan/VFS-Bot1/issues)
2. Review application logs: `tail -f logs/vfs_bot.log`
3. Check PostgreSQL logs: `sudo tail -f /var/log/postgresql/postgresql-16-main.log`
4. Open a new issue with:
   - PostgreSQL version: `psql --version`
   - Python version: `python --version`
   - Error messages from logs
   - Steps to reproduce

## Benefits After Migration

✅ **No more database locks** during concurrent operations
✅ **Better performance** for multi-user scenarios
✅ **Production-ready** scalability
✅ **Advanced features** available (JSONB, arrays, full-text search)
✅ **Industry-standard** database with extensive tooling
✅ **Better backup** and recovery options

Welcome to PostgreSQL! 🎉
