#!/bin/bash

# Exit on any error
set -e

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Running database migrations..."
python manage.py makemigrations
python manage.py migrate

echo "Setting up sample data and Google OAuth..."
python manage.py setup_sample_data

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Build completed successfully!"
