# Sheets Receiver Service
# Similar to ADMS Receiver - runs alongside Frappe

FROM python:3.11-slim

LABEL maintainer="sam@bebang.ph"
LABEL description="Google Sheets sync service for BEI ERP"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app/hrms/services/sheets_receiver/

# Create directories
RUN mkdir -p /app/data /app/logs /app/credentials

# Environment variables (override in docker-compose)
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO
ENV SHEETS_RECEIVER_PORT=8765
ENV SHEETS_RECEIVER_DB=/app/data/sheets_receiver.db
ENV SHEETS_RECEIVER_LOG=/app/logs/sheets_receiver.log

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8765/health || exit 1

# Expose webhook port
EXPOSE 8765

# Run the service
CMD ["python", "-m", "hrms.services.sheets_receiver.main"]
