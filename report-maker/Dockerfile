# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy requirements and install dependencies
COPY report-maker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules
COPY shared /app/shared

# Copy application code
COPY report-maker/mainConsumerScript.py .

# Make script executable
RUN chmod +x mainConsumerScript.py

# Set entrypoint
ENTRYPOINT ["python", "mainConsumerScript.py"]

