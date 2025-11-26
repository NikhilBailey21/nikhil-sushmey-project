#!/bin/bash
set -e

# Run the Flask application
# Use PORT environment variable if set, otherwise default to 8080 (Cloud Run default)
PORT=${PORT:-8080}
echo "Starting Flask application on port ${PORT}..."
exec flask run --host=0.0.0.0 --port=$PORT

