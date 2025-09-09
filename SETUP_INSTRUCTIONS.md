# News Intelligence System - Setup Instructions

## Quick Setup (Current Configuration)
Your system is already accessible at:
- Frontend: http://news-intelligence.local:3001
- API: http://api.news-intelligence.local:8000

## For Other Devices on Your Network
Add these entries to /etc/hosts on each device:


## To Use Custom Domain (Optional)
1. Run: ./update-config.sh
2. Access: http://news-intelligence.local:3001

## To Use Reverse Proxy (Advanced)
1. Install Nginx: sudo apt install nginx
2. Copy nginx-news-intelligence.conf to /etc/nginx/sites-available/
3. Enable site: sudo ln -s /etc/nginx/sites-available/news-intelligence /etc/nginx/sites-enabled/
4. Test: sudo nginx -t
5. Reload: sudo systemctl reload nginx
6. Access: http://news-intelligence.local

## For Production Deployment
1. Use docker-compose.production.yml
2. Set up SSL certificates
3. Configure firewall rules
4. Set up monitoring and backups

## Current Status
✅ Domains added to /etc/hosts
✅ System accessible from local network
✅ Configuration files created
✅ Ready for production deployment
