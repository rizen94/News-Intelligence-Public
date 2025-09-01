# News Intelligence System v3.0 - Project Overview

## System Architecture
- **Backend**: Flask API with Python 3.11
- **Frontend**: React web application
- **Database**: PostgreSQL 15 with pgvector extension
- **Containerization**: Docker & Docker Compose
- **Monitoring**: Prometheus, Grafana, custom metrics
- **Storage**: TerraMaster NAS integration

## Key Features
- Automated RSS feed collection and processing
- AI/ML-powered content analysis and summarization
- Advanced deduplication and content management
- Real-time monitoring and resource tracking
- NAS-based persistent storage

## Directory Structure
```
news-intelligence-system/
├── api/                    # Backend Flask application
├── web/                    # Frontend React application
├── docker/                 # Docker configuration files
├── docs/                   # Project documentation
├── scripts/                # Deployment and utility scripts
│   ├── deployment/         # Deployment scripts
│   ├── monitoring/         # Monitoring scripts
│   └── docker/            # Docker-related scripts
├── config/                 # Configuration files
├── backups/                # Database and system backups
├── logs/                   # Application logs
├── temp/                   # Temporary files
├── docker-compose.yml      # Local deployment
├── docker-compose.nas.yml  # NAS deployment
└── README.md               # Main project README
```

## Deployment Options
1. **Local Storage**: Use `docker-compose.yml`
2. **NAS Storage**: Use `docker-compose.nas.yml` with `.env.nas`

## Quick Start
1. Install Docker and Docker Compose
2. Configure environment variables
3. Run `./scripts/deployment/deploy_nas.sh` for NAS deployment
4. Access web interface at http://localhost:8000

## Monitoring
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001 (admin/admin123)
- System metrics: http://localhost:8000/metrics
