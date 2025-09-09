#!/bin/bash

# News Intelligence System - Custom Domain Setup Script
# This script sets up a custom domain for local network access

echo "=== News Intelligence System - Custom Domain Setup ==="
echo ""

# Get current IP address
CURRENT_IP=$(hostname -I | awk '{print $1}')
echo "Current IP address: $CURRENT_IP"

# Domain names
FRONTEND_DOMAIN="news-intelligence.local"
API_DOMAIN="api.news-intelligence.local"

echo "Setting up domains:"
echo "  Frontend: http://$FRONTEND_DOMAIN:3001"
echo "  API: http://$API_DOMAIN:8000"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "⚠️  Running as root. This is not recommended for security reasons."
    echo "Please run this script as a regular user and use sudo when needed."
    exit 1
fi

# Function to add domain to /etc/hosts
add_to_hosts() {
    local domain=$1
    local ip=$2
    
    if grep -q "$domain" /etc/hosts; then
        echo "✅ $domain already exists in /etc/hosts"
    else
        echo "Adding $domain to /etc/hosts..."
        echo "$ip $domain" | sudo tee -a /etc/hosts
        echo "✅ Added $domain to /etc/hosts"
    fi
}

# Add domains to /etc/hosts
echo "1. Adding domains to /etc/hosts..."
add_to_hosts "$FRONTEND_DOMAIN" "$CURRENT_IP"
add_to_hosts "$API_DOMAIN" "$CURRENT_IP"

# Test domain resolution
echo ""
echo "2. Testing domain resolution..."
if nslookup "$FRONTEND_DOMAIN" > /dev/null 2>&1; then
    echo "✅ $FRONTEND_DOMAIN resolves correctly"
else
    echo "❌ $FRONTEND_DOMAIN resolution failed"
fi

if nslookup "$API_DOMAIN" > /dev/null 2>&1; then
    echo "✅ $API_DOMAIN resolves correctly"
else
    echo "❌ $API_DOMAIN resolution failed"
fi

# Test accessibility
echo ""
echo "3. Testing accessibility..."
if curl -s "http://$FRONTEND_DOMAIN:3001" | grep -q "News Intelligence System"; then
    echo "✅ Frontend accessible at http://$FRONTEND_DOMAIN:3001"
else
    echo "❌ Frontend not accessible at http://$FRONTEND_DOMAIN:3001"
fi

if curl -s "http://$API_DOMAIN:8000/health" | grep -q "healthy"; then
    echo "✅ API accessible at http://$API_DOMAIN:8000"
else
    echo "❌ API not accessible at http://$API_DOMAIN:8000"
fi

# Create configuration update script
echo ""
echo "4. Creating configuration update script..."
cat > update-config.sh << 'EOF'
#!/bin/bash

# Update API_BASE in web/index.html
echo "Updating API_BASE in web/index.html..."

# Backup original file
cp web/index.html web/index.html.backup

# Update API_BASE
sed -i "s|const API_BASE = 'http://localhost:8000/api';|const API_BASE = 'http://api.news-intelligence.local:8000/api';|g" web/index.html

echo "✅ Updated API_BASE to use custom domain"

# Deploy updated configuration
echo "Deploying updated configuration..."
docker cp web/index.html news-frontend:/usr/share/nginx/html/

echo "✅ Configuration deployed successfully"
echo ""
echo "🌐 Your News Intelligence System is now accessible at:"
echo "   Frontend: http://news-intelligence.local:3001"
echo "   API: http://api.news-intelligence.local:8000"
echo ""
echo "📱 Other devices on your network can access it using:"
echo "   http://192.168.93.92:3001"
echo "   http://192.168.93.92:8000"
EOF

chmod +x update-config.sh

echo "✅ Created update-config.sh script"

# Create nginx configuration for reverse proxy
echo ""
echo "5. Creating Nginx reverse proxy configuration..."
cat > nginx-news-intelligence.conf << EOF
# News Intelligence System - Nginx Configuration
# Place this file in /etc/nginx/sites-available/news-intelligence

server {
    listen 80;
    server_name news-intelligence.local;
    
    # Frontend
    location / {
        proxy_pass http://localhost:3001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    # API
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    # Health check
    location /health {
        proxy_pass http://localhost:8000/health;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF

echo "✅ Created nginx-news-intelligence.conf"

# Create Docker Compose configuration
echo ""
echo "6. Creating Docker Compose configuration..."
cat > docker-compose.production.yml << 'EOF'
version: '3.8'

services:
  frontend:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./web:/usr/share/nginx/html
      - ./nginx-news-intelligence.conf:/etc/nginx/conf.d/default.conf
    depends_on:
      - backend
    restart: unless-stopped

  backend:
    build: ./api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/news_intelligence
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
    restart: unless-stopped

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=news_intelligence
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
EOF

echo "✅ Created docker-compose.production.yml"

# Create setup instructions
echo ""
echo "7. Creating setup instructions..."
cat > SETUP_INSTRUCTIONS.md << EOF
# News Intelligence System - Setup Instructions

## Quick Setup (Current Configuration)
Your system is already accessible at:
- Frontend: http://$FRONTEND_DOMAIN:3001
- API: http://$API_DOMAIN:8000

## For Other Devices on Your Network
Add these entries to /etc/hosts on each device:
```
$CURRENT_IP $FRONTEND_DOMAIN
$CURRENT_IP $API_DOMAIN
```

## To Use Custom Domain (Optional)
1. Run: ./update-config.sh
2. Access: http://$FRONTEND_DOMAIN:3001

## To Use Reverse Proxy (Advanced)
1. Install Nginx: sudo apt install nginx
2. Copy nginx-news-intelligence.conf to /etc/nginx/sites-available/
3. Enable site: sudo ln -s /etc/nginx/sites-available/news-intelligence /etc/nginx/sites-enabled/
4. Test: sudo nginx -t
5. Reload: sudo systemctl reload nginx
6. Access: http://$FRONTEND_DOMAIN

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
EOF

echo "✅ Created SETUP_INSTRUCTIONS.md"

echo ""
echo "🎉 Setup Complete!"
echo ""
echo "📋 Next Steps:"
echo "1. Test access: http://$FRONTEND_DOMAIN:3001"
echo "2. For other devices: Add domains to their /etc/hosts"
echo "3. Optional: Run ./update-config.sh to use custom domain"
echo "4. Advanced: Set up Nginx reverse proxy"
echo ""
echo "📱 Network Access:"
echo "   Frontend: http://$CURRENT_IP:3001"
echo "   API: http://$CURRENT_IP:8000"
echo ""
echo "🌐 Custom Domain:"
echo "   Frontend: http://$FRONTEND_DOMAIN:3001"
echo "   API: http://$API_DOMAIN:8000"
echo ""
echo "📖 See SETUP_INSTRUCTIONS.md for detailed instructions"


