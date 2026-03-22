# AWS Quick Start - Frappe HRMS

## 🚀 Quick Setup (5 Minutes)

### 1. Install AWS CLI
```bash
# Windows (Git Bash)
curl "https://awscli.amazonaws.com/awscli-exe-windows-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Verify
aws --version
```

### 2. Configure AWS CLI
```bash
aws configure
# Enter: Access Key ID, Secret Key, Region (ap-southeast-1), Output (json)
```

### 3. Run Setup Script
```bash
./aws-setup.sh
```

### 4. Verify Setup
```bash
aws sts get-caller-identity
```

---

## 📋 Prerequisites Checklist

- [ ] AWS Account created
- [ ] IAM User created with access keys
- [ ] AWS CLI installed
- [ ] AWS CLI configured (`aws configure`)
- [ ] MCP configuration created (`.cursor/mcp.json`)
- [ ] Cursor restarted (to load MCP)

---

## 🔑 Getting AWS Access Keys

1. Go to AWS Console → IAM → Users
2. Create user: `frappe-hrms-admin`
3. Attach policies:
   - `AmazonEC2FullAccess`
   - `AmazonRDSFullAccess`
   - `AmazonS3FullAccess`
   - `AmazonVPCFullAccess`
4. Create access key → Save Access Key ID and Secret

---

## 🏗️ Infrastructure Options

### Option 1: Manual EC2 Setup (Simplest)
- Follow `AWS_Setup_Guide.md` Step 4
- Launch EC2 instance
- Install Docker
- Deploy Frappe HRMS

### Option 2: Terraform (Infrastructure as Code)
```bash
cd aws/terraform
terraform init
terraform plan
terraform apply
```

### Option 3: AWS Console (GUI)
- Use AWS Console to create resources manually
- Follow `AWS_Setup_Guide.md` for step-by-step

---

## 💰 Estimated Costs

**Development:**
- EC2 t3.medium: ~$30/month
- RDS db.t3.medium: ~$50/month
- Storage: ~$10/month
- **Total: ~$90/month**

**Production:**
- EC2 t3.large: ~$60/month
- RDS db.t3.large: ~$100/month
- ALB: ~$16/month
- Storage: ~$20/month
- **Total: ~$200/month**

---

## 🧪 Test Your Setup

```bash
# Test AWS CLI
aws sts get-caller-identity

# Test EC2 access
aws ec2 describe-instances

# Test RDS access
aws rds describe-db-instances

# Test S3 access
aws s3 ls
```

---

## 📚 Next Steps

1. Read `AWS_Setup_Guide.md` for detailed instructions
2. Choose deployment option (EC2/ECS/EKS)
3. Set up RDS database
4. Configure S3 for backups
5. Deploy Frappe HRMS

---

## 🆘 Common Issues

**"AWS CLI not found"**
→ Install AWS CLI (see Step 1)

**"Access Denied"**
→ Check IAM user permissions

**"Region not found"**
→ Use valid region: `ap-southeast-1`, `us-east-1`, etc.

**"MCP not working"**
→ Restart Cursor after configuring `.cursor/mcp.json`

---

**Need Help?** See `AWS_Setup_Guide.md` for detailed troubleshooting.


