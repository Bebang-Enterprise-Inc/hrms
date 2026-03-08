FROM python:3.12-slim

# Install system dependencies (curl + bash needed for Claude CLI, supercronic)
RUN apt-get update && apt-get install -y --no-install-recommends curl bash && \
    rm -rf /var/lib/apt/lists/*

# Install Claude CLI (install script requires bash, not sh)
RUN curl -fsSL https://claude.ai/install.sh | bash

# Install supercronic (Docker-native cron)
RUN curl -fsSLO https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-amd64 && \
    chmod +x supercronic-linux-amd64 && \
    mv supercronic-linux-amd64 /usr/local/bin/supercronic

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy agent code
COPY agent.py /app/analytics-agent/
COPY tools/ /app/analytics-agent/tools/
COPY templates/ /app/analytics-agent/templates/
COPY prompts/ /app/analytics-agent/prompts/
COPY __init__.py /app/analytics-agent/

# Copy cron schedule
COPY supercronic-crontab /app/

WORKDIR /app

CMD ["supercronic", "/app/supercronic-crontab"]
