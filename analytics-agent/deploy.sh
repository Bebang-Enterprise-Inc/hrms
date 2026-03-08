#!/bin/bash
# BEI Analytics Agent — EC2 Deployment Script
# Run from EC2 instance (i-026b7477d27bd46d6)
# Same pattern as Blip Sentinel deployment

set -euo pipefail

DEPLOY_DIR="/home/ubuntu/analytics-agent"
REPO_TMP="/tmp/hrms-deploy"
REPO_URL="https://github.com/Bebang-Enterprise-Inc/hrms.git"

echo "=== BEI Analytics Agent Deployment ==="

# 1. Clone latest production (shallow)
echo "[1/6] Cloning latest production..."
rm -rf "$REPO_TMP"
git clone --depth 1 --branch production "$REPO_URL" "$REPO_TMP"

# 2. Create deploy directory if needed
echo "[2/6] Setting up deploy directory..."
mkdir -p "$DEPLOY_DIR"
mkdir -p "$DEPLOY_DIR/runs"
mkdir -p "$DEPLOY_DIR/credentials"
mkdir -p "$DEPLOY_DIR/claude-auth"

# 3. Copy agent files (preserve .env, credentials, claude-auth, runs)
echo "[3/6] Copying agent files..."
cp -r "$REPO_TMP/analytics-agent/agent.py" "$DEPLOY_DIR/"
cp -r "$REPO_TMP/analytics-agent/__init__.py" "$DEPLOY_DIR/"
cp -r "$REPO_TMP/analytics-agent/tools" "$DEPLOY_DIR/"
cp -r "$REPO_TMP/analytics-agent/templates" "$DEPLOY_DIR/"
cp -r "$REPO_TMP/analytics-agent/prompts" "$DEPLOY_DIR/"
cp -r "$REPO_TMP/analytics-agent/Dockerfile" "$DEPLOY_DIR/"
cp -r "$REPO_TMP/analytics-agent/docker-compose.yml" "$DEPLOY_DIR/"
cp -r "$REPO_TMP/analytics-agent/requirements.txt" "$DEPLOY_DIR/"
cp -r "$REPO_TMP/analytics-agent/supercronic-crontab" "$DEPLOY_DIR/"

# Copy sync script (mounted as volume by docker-compose)
mkdir -p "$DEPLOY_DIR/../scripts"
cp "$REPO_TMP/scripts/sync_meta_ads_to_supabase.py" "$DEPLOY_DIR/../scripts/"

# 4. Verify .env exists
echo "[4/6] Checking .env..."
if [ ! -f "$DEPLOY_DIR/.env" ]; then
    echo "ERROR: $DEPLOY_DIR/.env not found!"
    echo "Create it from .env.example with real values before deploying."
    cp "$REPO_TMP/analytics-agent/.env.example" "$DEPLOY_DIR/.env.example"
    exit 1
fi

# 5. Verify credentials exist
echo "[5/6] Checking credentials..."
if [ ! -f "$DEPLOY_DIR/credentials/task-manager-service.json" ]; then
    echo "ERROR: Service account credentials not found!"
    echo "Copy task-manager-service.json to $DEPLOY_DIR/credentials/"
    exit 1
fi

if [ ! -d "$DEPLOY_DIR/claude-auth" ] || [ -z "$(ls -A $DEPLOY_DIR/claude-auth 2>/dev/null)" ]; then
    echo "WARNING: claude-auth/ is empty. Run 'claude setup-token' and copy auth files."
fi

# 6. Build and start container
echo "[6/6] Building and starting container..."
cd "$DEPLOY_DIR"
docker compose down 2>/dev/null || true
docker compose build --no-cache
docker compose up -d

echo ""
echo "=== Deployment Complete ==="
echo "Container: bei-analytics-agent"
echo "Cron: Sunday 11:00 UTC (7:00 PM PHT)"
echo ""
echo "Verify with:"
echo "  docker logs bei-analytics-agent"
echo "  docker ps | grep analytics"

# Cleanup
rm -rf "$REPO_TMP"
