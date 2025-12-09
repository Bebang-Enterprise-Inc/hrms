#!/bin/bash

# AWS Setup Script for Frappe HRMS
# This script helps configure AWS CLI and verify setup

set -e

echo "🚀 Frappe HRMS - AWS Setup Script"
echo "===================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if AWS CLI is installed
check_aws_cli() {
    echo "📦 Checking AWS CLI installation..."
    if command -v aws &> /dev/null; then
        AWS_VERSION=$(aws --version)
        echo -e "${GREEN}✓ AWS CLI installed: $AWS_VERSION${NC}"
        return 0
    else
        echo -e "${RED}✗ AWS CLI not found${NC}"
        echo "Please install AWS CLI first:"
        echo "  Windows: choco install awscli"
        echo "  macOS: brew install awscli"
        echo "  Linux: curl 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip' -o 'awscliv2.zip' && unzip awscliv2.zip && sudo ./aws/install"
        return 1
    fi
}

# Configure AWS CLI
configure_aws() {
    echo ""
    echo "🔑 Configuring AWS CLI..."
    echo "You'll need:"
    echo "  - AWS Access Key ID"
    echo "  - AWS Secret Access Key"
    echo "  - Default region (e.g., ap-southeast-1)"
    echo ""
    read -p "Press Enter to continue with AWS configure..."
    
    aws configure
    
    echo ""
    echo "✅ AWS CLI configured!"
}

# Verify AWS credentials
verify_aws() {
    echo ""
    echo "🔍 Verifying AWS credentials..."
    
    if aws sts get-caller-identity &> /dev/null; then
        echo -e "${GREEN}✓ AWS credentials are valid${NC}"
        echo ""
        echo "Your AWS Account Information:"
        aws sts get-caller-identity
        return 0
    else
        echo -e "${RED}✗ AWS credentials are invalid or not configured${NC}"
        echo "Please run: aws configure"
        return 1
    fi
}

# Test AWS services
test_aws_services() {
    echo ""
    echo "🧪 Testing AWS Services Access..."
    
    # Test EC2
    echo -n "Testing EC2 access... "
    if aws ec2 describe-regions --query 'Regions[0].RegionName' --output text &> /dev/null; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
    fi
    
    # Test RDS
    echo -n "Testing RDS access... "
    if aws rds describe-db-engine-versions --query 'DBEngineVersions[0].Engine' --output text &> /dev/null; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
    fi
    
    # Test S3
    echo -n "Testing S3 access... "
    if aws s3 ls &> /dev/null; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
    fi
}

# Setup MCP configuration
setup_mcp() {
    echo ""
    echo "🤖 Setting up AWS MCP configuration..."
    
    MCP_DIR=".cursor"
    MCP_FILE="$MCP_DIR/mcp.json"
    
    if [ ! -d "$MCP_DIR" ]; then
        mkdir -p "$MCP_DIR"
        echo "Created .cursor directory"
    fi
    
    if [ -f "$MCP_FILE" ]; then
        echo -e "${YELLOW}⚠ MCP configuration already exists${NC}"
        read -p "Overwrite? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Skipping MCP setup..."
            return
        fi
    fi
    
    # Get AWS region from config
    AWS_REGION=$(aws configure get region 2>/dev/null || echo "ap-southeast-1")
    
    cat > "$MCP_FILE" << EOF
{
  "mcpServers": {
    "aws": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-aws"
      ],
      "env": {
        "AWS_REGION": "$AWS_REGION",
        "AWS_DEFAULT_REGION": "$AWS_REGION"
      }
    }
  }
}
EOF
    
    echo -e "${GREEN}✓ MCP configuration created at $MCP_FILE${NC}"
    echo ""
    echo "⚠️  IMPORTANT: AWS credentials will be read from your AWS CLI configuration"
    echo "   For production, consider using IAM roles instead of access keys"
}

# Main execution
main() {
    if ! check_aws_cli; then
        exit 1
    fi
    
    # Check if already configured
    if aws sts get-caller-identity &> /dev/null; then
        echo -e "${GREEN}✓ AWS CLI is already configured${NC}"
        verify_aws
        test_aws_services
    else
        echo -e "${YELLOW}⚠ AWS CLI is not configured${NC}"
        configure_aws
        if ! verify_aws; then
            exit 1
        fi
        test_aws_services
    fi
    
    setup_mcp
    
    echo ""
    echo "===================================="
    echo -e "${GREEN}✅ AWS Setup Complete!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Review AWS_Setup_Guide.md for infrastructure setup"
    echo "2. Restart Cursor to enable AWS MCP"
    echo "3. Test MCP by asking: 'List my EC2 instances'"
    echo ""
}

# Run main function
main


