#!/bin/sh
# Database backup script for VFS-Bot1.
# Creates a compressed pg_dump backup, verifies it, and rotates old backups.
#
# Required environment variables:
#   PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
# Optional environment variables:
#   BACKUP_RETENTION_DAYS  (default: 30)
set -euo pipefail

BACKUP_DIR="/backups"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/vfs_bot_${TIMESTAMP}.dump"

echo "🔄 Starting database backup..."
echo "   Host:      ${PGHOST}:${PGPORT}"
echo "   Database:  ${PGDATABASE}"
echo "   File:      ${BACKUP_FILE}"

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

# Run pg_dump
if PGPASSWORD="${PGPASSWORD}" pg_dump \
    --host="${PGHOST}" \
    --port="${PGPORT}" \
    --username="${PGUSER}" \
    --dbname="${PGDATABASE}" \
    --format=custom \
    --compress=9 \
    --file="${BACKUP_FILE}"; then
    echo "✅ pg_dump completed successfully."
else
    echo "❌ pg_dump failed."
    exit 1
fi

# Verify the backup file exists and is non-empty
if [ ! -s "${BACKUP_FILE}" ]; then
    echo "❌ Backup file is missing or empty: ${BACKUP_FILE}"
    exit 1
fi

BACKUP_SIZE="$(du -sh "${BACKUP_FILE}" | cut -f1)"
echo "📊 Backup size: ${BACKUP_SIZE}"

# Rotate old backups
echo "🧹 Rotating backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "vfs_bot_*.dump" -mtime "+${RETENTION_DAYS}" -delete
REMAINING="$(find "${BACKUP_DIR}" -name "vfs_bot_*.dump" | wc -l | tr -d ' ')"
echo "   ${REMAINING} backup(s) retained."

echo "✅ Backup completed: ${BACKUP_FILE}"
