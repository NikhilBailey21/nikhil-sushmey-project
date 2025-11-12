#!/bin/bash
set -e

# Initialize database if it doesn't exist
if [ ! -f instance/flaskr.sqlite ]; then
    echo "Initializing database..."
    flask init-db
fi

# Run the Flask application
exec flask run --host=0.0.0.0 --port=5000

