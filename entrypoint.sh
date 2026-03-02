#!/bin/bash
# entrypoint.sh

# Wait for PostgreSQL to be ready (skip if using SQLite)
if [ "$USE_POSTGRES" = "True" ]; then
  echo "Waiting for PostgreSQL..."
  until pg_isready -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER; do
    sleep 2
  done
fi

# Apply Django migrations
echo "Applying migrations..."
python scrapper/manage.py migrate

# Create superuser if it does not exist
echo "Creating superuser..."
python - << END
from django.contrib.auth import get_user_model
import os
User = get_user_model()
username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@example.com")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "adminpass")
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
END

# Collect static files
echo "Collecting static files..."
python scrapper/manage.py collectstatic --noinput

# Start Gunicorn
echo "Starting Gunicorn..."
exec gunicorn scrapper.wsgi:application --bind 0.0.0.0:8000