#!/bin/bash

# Quick GitHub Repository Setup Script
# This script helps you set up your GitHub repo and push your code

set -e

echo "🚀 GitHub Repository Setup for Frappe HRMS"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo -e "${RED}❌ Git is not installed${NC}"
    echo "Please install Git first: https://git-scm.com/downloads"
    exit 1
fi

echo -e "${GREEN}✓ Git is installed${NC}"
echo ""

# Check if already a git repo
if [ -d ".git" ]; then
    echo -e "${YELLOW}⚠️  This is already a git repository${NC}"
    echo "Current remote:"
    git remote -v 2>/dev/null || echo "No remote configured"
    echo ""
    read -p "Continue with setup? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
else
    echo "Initializing git repository..."
    git init
    echo -e "${GREEN}✓ Git repository initialized${NC}"
fi

# Get repository details
echo ""
echo "Enter your GitHub repository details:"
read -p "GitHub username: " GITHUB_USERNAME
read -p "Repository name (e.g., frappe-hrms-production): " REPO_NAME
read -p "Use SSH? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    REPO_URL="git@github.com:${GITHUB_USERNAME}/${REPO_NAME}.git"
else
    REPO_URL="https://github.com/${GITHUB_USERNAME}/${REPO_NAME}.git"
fi

# Check if remote exists
if git remote get-url origin &> /dev/null; then
    echo -e "${YELLOW}⚠️  Remote 'origin' already exists${NC}"
    CURRENT_URL=$(git remote get-url origin)
    echo "Current URL: $CURRENT_URL"
    read -p "Update to new URL? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git remote set-url origin "$REPO_URL"
        echo -e "${GREEN}✓ Remote updated${NC}"
    fi
else
    git remote add origin "$REPO_URL"
    echo -e "${GREEN}✓ Remote added${NC}"
fi

# Check for uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo ""
    echo "You have uncommitted changes. Staging all files..."
    git add .
    
    echo ""
    read -p "Enter commit message (or press Enter for default): " COMMIT_MSG
    if [ -z "$COMMIT_MSG" ]; then
        COMMIT_MSG="Initial commit: Frappe HRMS setup with AWS configuration"
    fi
    
    git commit -m "$COMMIT_MSG"
    echo -e "${GREEN}✓ Changes committed${NC}"
fi

# Check current branch
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "main")

# Push to GitHub
echo ""
echo "Pushing to GitHub..."
echo "Repository: $REPO_URL"
echo "Branch: $CURRENT_BRANCH"
echo ""

read -p "Push to GitHub now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Set upstream branch
    git branch -M main 2>/dev/null || true
    
    # Push
    if git push -u origin main 2>/dev/null || git push -u origin master 2>/dev/null; then
        echo -e "${GREEN}✅ Successfully pushed to GitHub!${NC}"
        echo ""
        echo "Repository URL: https://github.com/${GITHUB_USERNAME}/${REPO_NAME}"
    else
        echo -e "${RED}❌ Push failed${NC}"
        echo ""
        echo "Possible reasons:"
        echo "1. Repository doesn't exist on GitHub - create it first at https://github.com/new"
        echo "2. Authentication failed - set up SSH keys or use GitHub CLI"
        echo "3. No internet connection"
        echo ""
        echo "To create the repository on GitHub:"
        echo "1. Go to https://github.com/new"
        echo "2. Repository name: $REPO_NAME"
        echo "3. Choose Private or Public"
        echo "4. Don't initialize with README (we already have files)"
        echo "5. Click 'Create repository'"
        echo "6. Then run this script again"
    fi
else
    echo "Skipping push. You can push later with:"
    echo "  git push -u origin main"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Verify your repository at: https://github.com/${GITHUB_USERNAME}/${REPO_NAME}"
echo "2. Set up GitHub Secrets for CI/CD (see GitHub_Setup_Guide.md)"
echo "3. Configure AWS deployment (see AWS_Setup_Guide.md)"
echo ""


