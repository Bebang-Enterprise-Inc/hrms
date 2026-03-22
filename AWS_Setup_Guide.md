# AWS Hosting Setup Guide for Frappe HRMS

This guide will help you set up Frappe HRMS on AWS, configure AWS CLI, and integrate AWS MCP with Cursor.

---

## 📋 **PREREQUISITES**

- AWS Account with admin access
- AWS Access Key ID and Secret Access Key
- Basic knowledge of AWS services (EC2, RDS, S3, etc.)
- Docker installed locally (for testing)
- Git installed

---

## 🔑 **STEP 1: AWS CLI Setup**

### 1.1 Install AWS CLI

**Windows (using Git Bash):**
```bash
# Download AWS CLI v2 installer
curl "https://awscli.amazonaws.com/awscli-exe-windows-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Verify installation
aws --version
```

**Alternative (using Chocolatey):**
```bash
choco install awscli
```

**macOS:**
```bash
brew install awscli
```

**Linux:**
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

### 1.2 Create AWS IAM User and Access Keys

1. **Log in to AWS Console** → Go to IAM (Identity and Access Management)
2. **Create IAM User:**
   - Click "Users" → "Add users"
   - Username: `frappe-hrms-admin` (or your preferred name)
   - Access type: **Programmatic access**
   - Click "Next"

3. **Attach Policies:**
   - Select "Attach policies directly"
   - Add these policies (minimum):
     - `AmazonEC2FullAccess` (for EC2 instances)
     - `AmazonRDSFullAccess` (for RDS database)
     - `AmazonS3FullAccess` (for backups/storage)
     - `AmazonVPCFullAccess` (for networking)
     - `IAMFullAccess` (for creating roles)
     - `CloudFormationFullAccess` (for infrastructure as code)
   - Click "Next" → "Create user"

4. **Save Access Keys:**
   - **⚠️ CRITICAL**: Download or copy:
     - **Access Key ID**: `AKIA...`
     - **Secret Access Key**: `wJalr...` (only shown once!)
   - Store these securely (we'll use them in Step 1.3)

### 1.3 Configure AWS CLI

Run this command and enter your credentials when prompted:

```bash
aws configure
```

**Enter the following:**
```
AWS Access Key ID [None]: AKIA... (your access key)
AWS Secret Access Key [None]: wJalr... (your secret key)
Default region name [None]: ap-southeast-1 (or your preferred region)
Default output format [None]: json
```

**Verify Configuration:**
```bash
aws sts get-caller-identity
```

You should see your AWS account ID and user ARN.

### 1.4 Create AWS Credentials File (Alternative Method)

If you prefer to configure manually, create/edit `~/.aws/credentials`:

```ini
[default]
aws_access_key_id = AKIA...
aws_secret_access_key = wJalr...
region = ap-southeast-1
output = json

[frappe-hrms]
aws_access_key_id = AKIA...
aws_secret_access_key = wJalr...
region = ap-southeast-1
output = json
```

---

## 🤖 **STEP 2: AWS MCP (Model Context Protocol) Setup**

AWS MCP allows Cursor to interact with AWS services directly.

### 2.1 Install AWS MCP Server

The AWS MCP server is typically installed via Cursor's MCP configuration. We'll set it up in the project.

### 2.2 Configure MCP in Cursor

1. **Open Cursor Settings** → Extensions → MCP
2. **Add AWS MCP Server Configuration**

Create or edit `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "aws": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-aws"
      ],
      "env": {
        "AWS_ACCESS_KEY_ID": "AKIA...",
        "AWS_SECRET_ACCESS_KEY": "wJalr...",
        "AWS_REGION": "ap-southeast-1"
      }
    }
  }
}
```

**⚠️ SECURITY NOTE**: For production, use environment variables or AWS IAM roles instead of hardcoding credentials.

### 2.3 Alternative: Use Environment Variables

Create `.env` file (add to `.gitignore`):

```bash
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=wJalr...
AWS_REGION=ap-southeast-1
AWS_DEFAULT_REGION=ap-southeast-1
```

Then reference in MCP config:

```json
{
  "mcpServers": {
    "aws": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-aws"
      ],
      "env": {
        "AWS_ACCESS_KEY_ID": "${AWS_ACCESS_KEY_ID}",
        "AWS_SECRET_ACCESS_KEY": "${AWS_SECRET_ACCESS_KEY}",
        "AWS_REGION": "${AWS_REGION}"
      }
    }
  }
}
```

---

## ☁️ **STEP 3: AWS Infrastructure Setup**

### 3.1 Choose Your Deployment Option

**Option A: EC2 (Simple, Single Server)**
- ✅ Easy setup
- ✅ Cost-effective for small teams
- ❌ Manual scaling
- ❌ Single point of failure

**Option B: ECS Fargate (Containerized, Managed)**
- ✅ Auto-scaling
- ✅ No server management
- ✅ High availability
- ❌ More complex setup
- ❌ Higher cost

**Option C: EKS (Kubernetes)**
- ✅ Maximum flexibility
- ✅ Enterprise-grade
- ❌ Complex setup
- ❌ Requires Kubernetes knowledge

**Recommendation**: Start with **Option A (EC2)** for initial setup, then migrate to **Option B (ECS)** for production.

### 3.2 Infrastructure Requirements

**Minimum Requirements:**
- **EC2 Instance**: t3.medium (2 vCPU, 4 GB RAM) - $0.0416/hour
- **RDS Database**: db.t3.medium (MariaDB 10.8) - $0.068/hour
- **Storage**: 100 GB EBS (SSD) - $10/month
- **S3 Bucket**: For backups - $0.023/GB/month

**Recommended for Production:**
- **EC2 Instance**: t3.large (2 vCPU, 8 GB RAM) or t3.xlarge (4 vCPU, 16 GB RAM)
- **RDS Database**: db.t3.large or db.r5.large (for better performance)
- **Storage**: 500 GB EBS (SSD) with automated snapshots
- **Load Balancer**: Application Load Balancer (ALB) - $0.0225/hour
- **Auto Scaling Group**: For high availability

**Estimated Monthly Cost:**
- Development: ~$50-80/month
- Production: ~$200-400/month (with ALB, auto-scaling, backups)

---

## 🚀 **STEP 4: Quick Start - EC2 Deployment**

### 4.1 Launch EC2 Instance

**Using AWS CLI:**

```bash
# Create security group
aws ec2 create-security-group \
  --group-name frappe-hrms-sg \
  --description "Security group for Frappe HRMS"

# Get your security group ID (from output above)
SG_ID="sg-xxxxxxxxxxxxx"

# Allow SSH (port 22)
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0

# Allow HTTP (port 80)
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0

# Allow HTTPS (port 443)
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0

# Allow Frappe (port 8000) - restrict to your IP for security
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 8000 \
  --cidr YOUR_IP_ADDRESS/32

# Launch EC2 instance
aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type t3.medium \
  --key-name your-key-pair-name \
  --security-group-ids $SG_ID \
  --subnet-id subnet-xxxxxxxxx \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Frappe-HRMS}]'
```

**Using AWS Console:**
1. Go to EC2 → Launch Instance
2. Choose **Ubuntu Server 22.04 LTS** (or latest)
3. Instance type: **t3.medium**
4. Configure security group (ports 22, 80, 443, 8000)
5. Create/select key pair for SSH access
6. Launch instance

### 4.2 Connect to EC2 Instance

```bash
# Get your instance public IP
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=Frappe-HRMS" \
  --query "Reservations[*].Instances[*].PublicIpAddress" \
  --output text

# SSH into instance
ssh -i your-key.pem ubuntu@YOUR_INSTANCE_IP
```

### 4.3 Install Docker on EC2

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify
docker --version
docker-compose --version
```

### 4.4 Deploy Frappe HRMS on EC2

```bash
# Clone repository
git clone https://github.com/frappe/hrms.git
cd hrms/docker

# Edit docker-compose.yml for production (see Step 4.5)
# Then start services
docker-compose up -d

# Check logs
docker-compose logs -f
```

---

## 🗄️ **STEP 5: RDS Database Setup**

### 5.1 Create RDS MariaDB Instance

**Using AWS CLI:**

```bash
# Create DB subnet group (if not exists)
aws rds create-db-subnet-group \
  --db-subnet-group-name frappe-hrms-subnet-group \
  --db-subnet-group-description "Subnet group for Frappe HRMS" \
  --subnet-ids subnet-xxxxx subnet-yyyyy

# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier frappe-hrms-db \
  --db-instance-class db.t3.medium \
  --engine mariadb \
  --engine-version 10.8 \
  --master-username admin \
  --master-user-password YOUR_SECURE_PASSWORD \
  --allocated-storage 100 \
  --storage-type gp3 \
  --vpc-security-group-ids $SG_ID \
  --db-subnet-group-name frappe-hrms-subnet-group \
  --backup-retention-period 7 \
  --multi-az
```

**Using AWS Console:**
1. Go to RDS → Create Database
2. Engine: **MariaDB 10.8**
3. Template: **Production** (or Dev/Test)
4. DB instance class: **db.t3.medium**
5. Storage: 100 GB, **gp3**
6. VPC: Your VPC
7. Security group: Create new or use existing
8. Master username: `admin`
9. Master password: (strong password)
10. Enable **Multi-AZ** for production
11. Enable **Automated backups** (7 days retention)
12. Create database

### 5.2 Update Frappe Configuration

Edit `docker/docker-compose.yml` to use RDS:

```yaml
services:
  frappe:
    environment:
      - DB_HOST=your-rds-endpoint.region.rds.amazonaws.com
      - DB_PORT=3306
      - DB_USER=admin
      - DB_PASSWORD=YOUR_SECURE_PASSWORD
      - DB_NAME=frappe_hrms
```

---

## 📦 **STEP 6: S3 Backup Configuration**

### 6.1 Create S3 Bucket

```bash
# Create bucket
aws s3 mb s3://frappe-hrms-backups-$(date +%s) \
  --region ap-southeast-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket frappe-hrms-backups-xxxxx \
  --versioning-configuration Status=Enabled

# Enable lifecycle policy (delete old backups after 90 days)
aws s3api put-bucket-lifecycle-configuration \
  --bucket frappe-hrms-backups-xxxxx \
  --lifecycle-configuration file://lifecycle.json
```

### 6.2 Configure Frappe to Backup to S3

Add to your EC2 instance:

```bash
# Install AWS CLI on EC2
sudo apt install awscli -y
aws configure

# Create backup script
cat > /home/ubuntu/backup-to-s3.sh << 'EOF'
#!/bin/bash
BUCKET="frappe-hrms-backups-xxxxx"
SITE="hrms.localhost"
DATE=$(date +%Y%m%d_%H%M%S)

cd /home/ubuntu/hrms/docker
docker-compose exec -T frappe bench --site $SITE backup --with-files
docker-compose exec -T frappe bench --site $SITE backup --with-files | \
  aws s3 cp - s3://$BUCKET/backups/$DATE.tar.gz
EOF

chmod +x /home/ubuntu/backup-to-s3.sh

# Add to crontab (daily backup at 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * /home/ubuntu/backup-to-s3.sh") | crontab -
```

---

## 🔒 **STEP 7: Security Best Practices**

### 7.1 Use IAM Roles Instead of Access Keys

**Create IAM Role for EC2:**

```bash
# Create role
aws iam create-role \
  --role-name FrappeHRMS-EC2-Role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ec2.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# Attach policies
aws iam attach-role-policy \
  --role-name FrappeHRMS-EC2-Role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

# Create instance profile
aws iam create-instance-profile \
  --instance-profile-name FrappeHRMS-EC2-Profile

aws iam add-role-to-instance-profile \
  --instance-profile-name FrappeHRMS-EC2-Profile \
  --role-name FrappeHRMS-EC2-Role

# Attach to EC2 instance
aws ec2 associate-iam-instance-profile \
  --instance-id i-xxxxxxxxxxxxx \
  --iam-instance-profile Name=FrappeHRMS-EC2-Profile
```

### 7.2 Enable SSL/TLS with Let's Encrypt

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Get certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo certbot renew --dry-run
```

### 7.3 Restrict Security Groups

- Remove public access to port 8000 (only allow from your IP)
- Use VPN or AWS Systems Manager Session Manager for SSH
- Enable CloudWatch logging and monitoring

---

## 📊 **STEP 8: Monitoring and Logging**

### 8.1 Enable CloudWatch

```bash
# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i amazon-cloudwatch-agent.deb

# Configure (interactive)
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-config-wizard
```

### 8.2 Set Up Alarms

```bash
# CPU utilization alarm
aws cloudwatch put-metric-alarm \
  --alarm-name frappe-hrms-high-cpu \
  --alarm-description "Alert when CPU exceeds 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/EC2 \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2
```

---

## 🧪 **STEP 9: Testing Your Setup**

### 9.1 Verify AWS CLI

```bash
aws sts get-caller-identity
aws ec2 describe-instances
aws rds describe-db-instances
aws s3 ls
```

### 9.2 Verify MCP Connection

In Cursor, try asking:
- "List my EC2 instances"
- "Show me RDS databases"
- "What's my S3 bucket usage?"

### 9.3 Test Frappe HRMS

1. Access: `http://YOUR_EC2_IP:8000`
2. Login: Administrator / admin
3. Verify all modules load correctly
4. Test database connectivity
5. Test file uploads (should work with S3)

---

## 📝 **STEP 10: Next Steps**

1. **Set up Domain Name**: Route 53 or external DNS
2. **Configure Load Balancer**: For high availability
3. **Set up Auto Scaling**: For traffic spikes
4. **Enable Multi-AZ RDS**: For database redundancy
5. **Configure CDN**: CloudFront for static assets
6. **Set up CI/CD**: GitHub Actions or AWS CodePipeline

---

## 🆘 **TROUBLESHOOTING**

### Issue: AWS CLI not found
**Solution**: Add to PATH or reinstall AWS CLI

### Issue: MCP server not connecting
**Solution**: Check credentials in `.cursor/mcp.json` and restart Cursor

### Issue: EC2 instance not accessible
**Solution**: Check security group rules and instance status

### Issue: RDS connection timeout
**Solution**: Verify security group allows EC2 → RDS (port 3306)

### Issue: Docker containers not starting
**Solution**: Check logs: `docker-compose logs` and verify environment variables

---

## 📚 **ADDITIONAL RESOURCES**

- [AWS CLI Documentation](https://docs.aws.amazon.com/cli/)
- [Frappe Cloud Documentation](https://frappecloud.com/docs)
- [AWS MCP Server](https://github.com/modelcontextprotocol/servers/tree/main/src/aws)
- [Frappe Deployment Guide](https://frappeframework.com/docs/user/en/installation)

---

**Last Updated**: November 2025
**Version**: 1.0


