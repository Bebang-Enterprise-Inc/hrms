#!/bin/bash
# Sheets Receiver - Standalone Deployment Script
# Run on AWS EC2 instance
#
# Usage:
#   ./deploy.sh              # Full deploy
#   ./deploy.sh start        # Start service
#   ./deploy.sh stop         # Stop service
#   ./deploy.sh status       # Check status
#   ./deploy.sh logs         # View logs
#   ./deploy.sh remove       # Remove completely (post go-live)

set -e

# Configuration
DEPLOY_DIR="/home/ubuntu/sheets-receiver"
REPO_URL="https://github.com/Bebang-Enterprise-Inc/hrms.git"
BRANCH="production"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date '+%H:%M:%S')] WARNING:${NC} $1"; }
error() { echo -e "${RED}[$(date '+%H:%M:%S')] ERROR:${NC} $1"; exit 1; }

case "${1:-deploy}" in
    deploy)
        log "Deploying Sheets Receiver..."

        # Create directory structure
        mkdir -p "$DEPLOY_DIR"/{credentials,data,logs}
        cd "$DEPLOY_DIR"

        # Copy service files from repo (or clone)
        if [ -d "hrms" ]; then
            cd hrms && git pull origin "$BRANCH" && cd ..
        else
            git clone --depth 1 -b "$BRANCH" "$REPO_URL" hrms
        fi

        # Copy deployment files
        cp hrms/hrms/services/sheets_receiver/deploy/docker-compose.yml .
        cp hrms/hrms/services/sheets_receiver/deploy/nginx-sheets-receiver.conf .

        # Copy credentials (must exist on server)
        if [ -f "/home/ubuntu/frappe_docker/credentials/task-manager-service.json" ]; then
            cp /home/ubuntu/frappe_docker/credentials/task-manager-service.json credentials/
            log "Copied Google credentials"
        else
            warn "Google credentials not found - copy manually to $DEPLOY_DIR/credentials/"
        fi

        # Get Frappe API keys from Doppler
        log "Fetching secrets from Doppler..."
        export FRAPPE_API_KEY=$(doppler secrets get FRAPPE_API_KEY --plain --project bei-erp --config dev 2>/dev/null || echo "")
        export FRAPPE_API_SECRET=$(doppler secrets get FRAPPE_API_SECRET --plain --project bei-erp --config dev 2>/dev/null || echo "")

        if [ -z "$FRAPPE_API_KEY" ]; then
            warn "Doppler secrets not found. Set FRAPPE_API_KEY and FRAPPE_API_SECRET manually."
            echo "FRAPPE_API_KEY=your-key" > .env
            echo "FRAPPE_API_SECRET=your-secret" >> .env
            warn "Edit .env file with correct values"
        else
            echo "FRAPPE_API_KEY=$FRAPPE_API_KEY" > .env
            echo "FRAPPE_API_SECRET=$FRAPPE_API_SECRET" >> .env
            log "Secrets configured"
        fi

        # Build and start
        log "Building Docker image..."
        docker-compose build

        log "Starting service..."
        docker-compose up -d

        # Legacy nginx proxy config is no longer required for the main webhook path,
        # because Google hits the public Frappe method route directly. Keep the file
        # available for optional host-local proxy use, but do not treat nginx as a
        # deployment dependency.
        if [ -f nginx-sheets-receiver.conf ]; then
            log "Legacy nginx helper file refreshed (not required for webhook path)"
        fi

        log "Deployment complete!"
        log "Webhook URL: https://hq.bebang.ph/api/method/hrms.api.erp_sync.webhook"
        log "Status: docker-compose logs -f"
        ;;

    start)
        cd "$DEPLOY_DIR"
        docker-compose up -d
        log "Started"
        ;;

    stop)
        cd "$DEPLOY_DIR"
        docker-compose down
        log "Stopped"
        ;;

    restart)
        cd "$DEPLOY_DIR"
        docker-compose restart
        log "Restarted"
        ;;

    status)
        cd "$DEPLOY_DIR"
        docker-compose ps
        echo ""
        curl -s http://localhost:8765/health 2>/dev/null && echo "" || echo "Service not responding"
        echo ""
        curl -s http://localhost:8765/api/status 2>/dev/null | python3 -m json.tool || true
        ;;

    logs)
        cd "$DEPLOY_DIR"
        docker-compose logs -f --tail=100
        ;;

    setup-watches)
        log "Setting up Google Drive watches..."
        curl -X POST http://localhost:8765/api/watches/setup
        echo ""
        ;;

    sync)
        sheet="${2:-all}"
        if [ "$sheet" = "all" ]; then
            log "Triggering sync for all sheets..."
            curl -X POST "http://localhost:8765/api/sync-all?force=true"
        else
            log "Triggering sync for $sheet..."
            curl -X POST "http://localhost:8765/api/sync/$sheet?force=true"
        fi
        echo ""
        ;;

    remove)
        warn "This will completely remove Sheets Receiver!"
        read -p "Are you sure? (type 'yes' to confirm): " confirm
        if [ "$confirm" = "yes" ]; then
            cd "$DEPLOY_DIR"
            docker-compose down -v
            sudo rm -f /etc/nginx/conf.d/nginx-sheets-receiver.conf
            sudo nginx -t && sudo systemctl reload nginx
            log "Removed. Data preserved in $DEPLOY_DIR/data/"
            log "To fully remove: rm -rf $DEPLOY_DIR"
        else
            log "Cancelled"
        fi
        ;;

    *)
        echo "Usage: $0 {deploy|start|stop|restart|status|logs|setup-watches|sync|remove}"
        exit 1
        ;;
esac
