#!/bin/bash

# KRT Maker - Quick Deployment Script
# This script automates the deployment process to your VPS

set -e  # Exit on any error

echo "🚀 KRT Maker Deployment Script"
echo "==============================="

# Configuration
VPS_HOST="91.99.161.136"
VPS_USER="xeradb"
DEPLOY_PATH="/var/www/krt"
DOMAIN="krt.xeradb.com"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if we're in the right directory
if [[ ! -f "manage.py" ]]; then
    print_error "Please run this script from the krt_maker directory"
    exit 1
fi

print_status "Starting deployment to $DOMAIN ($VPS_HOST)"

# Step 1: Create deployment package
print_status "Creating deployment package..."
rm -f krt_maker_deploy.tar.gz
tar -czf krt_maker_deploy.tar.gz \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='db.sqlite3' \
    --exclude='media' \
    --exclude='staticfiles' \
    --exclude='.git' \
    .

print_status "Package created: krt_maker_deploy.tar.gz"

# Step 2: Upload to VPS
print_status "Uploading to VPS..."
scp krt_maker_deploy.tar.gz $VPS_USER@$VPS_HOST:/tmp/

# Step 3: Deploy on VPS
print_status "Deploying on VPS..."
ssh $VPS_USER@$VPS_HOST << 'ENDSSH'
set -e

# Create directory if it doesn't exist
sudo mkdir -p /var/www/krt
sudo chown xeradb:xeradb /var/www/krt

# Backup existing deployment (if exists)
if [[ -d "/var/www/krt/manage.py" ]]; then
    echo "Creating backup of existing deployment..."
    sudo cp -r /var/www/krt /var/www/krt_backup_$(date +%Y%m%d_%H%M%S)
fi

# Extract new deployment
cd /var/www/krt
tar -xzf /tmp/krt_maker_deploy.tar.gz

# Set permissions
sudo chown -R xeradb:www-data /var/www/krt
sudo chmod -R 755 /var/www/krt

# Create/update virtual environment
if [[ ! -d "venv" ]]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment and install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r web_requirements.txt

# Check for .env file
if [[ ! -f ".env" ]]; then
    echo "Creating .env file template..."
    cat > .env << 'EOF'
# Django Configuration
SECRET_KEY=your-super-secret-key-change-this-in-production
DEBUG=False
ALLOWED_HOSTS=krt.xeradb.com,91.99.161.136,localhost

# Database Configuration
DATABASE_URL=postgresql://krt_user:Choxos10203040@localhost:5432/krt_production

# API Keys (Optional - for LLM functionality)
# OPENAI_API_KEY=sk-your-openai-key
# ANTHROPIC_API_KEY=your-anthropic-key
# GOOGLE_API_KEY=your-google-key

# AWS Configuration (Optional - for S3 bioRxiv access)
# AWS_ACCESS_KEY_ID=your-aws-key
# AWS_SECRET_ACCESS_KEY=your-aws-secret
EOF
    echo "⚠ IMPORTANT: Edit /var/www/krt/.env with your configuration!"
fi

# Run Django management commands
echo "Running Django management commands..."
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Clean up
rm -f /tmp/krt_maker_deploy.tar.gz

echo "✓ Deployment completed successfully!"

ENDSSH

# Step 4: Update Nginx configuration (if needed)
print_status "Checking Nginx configuration..."
ssh $VPS_USER@$VPS_HOST << 'ENDSSH'
if [[ ! -f "/etc/nginx/sites-available/krt.xeradb.com" ]]; then
    echo "Creating Nginx configuration..."
    sudo tee /etc/nginx/sites-available/krt.xeradb.com > /dev/null << 'EOF'
server {
    listen 80;
    server_name krt.xeradb.com 91.99.161.136;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
    
    # File upload size
    client_max_body_size 50M;
    
    # Static files
    location /static/ {
        alias /var/www/krt/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Media files
    location /media/ {
        alias /var/www/krt/media/;
        expires 1y;
        add_header Cache-Control "public";
    }
    
    # Main application
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # Timeout settings for large file uploads
        proxy_connect_timeout       60s;
        proxy_send_timeout          60s;
        proxy_read_timeout          60s;
    }
}
EOF

    # Enable site
    sudo ln -sf /etc/nginx/sites-available/krt.xeradb.com /etc/nginx/sites-enabled/
    sudo nginx -t
    if [[ $? -eq 0 ]]; then
        sudo systemctl reload nginx
        echo "✓ Nginx configuration updated"
    else
        echo "✗ Nginx configuration test failed"
        exit 1
    fi
else
    echo "✓ Nginx configuration already exists"
fi
ENDSSH

# Step 5: Update Supervisor configuration
print_status "Checking Supervisor configuration..."
ssh $VPS_USER@$VPS_HOST << 'ENDSSH'
if [[ ! -f "/etc/supervisor/conf.d/krt_maker.conf" ]]; then
    echo "Creating Supervisor configuration..."
    sudo tee /etc/supervisor/conf.d/krt_maker.conf > /dev/null << 'EOF'
[program:krt_maker]
command=/var/www/krt/venv/bin/gunicorn krt_web.wsgi:application --bind 127.0.0.1:8000 --workers 3
directory=/var/www/krt
user=xeradb
group=www-data
autostart=true
autorestart=true
stdout_logfile=/var/log/supervisor/krt_maker.log
stderr_logfile=/var/log/supervisor/krt_maker_error.log
environment=PATH="/var/www/krt/venv/bin"
EOF

    sudo supervisorctl reread
    sudo supervisorctl update
    echo "✓ Supervisor configuration created"
else
    echo "✓ Supervisor configuration already exists"
fi

# Restart the application
echo "Restarting application..."
sudo supervisorctl restart krt_maker

# Check status
echo "Checking application status..."
sudo supervisorctl status krt_maker
ENDSSH

# Clean up local files
rm -f krt_maker_deploy.tar.gz

print_status "Deployment completed successfully!"
echo ""
echo "🎉 Your KRT Maker is now live!"
echo "🌐 URL: https://$DOMAIN"
echo ""
echo "📋 Next steps:"
echo "   1. Edit /var/www/krt/.env with your API keys"
echo "   2. Set up SSL certificate: sudo certbot --nginx -d $DOMAIN"
echo "   3. Test the application by uploading a sample XML file"
echo ""
echo "📊 Monitor logs:"
echo "   sudo tail -f /var/log/supervisor/krt_maker.log"
echo ""
echo "🔄 To redeploy, just run this script again!"