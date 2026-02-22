#!/bin/bash
# deploy_frontend.sh
# 
# A foolproof script to deploy the frontend to Vercel without relying on the developer
# or AI agent to remember to fetch the Doppler token manually.

set -e

echo -e "\033[0;36m🚀 Starting Automated Frontend Deployment...\033[0m"

# 1. Fetch the Token directly from Doppler
echo -e "\033[1;33m🔑 Fetching Vercel token from Doppler (Project: bei-erp, Config: dev)...\033[0m"
VERCEL_TOKEN=$(doppler secrets get VERCEL_TOKEN --project bei-erp --config dev --plain)

if [ -z "$VERCEL_TOKEN" ]; then
    echo -e "\033[0;31m❌ Failed to retrieve VERCEL_TOKEN from Doppler. Please check your authentication.\033[0m"
    exit 1
fi

# 2. Navigate to the frontend directory
FRONTEND_DIR="frontend-procurement"
if [ -d "$FRONTEND_DIR" ]; then
    cd "$FRONTEND_DIR"
else
    echo -e "\033[0;31m❌ Could not find the frontend directory '$FRONTEND_DIR'.\033[0m"
    exit 1
fi

# 3. Execute the Deployment
echo -e "\033[1;33m📦 Pushing production build to Vercel...\033[0m"
npx vercel --prod --force --token "$VERCEL_TOKEN" --scope team_xvK1nhuvsdZp3GNfd4uDJ0DW --yes

echo -e "\033[0;32m✅ Deployment Successful!\033[0m"
