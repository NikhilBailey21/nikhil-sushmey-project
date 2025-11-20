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
# Install psycopg2-binary first to ensure it's available for the connector
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir psycopg2-binary>=2.9.0 && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Install the application in editable mode
RUN pip install -e .

# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create instance directory for database
RUN mkdir -p instance

# Expose port 8080 (Cloud Run default, configurable via PORT env var)
EXPOSE 8080

# Set entrypoint
ENTRYPOINT ["docker-entrypoint.sh"]

