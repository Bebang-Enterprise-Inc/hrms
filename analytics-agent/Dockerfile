FROM python:3.12-slim

# Install system dependencies (curl for supercronic download)
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -s /bin/bash agent

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

# Set ownership and switch to non-root user
RUN chown -R agent:agent /app
WORKDIR /app
USER agent

CMD ["supercronic", "/app/supercronic-crontab"]
