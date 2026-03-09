FROM python:3.12-slim

# System deps: curl for supercronic, Node.js for Claude CLI (required by claude-agent-sdk)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | \
    gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > \
    /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install Claude CLI (required by claude-agent-sdk)
RUN npm install -g @anthropic-ai/claude-code

# Non-root user
RUN useradd -m -s /bin/bash agent

# Supercronic (Docker-native cron)
RUN curl -fsSLO https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-amd64 && \
    chmod +x supercronic-linux-amd64 && \
    mv supercronic-linux-amd64 /usr/local/bin/supercronic

# Python deps
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# Agent code
COPY agent.py /app/analytics-agent/
COPY tools/ /app/analytics-agent/tools/
COPY templates/ /app/analytics-agent/templates/
COPY prompts/ /app/analytics-agent/prompts/
COPY __init__.py /app/analytics-agent/
COPY supercronic-crontab /app/

RUN chown -R agent:agent /app
WORKDIR /app
USER agent

CMD ["supercronic", "/app/supercronic-crontab"]
