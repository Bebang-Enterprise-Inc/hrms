# Google Chat Integration App - Deployment Guide

## Prerequisites
- SSH access to EC2 instance (13.214.59.15)
- Or AWS SSM access via console

## Deployment Steps

### Option 1: Direct Copy via SCP (if SSH key available)

```bash
# From local machine
scp -r gchat_integration ubuntu@13.214.59.15:/tmp/

# Then SSH into the server
ssh ubuntu@13.214.59.15
```

### Option 2: AWS SSM Session Manager (via AWS Console)

1. Go to AWS Console > EC2 > Instances
2. Select `i-026b7477d27bd46d6`
3. Click "Connect" > "Session Manager" > "Connect"

### Once on the Server

```bash
# 1. Copy app into Docker container
cd /home/ubuntu/bebang-hrms

# If using Option 1, copy from /tmp:
docker cp /tmp/gchat_integration bebang-hrms-backend-1:/home/frappe/frappe-bench/apps/

# 2. Enter the container
docker exec -it bebang-hrms-backend-1 bash

# 3. Install Python dependencies
cd /home/frappe/frappe-bench
pip install google-auth google-api-python-client

# 4. Install the app to the site
bench --site hrms.bebang.ph install-app gchat_integration

# 5. Restart services
bench restart

# 6. Exit container
exit
```

### Option 3: Create App Directly on Server

If you can't copy files, run these commands inside the container:

```bash
docker exec -it bebang-hrms-backend-1 bash
cd /home/frappe/frappe-bench

# Create app structure
bench new-app gchat_integration --no-git

# Then manually paste the contents of api.py and hooks.py
# Or use the curl commands below to fetch from a gist
```

## Verify Installation

```bash
# Inside container
bench --site hrms.bebang.ph list-apps
# Should show: gchat_integration
```

## Configure Google Chat Settings

After deployment, configure via Frappe:

1. Go to https://hq.bebang.ph/app/google-chat-settings
2. Enable the integration
3. Enter service account credentials:
   - Client Email: `task-manager-service@quiet-walker-475722-s2.iam.gserviceaccount.com`
   - Private Key: (from credentials file)
   - Token URI: `https://oauth2.googleapis.com/token`

## Test the Integration

```bash
# Inside container, test the API
bench --site hrms.bebang.ph execute gchat_integration.api.send_to_google_chat \
  --args '["ERP Automation Committee", "Test message from Frappe!"]'
```

