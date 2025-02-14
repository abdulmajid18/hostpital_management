#!/bin/sh
set -e  # Exit immediately if a command exits with a non-zero status

# Function to output messages with timestamps
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Trap to handle errors
trap "log 'Script failed. Exiting...'; exit 1" ERR

# Function to check database connection using Django's check command
check_db_connection() {
    log "Checking database connection..."
    max_retries=5
    retry_delay=5

    for i in $(seq 1 $max_retries); do
        python manage.py check --database default
        if [ $? -eq 0 ]; then
            log "Database connected successfully"
            return 0
        else
            log "Attempt $i/$max_retries: Failed to connect to the database. Retrying in $retry_delay seconds..."
            sleep $retry_delay
        fi
    done

    log "Failed to connect to the database after $max_retries attempts"
    exit 1
}

# Database connection check
check_db_connection

# Apply migrations
log "Applying migrations"
python manage.py makemigrations || log "No new migrations found"
python manage.py migrate || { log "Migrations failed"; exit 1; }

# Populate the database with initial data
log "Setting up initial roles"
python manage.py setup_roles || { log "Database population failed (Admin setup)"; exit 1; }

# Collect static files
log "Collecting static files"
python manage.py collectstatic --noinput || { log "Collectstatic failed"; exit 1; }

# Start RabbitMQ consumer in the background
log "Starting RabbitMQ consumer..."
python manage.py consume_rabbitmq &

# Set Gunicorn workers and concurrency
WORKERS=2 # Number of workers based on CPU cores
THREADS=2
LOG_LEVEL="debug"
TIMEOUT=60

log "Starting Gunicorn with $WORKERS workers"
exec gunicorn hospital_management.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers $WORKERS \
    --log-level $LOG_LEVEL \
    --timeout $TIMEOUT \
    --preload \
    --worker-class=gthread \
    --threads $THREADS \
    --access-logfile - \
    --error-logfile -
