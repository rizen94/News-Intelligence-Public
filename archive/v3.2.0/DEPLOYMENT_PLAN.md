# News Intelligence System - Deployment Plan

## Current Status
- **Frontend**: http://192.168.93.92:3001 (accessible from local network)
- **Backend API**: http://192.168.93.92:8000 (accessible from local network)
- **Database**: PostgreSQL on port 5432
- **Redis**: Cache on port 6379

## Page Structure Analysis

### Main Pages
1. **Dashboard** - Main overview with stats and recent articles
2. **Articles** - Article management with pagination, search, filtering
3. **Storylines** - Storyline tracking and management
4. **Topic Clusters** - Word cloud and topic analysis
5. **Analytics** - Data visualization and trends
6. **Sources** - RSS feeds management

### Navigation Elements
- Top navigation bar with 6 main pages
- Breadcrumb navigation for deep linking
- Modal dialogs for detailed views
- Responsive design for mobile/desktop

## Deployment Options

### Option 1: Local Network with Custom Domain
**Best for**: Internal team use, development, testing

#### Setup Steps:
1. **Configure DNS Server** (Router or Pi-hole)
   ```
   # Add to /etc/hosts or router DNS
   192.168.93.92 news-intelligence.local
   192.168.93.92 api.news-intelligence.local
   ```

2. **Update API Configuration**
   ```javascript
   // In web/index.html
   const API_BASE = 'http://api.news-intelligence.local:8000/api';
   ```

3. **Access URLs**
   - Frontend: http://news-intelligence.local:3001
   - API: http://api.news-intelligence.local:8000

### Option 2: Reverse Proxy with Nginx
**Best for**: Production-like setup, better performance

#### Setup Steps:
1. **Install Nginx**
   ```bash
   sudo apt update
   sudo apt install nginx
   ```

2. **Create Nginx Configuration**
   ```nginx
   # /etc/nginx/sites-available/news-intelligence
   server {
       listen 80;
       server_name news-intelligence.local;
       
       # Frontend
       location / {
           proxy_pass http://localhost:3001;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
       
       # API
       location /api/ {
           proxy_pass http://localhost:8000/api/;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

3. **Enable Site**
   ```bash
   sudo ln -s /etc/nginx/sites-available/news-intelligence /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

### Option 3: Docker Compose with Custom Domain
**Best for**: Containerized deployment, easy management

#### Setup Steps:
1. **Create docker-compose.yml**
   ```yaml
   version: '3.8'
   services:
     frontend:
       image: nginx:alpine
       ports:
         - "80:80"
       volumes:
         - ./web:/usr/share/nginx/html
         - ./nginx.conf:/etc/nginx/nginx.conf
       depends_on:
         - backend
     
     backend:
       build: ./api
       ports:
         - "8000:8000"
       environment:
         - DATABASE_URL=postgresql://postgres:password@db:5432/news_intelligence
       depends_on:
         - db
         - redis
     
     db:
       image: postgres:15
       environment:
         - POSTGRES_DB=news_intelligence
         - POSTGRES_USER=postgres
         - POSTGRES_PASSWORD=password
       volumes:
         - postgres_data:/var/lib/postgresql/data
     
     redis:
       image: redis:alpine
       volumes:
         - redis_data:/data
   
   volumes:
     postgres_data:
     redis_data:
   ```

2. **Create nginx.conf**
   ```nginx
   events {
       worker_connections 1024;
   }
   
   http {
       upstream backend {
           server backend:8000;
       }
       
       server {
           listen 80;
           server_name news-intelligence.local;
           
           location / {
               root /usr/share/nginx/html;
               index index.html;
           }
           
           location /api/ {
               proxy_pass http://backend/api/;
               proxy_set_header Host $host;
               proxy_set_header X-Real-IP $remote_addr;
           }
       }
   }
   ```

## Configuration Updates Needed

### 1. Update API Base URL
```javascript
// In web/index.html, change:
const API_BASE = 'http://localhost:8000/api';

// To:
const API_BASE = 'http://api.news-intelligence.local:8000/api';
// Or for reverse proxy:
const API_BASE = '/api';
```

### 2. Update CORS Settings
```python
# In api/main.py, update CORS:
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://news-intelligence.local:3001",
        "http://news-intelligence.local",
        "http://192.168.93.92:3001",
        "http://192.168.93.92"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 3. Environment Variables
```bash
# Create .env file
FRONTEND_URL=http://news-intelligence.local:3001
API_URL=http://api.news-intelligence.local:8000
DATABASE_URL=postgresql://postgres:password@localhost:5432/news_intelligence
REDIS_URL=redis://localhost:6379
```

## DNS Configuration

### Router DNS (Recommended)
1. Access router admin panel (usually 192.168.1.1 or 192.168.0.1)
2. Go to DNS settings
3. Add custom DNS entries:
   - `news-intelligence.local` → `192.168.93.92`
   - `api.news-intelligence.local` → `192.168.93.92`

### Pi-hole DNS (Advanced)
1. Install Pi-hole on Raspberry Pi
2. Add custom DNS entries in Pi-hole admin
3. Configure router to use Pi-hole as DNS server

### Local /etc/hosts (Quick Test)
```bash
# Add to /etc/hosts on each client machine
192.168.93.92 news-intelligence.local
192.168.93.92 api.news-intelligence.local
```

## Security Considerations

### 1. Firewall Rules
```bash
# Allow only local network access
sudo ufw allow from 192.168.93.0/24 to any port 3001
sudo ufw allow from 192.168.93.0/24 to any port 8000
sudo ufw deny 3001
sudo ufw deny 8000
```

### 2. SSL/TLS (Optional)
```bash
# Install certbot for Let's Encrypt
sudo apt install certbot python3-certbot-nginx

# Generate certificate
sudo certbot --nginx -d news-intelligence.local
```

### 3. Authentication (Future)
- Add user authentication
- Implement role-based access control
- Add API key authentication

## Monitoring and Maintenance

### 1. Health Checks
```bash
# Create health check script
#!/bin/bash
curl -f http://news-intelligence.local:3001 || echo "Frontend down"
curl -f http://api.news-intelligence.local:8000/health || echo "API down"
```

### 2. Log Monitoring
```bash
# Monitor Docker logs
docker logs news-system-app -f
docker logs news-frontend -f
```

### 3. Backup Strategy
```bash
# Database backup
docker exec news-system-postgres pg_dump -U postgres news_intelligence > backup.sql

# Configuration backup
tar -czf config-backup.tar.gz web/ api/ docker-compose.yml
```

## Recommended Next Steps

1. **Immediate**: Set up custom domain with router DNS
2. **Short-term**: Implement reverse proxy with Nginx
3. **Medium-term**: Add SSL/TLS certificates
4. **Long-term**: Implement authentication and monitoring

## Testing Checklist

- [ ] Custom domain resolves correctly
- [ ] Frontend loads from custom domain
- [ ] API calls work from custom domain
- [ ] All pages navigate correctly
- [ ] Mobile responsiveness works
- [ ] Cross-browser compatibility
- [ ] Performance is acceptable
- [ ] Security headers are in place


