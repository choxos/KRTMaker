# KRT Maker - VPS Deployment Guide

Complete guide for deploying the standalone KRT Maker Django application to your VPS at `krt.xeradb.com`.

## 🚀 Quick Overview

This guide will help you deploy the KRT Maker Django app to your VPS with:
- **Domain**: krt.xeradb.com  
- **Server**: 91.99.161.136 (user: xeradb)
- **Database**: PostgreSQL (krt_production)
- **Location**: /var/www/krt

## 📋 Prerequisites

- VPS access with sudo privileges
- Domain pointing to your VPS IP
- PostgreSQL database already set up

## 🔧 Step 1: Server Setup

### 1.1 Connect to your VPS
```bash
ssh xeradb@91.99.161.136
```

### 1.2 Update system packages
```bash
sudo apt update && sudo apt upgrade -y
```

### 1.3 Install required packages
```bash
sudo apt install -y python3 python3-pip python3-venv nginx postgresql-client git curl
```

### 1.4 Install Node.js (for static file processing)
```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

## 📁 Step 2: Deploy Application Code

### 2.1 Create application directory
```bash
sudo mkdir -p /var/www/krt
sudo chown xeradb:xeradb /var/www/krt
cd /var/www/krt
```

### 2.2 Clone/Upload your code
You have two options:

**Option A: Git Clone (if you have a repo)**
```bash
git clone https://github.com/yourusername/KRTManager.git .
cd krt_maker
```

**Option B: Direct Upload (what we'll use)**
```bash
# From your local machine, upload the krt_maker folder
scp -r /Users/choxos/Documents/GitHub/KRTManager/krt_maker/* xeradb@91.99.161.136:/var/www/krt/
```

### 2.3 Set proper permissions
```bash
sudo chown -R xeradb:www-data /var/www/krt
sudo chmod -R 755 /var/www/krt
```

## 🐍 Step 3: Python Environment Setup

### 3.1 Create virtual environment
```bash
cd /var/www/krt
python3 -m venv venv
source venv/bin/activate
```

### 3.2 Install dependencies
```bash
pip install --upgrade pip
pip install -r web_requirements.txt
```

### 3.3 Install additional production packages
```bash
pip install gunicorn supervisor
```

## 🗄️ Step 4: Database Configuration

### 4.1 Test database connection
```bash
psql -h localhost -U krt_user -d krt_production
# Enter password: Choxos10203040
# Test connection, then \q to exit
```

### 4.2 Create environment configuration
```bash
nano /var/www/krt/.env
```

Add the following content:
```env
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
```

### 4.3 Run database migrations
```bash
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
```

### 4.4 Create superuser (optional)
```bash
python manage.py createsuperuser
```

## 🌐 Step 5: Nginx Configuration

### 5.1 Create Nginx configuration
```bash
sudo nano /etc/nginx/sites-available/krt.xeradb.com
```

Add this configuration:
```nginx
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
```

### 5.2 Enable the site
```bash
sudo ln -s /etc/nginx/sites-available/krt.xeradb.com /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 🔄 Step 6: Process Management with Supervisor

### 6.1 Create Gunicorn configuration
```bash
sudo nano /etc/supervisor/conf.d/krt_maker.conf
```

Add this configuration:
```ini
[program:krt_maker]
command=/var/www/krt/venv/bin/gunicorn krt_web.wsgi:application
directory=/var/www/krt
user=xeradb
group=www-data
bind=127.0.0.1:8000
workers=3
worker_class=sync
worker_connections=1000
max_requests=1000
max_requests_jitter=50
timeout=60
keepalive=2
preload_app=true
reload=false
autostart=true
autorestart=true
stdout_logfile=/var/log/supervisor/krt_maker.log
stderr_logfile=/var/log/supervisor/krt_maker_error.log
environment=PATH="/var/www/krt/venv/bin"
```

### 6.2 Create Gunicorn startup script
```bash
nano /var/www/krt/start_gunicorn.sh
```

Add this content:
```bash
#!/bin/bash
cd /var/www/krt
source venv/bin/activate
exec gunicorn krt_web.wsgi:application \
    --bind 127.0.0.1:8000 \
    --workers 3 \
    --worker-class sync \
    --worker-connections 1000 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --timeout 60 \
    --keepalive 2 \
    --preload \
    --access-logfile /var/log/gunicorn/access.log \
    --error-logfile /var/log/gunicorn/error.log \
    --log-level info
```

Make it executable:
```bash
chmod +x /var/www/krt/start_gunicorn.sh
sudo mkdir -p /var/log/gunicorn
sudo chown xeradb:xeradb /var/log/gunicorn
```

### 6.3 Start services
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start krt_maker
sudo supervisorctl status
```

## 🔒 Step 7: SSL Certificate (Optional but Recommended)

### 7.1 Install Certbot
```bash
sudo apt install certbot python3-certbot-nginx -y
```

### 7.2 Obtain SSL certificate
```bash
sudo certbot --nginx -d krt.xeradb.com
```

Follow the prompts to configure HTTPS.

## 📊 Step 8: Monitoring and Logs

### 8.1 Create log directories
```bash
sudo mkdir -p /var/log/krt_maker
sudo chown xeradb:xeradb /var/log/krt_maker
```

### 8.2 View logs
```bash
# Application logs
sudo tail -f /var/log/supervisor/krt_maker.log

# Error logs
sudo tail -f /var/log/supervisor/krt_maker_error.log

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Gunicorn logs
tail -f /var/log/gunicorn/access.log
tail -f /var/log/gunicorn/error.log
```

## 🔄 Step 9: File Transfer Setup

### 9.1 Create upload script for transferring KRT JSONs
```bash
nano /var/www/krt/transfer_to_main_site.py
```

Add this script:
```python
#!/usr/bin/env python3
"""
Script to transfer processed KRT JSONs to the main KRT Manager website
"""
import os
import json
import requests
from datetime import datetime

def transfer_krt_to_main_site(session_id, krt_data):
    """Transfer KRT data to main site via API"""
    
    # Main site API endpoint
    main_site_url = "http://your-main-site.com/api/import-krt/"
    
    payload = {
        'source': 'krt_maker',
        'session_id': session_id,
        'timestamp': datetime.now().isoformat(),
        'krt_data': krt_data
    }
    
    try:
        response = requests.post(main_site_url, json=payload, timeout=30)
        response.raise_for_status()
        return True, "Successfully transferred to main site"
    except requests.exceptions.RequestException as e:
        return False, f"Transfer failed: {str(e)}"

if __name__ == "__main__":
    # Example usage
    print("KRT Transfer script ready")
```

### 9.2 Set up automatic backups
```bash
nano /var/www/krt/backup_krts.sh
```

Add this backup script:
```bash
#!/bin/bash
# Daily backup of KRT database
BACKUP_DIR="/var/backups/krt_maker"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
pg_dump -h localhost -U krt_user -d krt_production > $BACKUP_DIR/krt_backup_$DATE.sql

# Keep only last 7 days of backups
find $BACKUP_DIR -name "krt_backup_*.sql" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR/krt_backup_$DATE.sql"
```

Make executable and add to crontab:
```bash
chmod +x /var/www/krt/backup_krts.sh
crontab -e
# Add this line for daily backup at 2 AM:
# 0 2 * * * /var/www/krt/backup_krts.sh
```

## ✅ Step 10: Final Testing

### 10.1 Test the application
```bash
curl -I http://krt.xeradb.com
```

### 10.2 Test file upload
Visit `http://krt.xeradb.com` and try uploading a test XML file.

### 10.3 Check all services
```bash
sudo systemctl status nginx
sudo supervisorctl status
```

## 🚀 Step 11: Going Live

### 11.1 Restart all services
```bash
sudo supervisorctl restart krt_maker
sudo systemctl restart nginx
```

### 11.2 Final verification
- ✅ Visit https://krt.xeradb.com
- ✅ Test file upload functionality
- ✅ Test KRT generation (both regex and LLM modes)
- ✅ Test export functionality (JSON, CSV, Excel)
- ✅ Check analytics dashboard

## 🔧 Maintenance Commands

### Update application code:
```bash
cd /var/www/krt
git pull  # if using git
source venv/bin/activate
pip install -r web_requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo supervisorctl restart krt_maker
```

### View live logs:
```bash
sudo tail -f /var/log/supervisor/krt_maker.log
```

### Restart services:
```bash
sudo supervisorctl restart krt_maker
sudo systemctl restart nginx
```

## 🆘 Troubleshooting

### Common Issues:

1. **502 Bad Gateway**
   ```bash
   sudo supervisorctl status krt_maker
   sudo supervisorctl restart krt_maker
   ```

2. **Permission Denied**
   ```bash
   sudo chown -R xeradb:www-data /var/www/krt
   sudo chmod -R 755 /var/www/krt
   ```

3. **Database Connection Issues**
   ```bash
   # Test connection
   psql -h localhost -U krt_user -d krt_production
   ```

4. **Static Files Not Loading**
   ```bash
   python manage.py collectstatic --noinput
   sudo systemctl restart nginx
   ```

## 📈 Performance Optimization

### For high traffic:
1. Increase Gunicorn workers: `workers=5`
2. Use Redis for caching (optional)
3. Set up Nginx caching for static files
4. Monitor with tools like `htop` and `iotop`

---

**🎉 Congratulations!** Your KRT Maker is now live at https://krt.xeradb.com

For support or updates, check the logs and ensure all services are running properly.