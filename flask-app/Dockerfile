# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=flaskr \
    FLASK_ENV=production

# Copy requirements and install Python dependencies
COPY flask-app/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy shared modules
COPY shared /app/shared

# Copy application code
COPY flask-app /app

# Install the application in editable mode
RUN pip install -e .

# Copy entrypoint script
COPY flask-app/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Expose port 8080 (Cloud Run default, configurable via PORT env var)
EXPOSE 8080

# Set entrypoint
ENTRYPOINT ["docker-entrypoint.sh"]

