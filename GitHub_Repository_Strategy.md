# GitHub Repository Strategy for Frappe HRMS

## 🎯 **Current Situation**

You're currently in the **Frappe HRMS** repository (cloned from `frappe/hrms`). This is the **upstream** repository that contains the base HRMS application.

## 📋 **Recommended Approach**

### **Option 1: Fork + Custom Repo (Recommended for Production)**

Create **TWO** repositories:

1. **Fork of Frappe HRMS** (for tracking upstream updates)
   - Fork `frappe/hrms` to your GitHub account
   - Keep it synced with upstream for updates
   - **Purpose**: Track official HRMS updates

2. **Your Production Repository** (for your customizations)
   - Create a new private repo: `frappe-hrms-production` or `bei-hrms`
   - Contains your customizations, AWS configs, company data
   - **Purpose**: Your production deployment

**Workflow:**
```
Upstream (frappe/hrms)
    ↓
Your Fork (your-username/hrms)
    ↓
Your Production Repo (your-username/frappe-hrms-production)
    └── Contains: Custom configs, AWS setup, company data
```

### **Option 2: Single Custom Repo (Simpler)**

Create **ONE** repository for your production setup:

1. **Your Production Repository**
   - Create: `frappe-hrms-production` or `bei-hrms`
   - Copy your customizations and configs
   - **Purpose**: Everything in one place

**Workflow:**
```
Upstream (frappe/hrms) - Reference only
    ↓
Your Production Repo (your-username/frappe-hrms-production)
    └── Contains: Everything you need
```

---

## ✅ **RECOMMENDED: Option 1 (Fork + Custom Repo)**

### **Why This Approach?**

1. **Track Updates**: Easily pull updates from official Frappe HRMS
2. **Separation**: Keep your customizations separate from base code
3. **Clean History**: Your production repo has only your changes
4. **Flexibility**: Update base HRMS without affecting your customizations

### **Setup Steps:**

#### **Step 1: Fork Frappe HRMS**

1. Go to https://github.com/frappe/hrms
2. Click **"Fork"** button (top right)
3. Fork to your account: `your-username/hrms`

#### **Step 2: Create Production Repository**

1. Go to https://github.com/new
2. Create: `frappe-hrms-production` (Private)
3. **Don't initialize** with README

#### **Step 3: Set Up Your Local Repository**

```bash
# Add your fork as upstream
git remote add fork https://github.com/YOUR_USERNAME/hrms.git

# Add production repo
git remote add production https://github.com/YOUR_USERNAME/frappe-hrms-production.git

# Verify
git remote -v
```

#### **Step 4: Push to Production Repo**

```bash
# Create production branch
git checkout -b production

# Add your custom files
git add .
git commit -m "Initial production setup with AWS config"

# Push to production repo
git push production production
```

---

## 🚀 **Quick Start: Create Production Repo Now**

Since you're already in a git repo, here's the fastest path:

### **Step 1: Create GitHub Repository**

1. Go to https://github.com/new
2. **Repository name**: `frappe-hrms-production` (or `bei-hrms`)
3. **Visibility**: ✅ **Private** (recommended)
4. **Don't check** any initialization options
5. Click **"Create repository"**

### **Step 2: Add Production Remote**

```bash
# Add your new repo as a remote
git remote add production https://github.com/YOUR_USERNAME/frappe-hrms-production.git

# Or if using SSH
git remote add production git@github.com:YOUR_USERNAME/frappe-hrms-production.git
```

### **Step 3: Create Production Branch**

```bash
# Create a clean production branch
git checkout -b production

# Add all your customizations
git add .
git commit -m "Production setup: AWS config, company data, customizations"

# Push to production repo
git push production production
```

### **Step 4: Set Production as Default**

In your production repo on GitHub:
- Go to Settings → Branches
- Set `production` as default branch

---

## 📁 **What to Include in Production Repo**

### ✅ **Include:**
- `aws/` - AWS configuration and Terraform
- `docker/` - Docker setup (if customized)
- `BEI Company Details/` - Your company data
- `.cursor/` - Cursor/MCP configs (without secrets)
- `*.md` - Documentation
- `.github/workflows/` - CI/CD workflows
- Custom scripts (`deploy.sh`, `setup-github-repo.sh`)

### ❌ **Exclude (via .gitignore):**
- `.env` files
- AWS credentials (`.aws/`)
- Private keys (`.pem`, `.key`)
- Database passwords
- `*.tfstate` files
- Sensitive company data (if any)

---

## 🔄 **Deployment Workflow**

### **After Setting Up GitHub:**

```
1. Make changes locally
   ↓
2. Commit: git commit -m "Description"
   ↓
3. Push to GitHub: git push production production
   ↓
4. Deploy to AWS:
   Option A: Automated (GitHub Actions)
   Option B: Manual (SSH + git pull)
```

### **Option A: Automated Deployment**

GitHub Actions will automatically deploy when you push:

```yaml
# .github/workflows/deploy-aws.yml (already created)
on:
  push:
    branches: [production]
```

**Setup:**
1. Add GitHub Secrets (AWS credentials, EC2 details)
2. Push to `production` branch
3. GitHub Actions deploys automatically

### **Option B: Manual Deployment**

SSH to AWS EC2 and pull:

```bash
# On AWS EC2
cd /home/ubuntu/frappe-hrms
git pull production production
./deploy.sh
```

---

## 🎯 **Answer to Your Question**

> **"Do we create a repo for our project first on GitHub before deploying on AWS?"**

### **YES - Recommended Order:**

```
1. ✅ Create GitHub Repository FIRST
   ↓
2. ✅ Push your code to GitHub
   ↓
3. ✅ Set up CI/CD (optional)
   ↓
4. ✅ Deploy to AWS
```

### **Why This Order?**

1. **Version Control**: Track all changes before deployment
2. **Backup**: Code is safe in GitHub
3. **CI/CD**: Automate deployments from GitHub
4. **Rollback**: Easy to revert if deployment fails
5. **Collaboration**: Team can review before deployment

### **Alternative (Not Recommended):**

```
1. Deploy to AWS first
2. Create GitHub repo later
```

**Problems:**
- No version control during initial setup
- Hard to track what was deployed
- Difficult to rollback
- No automated deployments

---

## 📝 **Action Items**

1. ✅ **Create GitHub Repository** (5 minutes)
   - Go to https://github.com/new
   - Name: `frappe-hrms-production`
   - Set as Private

2. ✅ **Add Production Remote** (2 minutes)
   ```bash
   git remote add production https://github.com/YOUR_USERNAME/frappe-hrms-production.git
   ```

3. ✅ **Push Your Code** (5 minutes)
   ```bash
   git checkout -b production
   git add .
   git commit -m "Production setup"
   git push production production
   ```

4. ✅ **Set Up GitHub Secrets** (10 minutes)
   - Go to repo Settings → Secrets
   - Add AWS credentials, EC2 details

5. ✅ **Deploy to AWS** (30+ minutes)
   - Use Terraform to create infrastructure
   - Deploy using GitHub Actions or manual

---

## 🔗 **Quick Commands**

```bash
# Check current remotes
git remote -v

# Add production remote
git remote add production https://github.com/YOUR_USERNAME/frappe-hrms-production.git

# Create and push production branch
git checkout -b production
git add .
git commit -m "Production setup"
git push production production

# Daily workflow
git add .
git commit -m "Description"
git push production production
```

---

**Last Updated**: November 2025
**Status**: Ready to implement

