#!/bin/bash
set -e

# Initialize database
echo "Initializing database..."
flask init-db

# Run the Flask application
# Use PORT environment variable if set, otherwise default to 8080 (Cloud Run default)
PORT=${PORT:-8080}
exec flask run --host=0.0.0.0 --port=$PORT

