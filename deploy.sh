#!/bin/bash
# Create deploy.sh

set -e

echo "Starting NovaEdgeFinance deployment..."

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | awk '/=/ {print $1}')
fi

# Run database migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Clear cache
echo "Clearing cache..."
python manage.py clear_cache

# Compile messages for internationalization
echo "Compiling messages..."
python manage.py compilemessages

# Create cache table
echo "Creating cache table..."
python manage.py createcachetable || true

# Start Celery worker in background
echo "Starting Celery worker..."
celery -A novaedge worker --loglevel=info --detach

# Start Celery beat in background
echo "Starting Celery beat..."
celery -A novaedge beat --loglevel=info --detach

# Start Gunicorn
echo "Starting Gunicorn server..."
gunicorn novaedge.wsgi:application \
    --workers 4 \
    --worker-class sync \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --max-requests 1200 \
    --max-requests-jitter 100 \
    --access-logfile - \
    --error-logfile - \
    --log-level info

echo "Deployment completed successfully!"