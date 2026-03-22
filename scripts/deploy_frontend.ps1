#!/usr/bin/env pwsh
# deploy_frontend.ps1
# 
# A foolproof script to deploy the frontend to Vercel without relying on the developer
# or AI agent to remember to fetch the Doppler token manually.

$ErrorActionPreference = "Stop"

Write-Host "🚀 Starting Automated Frontend Deployment..." -ForegroundColor Cyan

# 1. Fetch the Token directly from Doppler
Write-Host "🔑 Fetching Vercel token from Doppler (Project: bei-erp, Config: dev)..." -ForegroundColor Yellow
$VercelToken = C:\Users\Sam\bin\doppler.exe secrets get VERCEL_TOKEN --project bei-erp --config dev --plain

if (-not $VercelToken) {
    Write-Error "❌ Failed to retrieve VERCEL_TOKEN from Doppler. Please check your authentication."
    exit 1
}

# 2. Navigate to the frontend directory
$FrontendDir = "frontend-procurement"
if (Test-Path $FrontendDir) {
    Push-Location $FrontendDir
} else {
    Write-Error "❌ Could not find the frontend directory '$FrontendDir'."
    exit 1
}

# 3. Execute the Deployment
Write-Host "📦 Pushing production build to Vercel..." -ForegroundColor Yellow
npx vercel --prod --force --token $VercelToken --scope team_xvK1nhuvsdZp3GNfd4uDJ0DW --yes

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Deployment Successful!" -ForegroundColor Green
} else {
    Write-Error "❌ Deployment Failed."
}

Pop-Location
