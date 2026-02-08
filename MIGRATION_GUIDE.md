# PostgreSQL Database Setup Guide

## Overview

VFS-Bot uses PostgreSQL as its database backend for production-ready scalability, efficient concurrency handling, and enterprise-grade features.

## Why PostgreSQL?

- **Better Concurrency**: No database-level locks during writes, supports multiple concurrent connections
- **Native Connection Pooling**: asyncpg provides efficient connection management with C-level optimizations
- **Scalability**: Production-ready for high-traffic applications
- **Advanced Features**: JSONB, arrays, full-text search, materialized views
- **Industry Standard**: Widely used and supported in production environments
- **Robust Backup & Recovery**: Enterprise-grade tools like pg_dump and pg_restore

## Prerequisites

- PostgreSQL 16+ recommended (minimum 9.6 for basic features)
- Python 3.12+
- Docker (optional, recommended for development)

## Installation

### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib libpq-dev
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### macOS
```bash
brew install postgresql@16
brew services start postgresql@16
```

### Docker (Recommended)
```bash
# Use docker-compose (easiest method)
docker-compose up -d postgres
```

The included `docker-compose.yml` already has a PostgreSQL 16 service configured.

## Database Setup

### 1. Create Database and User

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

### 2. Configure Environment Variables

Update your `.env` file with PostgreSQL connection details:

```bash
DATABASE_URL=postgresql://vfs_bot:your_secure_password@localhost:5432/vfs_bot
POSTGRES_PASSWORD=your_secure_password
DB_POOL_SIZE=10
DB_CONNECTION_TIMEOUT=30.0
```

#### Docker Environment

If using Docker, the database URL should point to the postgres service:

```bash
DATABASE_URL=postgresql://vfs_bot:${POSTGRES_PASSWORD}@postgres:5432/vfs_bot
```

### 3. Install Dependencies

```bash
# Activate your virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies (includes asyncpg, alembic)
pip install -r requirements.txt
```

This will install:
- `asyncpg>=0.29.0` - High-performance PostgreSQL driver
- `alembic>=1.13.0` - Database migrations (for future schema changes)
- `sqlalchemy[asyncio]>=2.0.0` - ORM support

### 4. Initialize Database Schema

On first run, VFS-Bot automatically creates all necessary tables:

```bash
python main.py --mode both
```

Check the logs to verify schema creation:
```
INFO - Database connected with pool size 10: postgresql://vfs_bot@localhost:5432/vfs_bot
INFO - Created users table
INFO - Created personal_details table
INFO - Created appointments table
...
```

### 5. Verify Installation

1. **Check database connection**:
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "version": "2.2.0"
}
```

2. **Verify tables**:
```bash
# Connect to PostgreSQL
psql postgresql://vfs_bot:password@localhost:5432/vfs_bot

# List all tables
\dt

# Check schema
\d users
\d personal_details
\d appointments
```

3. **Test functionality**:
- Access the web dashboard: `http://localhost:8000`
- Add a test user
- Verify data persistence

## Backup and Restore

### Backup Database

PostgreSQL provides powerful backup tools:

```bash
# Basic backup
pg_dump postgresql://vfs_bot:password@localhost:5432/vfs_bot > backup_$(date +%Y%m%d).sql

# Or using environment variable
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# Compressed backup (recommended for large databases)
pg_dump $DATABASE_URL | gzip > backup_$(date +%Y%m%d).sql.gz

# Custom format (allows selective restore)
pg_dump -Fc $DATABASE_URL > backup_$(date +%Y%m%d).dump
```

### Restore Database

```bash
# From SQL backup
psql postgresql://vfs_bot:password@localhost:5432/vfs_bot < backup_20240207.sql

# From compressed backup
gunzip -c backup_20240207.sql.gz | psql $DATABASE_URL

# From custom format
pg_restore -d $DATABASE_URL backup_20240207.dump
```

### Automated Backup Schedule

Consider setting up automated backups with cron:

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * pg_dump $DATABASE_URL | gzip > /backups/vfs_bot_$(date +\%Y\%m\%d).sql.gz

# Keep only last 7 days
0 3 * * * find /backups -name "vfs_bot_*.sql.gz" -mtime +7 -delete
```

## Performance Tuning

### Connection Pool Configuration

Adjust `DB_POOL_SIZE` in `.env` based on your workload:

```env
# Conservative (low traffic, development)
DB_POOL_SIZE=5

# Default (moderate traffic)
DB_POOL_SIZE=10

# High traffic (production with many concurrent users)
DB_POOL_SIZE=20
```

### PostgreSQL Configuration

For production deployments, tune these settings in `postgresql.conf`:

```conf
# Connection settings
max_connections = 100
shared_buffers = 256MB

# Performance
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB

# Write performance
random_page_cost = 1.1  # For SSD storage
effective_io_concurrency = 200

# Query optimization
default_statistics_target = 100
```

After changes, restart PostgreSQL:
```bash
sudo systemctl restart postgresql
```

## Troubleshooting

### Connection Issues

**Problem**: `asyncpg.exceptions.InvalidPasswordError`
```
Solution: Check DATABASE_URL credentials in .env file
Verify password matches what you set in PostgreSQL
```

**Problem**: `asyncpg.exceptions.InvalidCatalogNameError: database "vfs_bot" does not exist`
```
Solution: Create the database first (see Database Setup section)
```

**Problem**: Connection timeout or refused
```
Solution:
1. Check if PostgreSQL is running: sudo systemctl status postgresql
2. Check if PostgreSQL is listening: netstat -an | grep 5432
3. Verify DATABASE_URL is correct
4. Check PostgreSQL logs: sudo tail -f /var/log/postgresql/postgresql-16-main.log
```

**Problem**: `FATAL: role "vfs_bot" does not exist`
```
Solution: Create the database user (see Database Setup section)
```

### Permission Issues

**Problem**: `ERROR: permission denied for schema public`
```
Solution: Grant proper permissions to the user
sudo -u postgres psql
GRANT ALL PRIVILEGES ON DATABASE vfs_bot TO vfs_bot;
GRANT ALL ON SCHEMA public TO vfs_bot;
```

### Performance Issues

**Problem**: Slow queries
```
Solution:
1. Enable query logging in postgresql.conf:
   log_statement = 'all'
   log_duration = on
2. Analyze slow queries
3. Add indexes if needed
4. Increase shared_buffers if you have RAM available
```

**Problem**: Too many connections
```
Solution:
1. Reduce DB_POOL_SIZE in .env
2. Increase max_connections in postgresql.conf
3. Use connection pooler like pgBouncer for very high traffic
```

## Test Environment

For testing, use a separate test database:

```bash
# Create test database
sudo -u postgres psql -c "CREATE DATABASE vfs_bot_test OWNER vfs_bot;"

# Set test database URL
export TEST_DATABASE_URL=postgresql://vfs_bot:password@localhost:5432/vfs_bot_test

# Run tests
pytest
```

The test suite will automatically use `TEST_DATABASE_URL` when running tests.

## Docker Deployment

### Using Docker Compose

The included `docker-compose.yml` handles PostgreSQL setup automatically:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: vfs_bot
      POSTGRES_USER: vfs_bot
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U vfs_bot"]
      interval: 10s
      timeout: 5s
      retries: 5

  vfs-bot:
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgresql://vfs_bot:${POSTGRES_PASSWORD}@postgres:5432/vfs_bot

volumes:
  postgres-data:
```

Start everything:
```bash
docker-compose up -d
```

### Accessing PostgreSQL in Docker

```bash
# Connect to PostgreSQL container
docker-compose exec postgres psql -U vfs_bot -d vfs_bot

# Backup from Docker
docker-compose exec postgres pg_dump -U vfs_bot vfs_bot > backup.sql

# Restore to Docker
docker-compose exec -T postgres psql -U vfs_bot vfs_bot < backup.sql
```

## Monitoring

### Database Health Checks

VFS-Bot includes built-in health monitoring:

```bash
# Check overall health (includes database)
curl http://localhost:8000/health

# Response includes database status
{
  "status": "healthy",
  "database": "connected",
  "pool_size": 10,
  "active_connections": 3
}
```

### PostgreSQL Built-in Monitoring

```sql
-- Current connections
SELECT * FROM pg_stat_activity WHERE datname = 'vfs_bot';

-- Database size
SELECT pg_size_pretty(pg_database_size('vfs_bot'));

-- Table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Slow queries (if logging enabled)
SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;
```

## Security Best Practices

1. **Use Strong Passwords**: Generate secure passwords for PostgreSQL users
   ```bash
   openssl rand -base64 32
   ```

2. **Never Commit Credentials**: Keep `.env` in `.gitignore`

3. **Use SSL in Production**: Enable SSL connections in `postgresql.conf`
   ```conf
   ssl = on
   ssl_cert_file = '/path/to/server.crt'
   ssl_key_file = '/path/to/server.key'
   ```
   
   Update `DATABASE_URL`:
   ```
   DATABASE_URL=postgresql://vfs_bot:password@localhost:5432/vfs_bot?sslmode=require
   ```

4. **Restrict Network Access**: Configure `pg_hba.conf` to limit connections
   ```conf
   # Allow only local connections
   host    vfs_bot    vfs_bot    127.0.0.1/32    md5
   ```

5. **Regular Backups**: Implement automated backup strategy (see Backup section)

6. **Keep Updated**: Regularly update PostgreSQL to latest stable version

## Getting Help

If you encounter issues:

1. Check application logs: `tail -f logs/vfs_bot.log`
2. Check PostgreSQL logs: `sudo tail -f /var/log/postgresql/postgresql-16-main.log`
3. Review [GitHub Issues](https://github.com/akbyhakan/VFS-Bot1/issues)
4. Open a new issue with:
   - PostgreSQL version: `psql --version`
   - Python version: `python --version`
   - Error messages from logs
   - Steps to reproduce

## Benefits of PostgreSQL

✅ **No database locks** during concurrent write operations  
✅ **High performance** for multi-user scenarios  
✅ **Production-ready** scalability  
✅ **Advanced features**: JSONB, arrays, full-text search, CTEs  
✅ **Industry-standard** with extensive tooling and community support  
✅ **Excellent backup** and recovery options  
✅ **ACID compliance** for data integrity  
✅ **Horizontal scaling** support via replication

## Additional Resources

- [PostgreSQL Official Documentation](https://www.postgresql.org/docs/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [PostgreSQL Security Best Practices](https://www.postgresql.org/docs/current/security.html)

---

**Ready to use PostgreSQL with VFS-Bot!** 🎉
