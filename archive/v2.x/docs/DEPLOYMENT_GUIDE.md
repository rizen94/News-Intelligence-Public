# Deployment Guide

## Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+
- 64GB+ RAM (for ML workloads)
- NVIDIA GPU with 32GB+ VRAM (optional)

## Local Deployment
```bash
# Clone repository
git clone <repository-url>
cd news-intelligence-system

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Deploy
docker-compose up -d
```

## NAS Deployment
```bash
# Setup NAS storage
./scripts/deployment/setup_nas_admin.sh

# Deploy with NAS storage
./scripts/deployment/deploy_nas.sh
```

## Environment Variables
- `DB_PASSWORD`: PostgreSQL password
- `GRAFANA_PASSWORD`: Grafana admin password
- `RSS_INTERVAL_MINUTES`: RSS collection interval
- `PRUNING_INTERVAL_HOURS`: Data cleanup interval

## Health Checks
- Application: http://localhost:8000/health
- Database: http://localhost:5432
- Monitoring: http://localhost:9090/metrics
