# GitHub Repository Setup Guide

## 🎯 **Why Create GitHub Repo First?**

### ✅ **Benefits:**

1. **Version Control**: Track all changes, rollback if needed
2. **Backup**: Your code is safe in the cloud
3. **CI/CD**: Automate deployments from GitHub to AWS
4. **Collaboration**: Multiple developers can work together
5. **Documentation**: Keep all project files in one place
6. **Deployment**: Deploy directly from GitHub to AWS (no manual file transfer)

### ❌ **Without GitHub:**
- Manual file uploads to AWS (slow, error-prone)
- No version history
- No automated deployments
- Hard to collaborate
- Risk of losing code

---

## 📋 **Recommended Workflow**

```
1. Create GitHub Repo
   ↓
2. Push Your Code to GitHub
   ↓
3. Set Up CI/CD (GitHub Actions)
   ↓
4. Deploy to AWS (Automated or Manual)
```

---

## 🚀 **STEP 1: Create GitHub Repository**

### Option A: Using GitHub Website

1. **Go to GitHub.com** → Sign in
2. **Click "+"** (top right) → "New repository"
3. **Repository Settings:**
   - **Name**: `frappe-hrms-production` (or your preferred name)
   - **Description**: "Frappe HRMS for BEI - Production"
   - **Visibility**: 
     - ✅ **Private** (recommended for production)
     - ⚠️ Public (if you want it open source)
   - **Initialize**: 
     - ❌ Don't check "Add README" (we already have one)
     - ❌ Don't add .gitignore (we have one)
     - ❌ Don't add license (unless needed)
4. **Click "Create repository"**

### Option B: Using GitHub CLI

```bash
# Install GitHub CLI (if not installed)
# Windows: choco install gh
# macOS: brew install gh
# Linux: curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg

# Login to GitHub
gh auth login

# Create repository
gh repo create frappe-hrms-production \
  --private \
  --description "Frappe HRMS for BEI - Production" \
  --source=. \
  --remote=origin \
  --push
```

---

## 📤 **STEP 2: Push Your Code to GitHub**

### 2.1 Check Current Git Status

```bash
# Check if already a git repo
git status

# If not initialized, initialize it
git init
```

### 2.2 Add Remote Repository

```bash
# Add GitHub as remote (replace YOUR_USERNAME and REPO_NAME)
git remote add origin https://github.com/YOUR_USERNAME/frappe-hrms-production.git

# Or if using SSH
git remote add origin git@github.com:YOUR_USERNAME/frappe-hrms-production.git

# Verify
git remote -v
```

### 2.3 Commit and Push

```bash
# Stage all files
git add .

# Commit
git commit -m "Initial commit: Frappe HRMS setup with AWS configuration"

# Push to GitHub
git branch -M main
git push -u origin main
```

**⚠️ Important**: Make sure sensitive files are in `.gitignore`:
- `.env` files
- AWS credentials (`.aws/`)
- Private keys (`.pem`, `.key`)
- Database passwords

---

## 🔐 **STEP 3: Set Up GitHub Secrets (For CI/CD)**

If you want automated deployments, store AWS credentials as GitHub Secrets:

1. **Go to your GitHub repo** → Settings → Secrets and variables → Actions
2. **Click "New repository secret"**
3. **Add these secrets:**

   - `AWS_ACCESS_KEY_ID`: Your AWS access key
   - `AWS_SECRET_ACCESS_KEY`: Your AWS secret key
   - `AWS_REGION`: `ap-southeast-1` (or your region)
   - `EC2_HOST`: Your EC2 instance IP or domain
   - `EC2_USER`: `ubuntu` (or your EC2 user)
   - `EC2_SSH_KEY`: Your SSH private key (for deployment)

---

## 🤖 **STEP 4: Set Up CI/CD (Optional but Recommended)**

### 4.1 Create GitHub Actions Workflow

Create `.github/workflows/deploy-aws.yml`:

```yaml
name: Deploy to AWS

on:
  push:
    branches:
      - main
      - production
  workflow_dispatch: # Manual trigger

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ secrets.AWS_REGION }}
      
      - name: Deploy to EC2
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ${{ secrets.EC2_USER }}
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            cd /home/ubuntu/frappe-hrms
            git pull origin main
            docker-compose down
            docker-compose up -d --build
            docker-compose exec frappe bench --site hrms.yourdomain.com migrate
            docker-compose exec frappe bench --site hrms.yourdomain.com clear-cache
```

### 4.2 Alternative: Simple Deployment Script

If you prefer manual deployment, create `deploy.sh`:

```bash
#!/bin/bash
# deploy.sh - Manual deployment script

set -e

echo "🚀 Deploying to AWS..."

# Pull latest code
git pull origin main

# Restart services
cd docker
docker-compose down
docker-compose up -d --build

# Run migrations
docker-compose exec -T frappe bench --site hrms.yourdomain.com migrate

# Clear cache
docker-compose exec -T frappe bench --site hrms.yourdomain.com clear-cache

echo "✅ Deployment complete!"
```

---

## 🔄 **STEP 5: Deployment Workflow Options**

### Option A: Automated (CI/CD)
```
Developer pushes code → GitHub → GitHub Actions → AWS EC2
```
- ✅ Automatic deployment on every push
- ✅ No manual steps
- ✅ Consistent deployments

### Option B: Manual (SSH)
```
Developer pushes code → GitHub → SSH to EC2 → git pull → restart
```
- ✅ More control
- ✅ Can test before deploying
- ❌ Manual steps required

### Option C: Hybrid
```
Developer pushes code → GitHub → Manual trigger → GitHub Actions → AWS
```
- ✅ Best of both worlds
- ✅ Deploy when ready
- ✅ Still automated

---

## 📁 **STEP 6: Repository Structure**

Your GitHub repo should have:

```
frappe-hrms-production/
├── .github/
│   └── workflows/
│       └── deploy-aws.yml          # CI/CD workflows
├── .cursor/
│   └── mcp.json                    # AWS MCP config
├── aws/
│   ├── docker-compose.production.yml
│   └── terraform/                  # Infrastructure as code
├── docker/
│   ├── docker-compose.yml          # Local development
│   └── init.sh
├── BEI Company Details/            # Your company configs
├── .gitignore                      # Exclude sensitive files
├── README.md
├── AWS_Setup_Guide.md
├── GitHub_Setup_Guide.md
└── ... (other project files)
```

---

## 🔒 **STEP 7: Security Best Practices**

### 7.1 What to Commit ✅
- Configuration files (without secrets)
- Documentation
- Code
- Docker files
- Terraform files (without state)

### 7.2 What NOT to Commit ❌
- `.env` files
- AWS credentials
- Private keys (`.pem`, `.key`)
- Database passwords
- `*.tfstate` files (Terraform state)
- `.aws/` directory

### 7.3 Verify .gitignore

Make sure your `.gitignore` includes:

```gitignore
# Environment variables
.env
.env.local
.env.production

# AWS
.aws/
*.pem
*.key

# Terraform
.terraform/
*.tfstate
*.tfstate.backup

# Sensitive data
**/secrets/
**/credentials/
```

---

## 🧪 **STEP 8: Test Your Setup**

### 8.1 Test Git Push

```bash
# Make a small change
echo "# Test" >> test.md

# Commit and push
git add test.md
git commit -m "Test: Verify GitHub connection"
git push origin main

# Check GitHub - you should see the change
```

### 8.2 Test Deployment (if CI/CD set up)

1. Make a change to a non-critical file
2. Commit and push
3. Check GitHub Actions tab
4. Verify deployment succeeded

---

## 📊 **STEP 9: Branching Strategy (Recommended)**

For production, use branches:

```
main          → Production (stable, tested)
├── develop   → Development (testing)
├── staging   → Staging environment
└── feature/*  → Feature branches
```

**Workflow:**
1. Create feature branch: `git checkout -b feature/new-feature`
2. Develop and commit
3. Push: `git push origin feature/new-feature`
4. Create Pull Request to `develop`
5. Test in staging
6. Merge to `main` for production

---

## 🆘 **TROUBLESHOOTING**

### Issue: "Repository not found"
**Solution**: Check repository name and permissions

### Issue: "Permission denied"
**Solution**: 
- Use SSH keys: `ssh-keygen -t ed25519 -C "your_email@example.com"`
- Add public key to GitHub: Settings → SSH and GPG keys

### Issue: "Large file push fails"
**Solution**: 
- Use Git LFS for large files
- Or exclude large files in `.gitignore`

### Issue: "Credentials exposed in commit"
**Solution**:
1. Remove from history: `git filter-branch` or BFG Repo-Cleaner
2. Rotate exposed credentials immediately
3. Add to `.gitignore` to prevent future commits

---

## 📚 **NEXT STEPS**

After setting up GitHub:

1. ✅ **Push your code** to GitHub
2. ✅ **Set up CI/CD** (optional but recommended)
3. ✅ **Deploy to AWS** using the deployment method you chose
4. ✅ **Set up monitoring** to track deployments
5. ✅ **Document your deployment process**

---

## 🔗 **QUICK REFERENCE**

```bash
# Initialize repo (if not done)
git init

# Add remote
git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git

# First push
git add .
git commit -m "Initial commit"
git branch -M main
git push -u origin main

# Daily workflow
git add .
git commit -m "Description of changes"
git push origin main
```

---

**Last Updated**: November 2025
**Version**: 1.0


