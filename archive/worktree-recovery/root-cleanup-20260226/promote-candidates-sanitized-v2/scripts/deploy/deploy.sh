#!/bin/bash

# Manual Deployment Script for Frappe HRMS
# Usage: ./deploy.sh [environment]
# Example: ./deploy.sh production

set -e

ENVIRONMENT=${1:-production}
SITE_NAME=${SITE_NAME:-hrms.yourdomain.com}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Frappe HRMS Deployment Script${NC}"
echo "===================================="
echo "Environment: $ENVIRONMENT"
echo "Site: $SITE_NAME"
echo ""

# Check if git repo
if [ ! -d ".git" ]; then
    echo -e "${RED}❌ Not a git repository${NC}"
    echo "Please initialize git first: git init"
    exit 1
fi

# Check for uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo -e "${YELLOW}⚠️  Warning: You have uncommitted changes${NC}"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Pull latest code
echo "📥 Pulling latest code from GitHub..."
git fetch origin
git pull origin main || git pull origin master

# Navigate to docker directory
if [ -d "docker" ]; then
    cd docker
elif [ -d "aws" ]; then
    cd aws
    if [ -f "docker-compose.production.yml" ]; then
        export COMPOSE_FILE=docker-compose.production.yml
    fi
else
    echo -e "${RED}❌ Docker directory not found${NC}"
    exit 1
fi

# Create backup
echo "💾 Creating backup..."
if docker-compose ps | grep -q "frappe"; then
    docker-compose exec -T frappe bench --site $SITE_NAME backup --with-files || echo "Backup failed, continuing..."
else
    echo "Services not running, skipping backup..."
fi

# Stop services
echo "🛑 Stopping services..."
docker-compose down

# Pull latest images
echo "📦 Pulling latest Docker images..."
docker-compose pull

# Start services
echo "🔄 Starting services..."
docker-compose up -d --build

# Wait for services
echo "⏳ Waiting for services to be ready..."
sleep 30

# Health check
echo "🏥 Checking service health..."
if ! docker-compose ps | grep -q "Up"; then
    echo -e "${RED}❌ Services failed to start${NC}"
    docker-compose logs
    exit 1
fi

# Run migrations
echo "🔧 Running database migrations..."
docker-compose exec -T frappe bench --site $SITE_NAME migrate || echo "Migration failed, check logs"

# Clear cache
echo "🧹 Clearing cache..."
docker-compose exec -T frappe bench --site $SITE_NAME clear-cache || echo "Cache clear failed"

# Verify
echo "✅ Verifying deployment..."
docker-compose ps

echo ""
echo -e "${GREEN}🎉 Deployment complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Check logs: docker-compose logs -f"
echo "2. Verify site: http://$SITE_NAME:8000"
echo "3. Test login and functionality"


