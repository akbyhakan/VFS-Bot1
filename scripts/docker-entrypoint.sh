#!/bin/bash
set -e

# Function to run migrations with retry logic
run_migrations() {
    local max_retries=3
    local retry_count=0
    local base_wait=2
    
    while [ $retry_count -lt $max_retries ]; do
        echo "Attempting database migration (attempt $((retry_count + 1))/$max_retries)..."
        
        if python -m alembic upgrade head; then
            echo "✅ Database migrations completed successfully"
            return 0
        else
            retry_count=$((retry_count + 1))
            
            if [ $retry_count -lt $max_retries ]; then
                # Exponential backoff: 2 * retry_count (linear backoff for simplicity)
                wait_time=$((base_wait * retry_count))
                echo "⚠️ Migration failed, retrying in ${wait_time}s..."
                sleep $wait_time
            fi
        fi
    done
    
    echo "❌ Database migrations failed after $max_retries attempts"
    return 1
}

# Check if migrations should be skipped
if [ "${SKIP_MIGRATIONS}" = "true" ]; then
    echo "⚠️ SKIP_MIGRATIONS=true - Skipping database migrations"
else
    # Run migrations with retry logic
    if ! run_migrations; then
        echo "⚠️ Starting bot in read-only mode due to migration failure"
        exec python main.py --read-only "$@"
    fi
fi

echo "Starting VFS-Bot..."
exec python main.py "$@"
