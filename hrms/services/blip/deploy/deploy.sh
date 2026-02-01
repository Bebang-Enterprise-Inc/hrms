#!/bin/bash
# Blip AI Assistant - Deployment Script
# Run on AWS EC2 server to deploy/update Blip

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$(dirname "$SCRIPT_DIR")"
DEPLOY_DIR="/opt/blip"

echo "=========================================="
echo "Blip AI Assistant - Deployment"
echo "=========================================="

# Check for required environment variables
required_vars=("FRAPPE_API_KEY" "FRAPPE_API_SECRET" "ANTHROPIC_API_KEY" "GEMINI_API_KEY")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "ERROR: Missing required environment variables:"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    echo ""
    echo "Set these in your environment or create a .env file:"
    echo "  export FRAPPE_API_KEY=your_key"
    echo "  export FRAPPE_API_SECRET=your_secret"
    echo "  export ANTHROPIC_API_KEY=your_key  # Claude Haiku 4.5"
    echo "  export GEMINI_API_KEY=your_key     # Gemini 3 Flash"
    exit 1
fi

# Create deployment directory
echo "Creating deployment directory..."
sudo mkdir -p "$DEPLOY_DIR"
sudo mkdir -p "$DEPLOY_DIR/logs"

# Copy service files
echo "Copying service files..."
sudo cp -r "$SERVICE_DIR"/* "$DEPLOY_DIR/"
sudo chown -R ubuntu:ubuntu "$DEPLOY_DIR"

# Create .env file
echo "Creating .env file..."
cat > "$DEPLOY_DIR/deploy/.env" << EOF
FRAPPE_API_KEY=${FRAPPE_API_KEY}
FRAPPE_API_SECRET=${FRAPPE_API_SECRET}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
GEMINI_API_KEY=${GEMINI_API_KEY}
GOOGLE_CHAT_PROJECT_NUMBER=${GOOGLE_CHAT_PROJECT_NUMBER:-}
EOF
chmod 600 "$DEPLOY_DIR/deploy/.env"

# Build and start container
echo "Building and starting Blip container..."
cd "$DEPLOY_DIR/deploy"
docker-compose down 2>/dev/null || true
docker-compose build --no-cache
docker-compose up -d

# Wait for health check
echo "Waiting for service to be healthy..."
sleep 5

# Check health
if curl -s http://localhost:8766/health | grep -q "healthy"; then
    echo "Blip is healthy!"
else
    echo "WARNING: Health check failed. Check logs:"
    docker-compose logs --tail=50
fi

# Setup nginx (if not already configured)
if [ ! -f /etc/nginx/sites-available/blip ]; then
    echo "Setting up nginx configuration..."
    sudo cp "$DEPLOY_DIR/deploy/nginx-blip.conf" /etc/nginx/sites-available/blip

    # Add to existing hq.bebang.ph config
    echo "NOTE: Add the following to your hq.bebang.ph nginx config:"
    echo "  include /etc/nginx/sites-available/blip;"
    echo ""
    echo "Or include the location blocks directly in your server block."
fi

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "Service Status:"
docker-compose ps
echo ""
echo "Endpoints:"
echo "  - Health: https://hq.bebang.ph/blip/health"
echo "  - Google Chat: https://hq.bebang.ph/webhook/gchat"
echo ""
echo "Next Steps:"
echo "  1. Update Google Chat app webhook URL to: https://hq.bebang.ph/webhook/gchat"
echo "  2. Test by sending a message to Blip in Google Chat"
echo ""
echo "Logs: docker-compose logs -f"
