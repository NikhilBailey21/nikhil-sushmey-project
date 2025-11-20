# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy application code
COPY hello.py .

# Make script executable
RUN chmod +x hello.py

# Expose port 8080 (Cloud Run default, configurable via PORT env var)
EXPOSE 8080

# Set entrypoint
ENTRYPOINT ["python", "hello.py"]

