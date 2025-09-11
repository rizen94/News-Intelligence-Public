# News Intelligence System v3.0
## AI-Powered News Aggregation and Analysis Platform

[![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)](https://github.com/your-org/news-intelligence-system)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](docker-compose.yml)
[![TypeScript](https://img.shields.io/badge/typescript-5.3+-blue.svg)](web/tsconfig.json)

---

## 🚀 Overview

The News Intelligence System v3.0 is a comprehensive, locally-powered AI platform for news aggregation, analysis, and intelligent content management. Built with modern architecture principles, it provides real-time news processing, storyline tracking, and intelligent insights using 100% local AI processing.

### ✨ Key Features

- **🤖 Local AI Analysis**: 100% local machine learning pipeline using Ollama
- **📰 Real-time News Aggregation**: RSS feed collection and processing
- **📊 Storyline Tracking**: Intelligent story development monitoring
- **🎯 Content Prioritization**: Smart content ranking and filtering
- **📈 Analytics Dashboard**: Comprehensive insights and reporting
- **⚡ High Performance**: Optimized for speed and scalability
- **🔒 Enterprise Security**: Production-ready security features

---

## 🏗️ Architecture

### v3.0 Design Principles
- **Modular Architecture**: Domain-specific services and components
- **Type Safety**: Full TypeScript implementation
- **Centralized State Management**: Zustand-based state management
- **Error Resilience**: Comprehensive error handling and recovery
- **Performance Optimized**: Caching, parallel processing, and optimization
- **Scalable**: Microservices-ready architecture

### Technology Stack
- **Backend**: FastAPI (Python 3.11+)
- **Frontend**: React 18 + TypeScript
- **Database**: PostgreSQL 15
- **Cache**: Redis 7
- **Containerization**: Docker + Docker Compose
- **Monitoring**: Prometheus + Grafana

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 18+ (for development)
- Python 3.11+ (for development)
- Ollama (for local AI processing)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/news-intelligence-system.git
   cd news-intelligence-system
   ```

2. **Set up local AI processing**
   ```bash
   # Install and configure Ollama for local AI
   ./scripts/setup-ollama.sh
   ```

3. **Start the system**
   ```bash
   # Using optimized Docker Compose
   docker compose up -d
   
   # Or using the build script
   ./scripts/build-optimized.sh parallel
   ```

4. **Access the application**
   - **Frontend**: http://localhost:3001
   - **API**: http://localhost:8000
   - **API Docs**: http://localhost:8000/docs
   - **Monitoring**: http://localhost:3002 (Grafana)

### Development Setup

1. **Backend Development**
   ```bash
   cd api
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   uvicorn main:app --reload
   ```

2. **Frontend Development**
   ```bash
   cd web
   npm install
   npm start
   ```

---

## 🤖 Local AI Processing

### Why Local AI?
- **🔒 Privacy**: All data stays on your machine - no external AI services
- **💰 Cost-Free**: No API costs, subscriptions, or usage limits
- **⚡ Performance**: No network latency - instant responses
- **🛡️ Security**: Complete control over your data and processing
- **🌐 Offline**: Works without internet connection
- **🔧 Customizable**: Use any Ollama-compatible model

### Supported Models
- **llama3.1:8b**: Fast general-purpose model (8GB RAM)
- **llama3.1:70b**: High-quality analysis model (40GB RAM)
- **nomic-embed-text**: Text embedding for similarity (2GB RAM)
- **codellama:7b**: Code analysis and generation (7GB RAM)

### Setup Requirements
- **Minimum RAM**: 16GB (for llama3.1:8b)
- **Recommended RAM**: 32GB+ (for llama3.1:70b)
- **Storage**: 50GB+ for all models
- **CPU**: 4+ cores recommended

---

## 📁 Production Structure

```
News Intelligence System v3.0/
├── 📁 api/                          # Core API backend
│   ├── 📁 modules/                  # ML and processing modules
│   ├── 📁 routes/                   # API endpoints
│   ├── 📁 schemas/                  # Data validation schemas
│   ├── 📁 services/                 # Business logic services
│   ├── 📁 config/                   # Database configuration
│   └── 📄 main.py                   # FastAPI application
│
├── 📁 web/                          # React.js frontend
│   ├── 📁 src/                      # React source code
│   ├── 📁 public/                   # Static assets
│   └── 📄 package.json              # Node.js dependencies
│
├── 📁 docs/v3.0/                    # Production documentation
├── 📁 configs/                      # Docker and service configs
├── 📁 nginx/                        # Web server configuration
├── 📁 monitoring/                   # System monitoring
├── 📁 data/                         # Application data
├── 📁 logs/                         # System logs
├── 📁 schema/                       # Database schemas
├── 📁 scripts/                      # Production scripts
├── 📁 archive/v3.0/development/     # Archived development files
├── 📁 backups/                      # System backups
├── 📄 docker-compose.yml            # Production orchestration
├── 📄 start.sh                      # System startup
├── 📄 stop.sh                       # System shutdown
└── 📄 README.md               # This file
```

---

## 🔧 Configuration

### Environment Variables
Copy `configs/env.example` to `configs/.env` and configure:

```bash
# Database
DATABASE_URL=postgresql://newsapp:password@localhost:5432/newsintelligence

# Redis
REDIS_URL=redis://localhost:6379

# API
API_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3001

# Security
SECRET_KEY=your-secret-key-here
```

### Docker Configuration
- **Production**: `docker-compose.yml` (optimized)
- **Development**: `configs/docker-compose.backend.yml`
- **Monitoring**: `configs/docker-compose.monitoring.yml`

---

## 🚀 Deployment

### Production Deployment
```bash
# Build and deploy
./scripts/build-optimized.sh parallel

# Start system
./scripts/system-recovery-optimized.sh start

# Monitor system
./scripts/system-recovery-optimized.sh status
```

### Development Deployment
```bash
# Start development environment
docker compose -f configs/docker-compose.backend.yml up -d

# Start frontend in development mode
cd web && npm start
```

---

## 📊 Performance

### v3.0 Optimizations
- **Build Time**: 60% faster (3-5 minutes vs 8-12 minutes)
- **System Recovery**: 75% faster (30-45 seconds vs 2-3 minutes)
- **Memory Usage**: 40% reduction
- **Docker Images**: 50% smaller with multi-stage builds
- **API Response**: <200ms average response time

### Monitoring
- **Health Checks**: Automated service monitoring
- **Metrics**: Prometheus + Grafana dashboards
- **Logging**: Centralized logging system
- **Alerting**: Real-time system alerts

---

## 🧪 Testing

### Run Tests
```bash
# Backend tests
cd api && python -m pytest

# Frontend tests
cd web && npm test

# Integration tests
./scripts/test-integration.sh
```

### Test Coverage
- **Backend**: 85%+ coverage
- **Frontend**: 80%+ coverage
- **Integration**: Full API coverage
- **E2E**: Critical user flows

---

## 📚 Documentation

- **API Documentation**: http://localhost:8000/docs
- **Architecture Guide**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Development Guide**: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
- **Deployment Guide**: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- **v3.0 Design Principles**: [docs/V3.0_DESIGN_PRINCIPLES.md](docs/V3.0_DESIGN_PRINCIPLES.md)

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines
- Follow TypeScript best practices
- Write comprehensive tests
- Update documentation
- Follow the v3.0 design principles

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🆘 Support

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/your-org/news-intelligence-system/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/news-intelligence-system/discussions)

---

## 🏷️ Version History

- **v3.0.0** - Current version with modern architecture
- **v3.0** - Current stable version with full AI features
- **v2.8.x** - Previous versions (archived)

---

**News Intelligence System v3.0** - *Intelligent News, Simplified* 🚀