# VPS Deployment Guide for KRT Maker

This guide covers deploying the KRT Maker application to a VPS with professional styling and terminal-based database management.

## 🚀 Quick Setup

### 1. Initial Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3 python3-pip python3-venv nginx git postgresql postgresql-contrib

# Create application user
sudo adduser krtmaker
sudo usermod -aG sudo krtmaker
```

### 2. Application Deployment

```bash
# Switch to application user
sudo su - krtmaker

# Clone repository
git clone https://github.com/your-username/KRTMaker.git
cd KRTMaker

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cat > .env << EOF
DEBUG=False
SECRET_KEY=your-super-secret-key-here
DATABASE_URL=postgresql://krtmaker:password@localhost/krtmaker_db
ALLOWED_HOSTS=your-vps-ip,your-domain.com
STATIC_ROOT=/home/krtmaker/KRTMaker/staticfiles/
MEDIA_ROOT=/home/krtmaker/KRTMaker/mediafiles/
XML_STORAGE_DIR=/home/krtmaker/KRTMaker/xml_files/
EOF
```

### 3. Database Setup

```bash
# Create PostgreSQL database and user
sudo -u postgres psql << EOF
CREATE DATABASE krtmaker_db;
CREATE USER krtmaker WITH PASSWORD 'your-strong-password';
GRANT ALL PRIVILEGES ON DATABASE krtmaker_db TO krtmaker;
ALTER USER krtmaker CREATEDB;
\q
EOF

# Run Django migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput
```

## 📊 Database Management (Terminal Commands)

### XML Files Database Population

```bash
# Download all bioRxiv XML files (2020-2025)
# This will take several hours and requires significant storage
python manage.py download_xml_files --start-year 2020 --end-year 2025

# Update with new papers (run daily/weekly)
python manage.py update_xml_files

# Check database status
python manage.py shell -c "
from web.models import XMLFile
print(f'Total XML files: {XMLFile.objects.count()}')
print(f'Available files: {XMLFile.objects.filter(is_available=True).count()}')
"
```

### Article Database Population

```bash
# Populate article metadata from existing XML files
python manage.py populate_articles

# Check article database
python manage.py shell -c "
from web.models import Article
print(f'Total articles: {Article.objects.count()}')
"
```

### Admin KRT Generation

```bash
# Generate KRTs using specific LLM for top papers
python manage.py generate_admin_krts \
    --provider gemini \
    --model gemini-1.5-flash \
    --limit 50 \
    --dry-run

# Generate KRTs for specific DOIs
python manage.py generate_admin_krts \
    --provider anthropic \
    --model claude-3-haiku-20240307 \
    --dois "10.1101/2025.01.01.123456,10.1101/2025.01.02.234567"

# Check generation status
python manage.py shell -c "
from web.models import AdminKRT
stats = AdminKRT.get_statistics()
print(f'Total: {stats[\"total\"]}, Completed: {stats[\"completed\"]}, Approved: {stats[\"approved\"]}')
"
```

### Maintenance Commands

```bash
# Clean up old sessions (run weekly)
python manage.py shell -c "
from web.models import KRTSession
from django.utils import timezone
from datetime import timedelta
cutoff = timezone.now() - timedelta(days=30)
old_sessions = KRTSession.objects.filter(created_at__lt=cutoff)
print(f'Deleting {old_sessions.count()} old sessions')
old_sessions.delete()
"

# Check disk usage
du -sh xml_files/
du -sh mediafiles/
du -sh staticfiles/

# Backup database
pg_dump krtmaker_db > backup_$(date +%Y%m%d).sql
```

## 🔧 Nginx Configuration

```bash
# Create Nginx config
sudo tee /etc/nginx/sites-available/krtmaker << EOF
server {
    listen 80;
    server_name your-domain.com your-vps-ip;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        root /home/krtmaker/KRTMaker;
    }
    
    location /media/ {
        root /home/krtmaker/KRTMaker;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/home/krtmaker/KRTMaker/krtmaker.sock;
    }
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/krtmaker /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

## 🏃‍♂️ Gunicorn Setup

```bash
# Create Gunicorn socket file
sudo tee /etc/systemd/system/krtmaker.socket << EOF
[Unit]
Description=gunicorn socket

[Socket]
ListenStream=/home/krtmaker/KRTMaker/krtmaker.sock

[Install]
WantedBy=sockets.target
EOF

# Create Gunicorn service file
sudo tee /etc/systemd/system/krtmaker.service << EOF
[Unit]
Description=gunicorn daemon
Requires=krtmaker.socket
After=network.target

[Service]
User=krtmaker
Group=www-data
WorkingDirectory=/home/krtmaker/KRTMaker
Environment="PATH=/home/krtmaker/KRTMaker/venv/bin"
ExecStart=/home/krtmaker/KRTMaker/venv/bin/gunicorn \
          --access-logfile - \
          --workers 3 \
          --bind unix:/home/krtmaker/KRTMaker/krtmaker.sock \
          krt_web.wsgi:application

[Install]
WantedBy=multi-user.target
EOF

# Start services
sudo systemctl start krtmaker.socket
sudo systemctl enable krtmaker.socket
sudo systemctl start krtmaker.service
sudo systemctl enable krtmaker.service
```

## 📈 Monitoring & Maintenance

### Service Status Checks

```bash
# Check service status
sudo systemctl status krtmaker.service
sudo systemctl status nginx
sudo systemctl status postgresql

# View logs
sudo journalctl -u krtmaker.service -f
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Automated Updates

```bash
# Create update script
cat > /home/krtmaker/update_xml.sh << EOF
#!/bin/bash
cd /home/krtmaker/KRTMaker
source venv/bin/activate
python manage.py update_xml_files
EOF

chmod +x /home/krtmaker/update_xml.sh

# Add to crontab (run daily at 2 AM)
crontab -e
# Add: 0 2 * * * /home/krtmaker/update_xml.sh >> /home/krtmaker/update.log 2>&1
```

## 🎨 Professional UI Features

- **Minimalistic Design**: Clean, professional color scheme
- **No Database UI**: All database management via terminal commands
- **Performance Optimized**: Streamlined for VPS deployment
- **Responsive**: Works on all screen sizes

## 🛡️ Security

```bash
# Set up firewall
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw enable

# Secure PostgreSQL
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'new-strong-password';"

# Set proper file permissions
sudo chown -R krtmaker:www-data /home/krtmaker/KRTMaker/
sudo chmod -R 755 /home/krtmaker/KRTMaker/
```

## 📱 Usage

1. **Access**: Visit `http://your-vps-ip:8014` or your domain
2. **Create KRT**: Upload PDF/XML or enter bioRxiv DOI
3. **View Results**: Professional, clean interface
4. **Export**: Download as CSV, JSON, or Excel
5. **Articles**: Browse processed papers

## 🔍 Troubleshooting

```bash
# Check if services are running
curl -I http://localhost

# Test database connection
python manage.py dbshell

# Check XML file availability
python manage.py shell -c "
from web.models import XMLFile
recent = XMLFile.objects.filter(is_available=True).order_by('-downloaded_at')[:5]
for xml in recent: print(f'{xml.doi}: {xml.file_size} bytes')
"

# Restart services
sudo systemctl restart krtmaker.service
sudo systemctl restart nginx
```

## 📞 Support

For issues:
1. Check service logs: `sudo journalctl -u krtmaker.service -f`
2. Verify XML database: `python manage.py shell`
3. Test individual components
4. Monitor disk space and memory usage

---

**Note**: All database management is done via Django management commands. The web interface focuses purely on KRT generation and viewing results.