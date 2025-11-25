#!/bin/bash
set -e

# Initialize database
echo "Initializing database..."
echo "FLASK_APP: ${FLASK_APP:-not set}"
echo "Database connection check..."

# Run init-db with explicit error handling
if flask init-db; then
    echo "Database initialized successfully!"
else
    echo "ERROR: Database initialization failed!"
    exit 1
fi

# Run the Flask application
# Use PORT environment variable if set, otherwise default to 8080 (Cloud Run default)
PORT=${PORT:-8080}
echo "Starting Flask application on port ${PORT}..."
exec flask run --host=0.0.0.0 --port=$PORT

