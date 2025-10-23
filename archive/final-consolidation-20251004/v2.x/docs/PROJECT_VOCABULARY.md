# 🎯 News Intelligence System v3.0 - Project Vocabulary

## 🏗️ **SYSTEM ARCHITECTURE OVERVIEW**

### **Core Components**
- **News Intelligence System** - The complete platform
- **Backend API** - Python FastAPI server (`/api/` directory)
- **Frontend Web App** - React.js application (`/web/` directory)
- **Database Layer** - PostgreSQL with Redis caching
- **AI/ML Engine** - Llama 3.1 70B and custom models
- **Infrastructure** - Docker containers with NAS storage

---

## 🐍 **BACKEND API COMPONENTS**

### **Main Application**
- **`api/app.py`** - FastAPI main application entry point
- **`api/main.py`** - Application runner and configuration
- **`api/requirements.txt`** - Python dependencies

### **API Route Modules** (`/api/routes/`)
- **`articles.py`** - Article management and analysis endpoints
- **`dashboard.py`** - Dashboard statistics and metrics
- **`intelligence.py`** - AI analysis and insights endpoints
- **`stories.py`** - Story tracking and evolution
- **`rss.py`** - RSS feed management and collection
- **`search.py`** - Search and discovery endpoints
- **`deduplication.py`** - Content deduplication logic
- **`entities.py`** - Entity extraction and management
- **`clusters.py`** - Content clustering and grouping
- **`automation.py`** - Automated processing workflows
- **`ml.py`** - Machine learning model endpoints
- **`ml_management.py`** - ML model management
- **`rag.py`** - RAG (Retrieval Augmented Generation) endpoints
- **`monitoring.py`** - System monitoring and health
- **`sources.py`** - News source management
- **`health.py`** - System health checks

### **Core Business Logic** (`/api/modules/`)
- **`data_collection/`** - RSS collection and ingestion
- **`intelligence/`** - AI analysis and processing
- **`deduplication/`** - Content similarity detection
- **`prioritization/`** - Content ranking and filtering
- **`automation/`** - Automated workflows
- **`ml/`** - Machine learning models and processing
- **`monitoring/`** - System monitoring utilities

### **Data Layer**
- **`config/database.py`** - Database connection and configuration
- **`database/migrations/`** - Database schema migrations
- **`collectors/`** - RSS feed collectors

---

## 🌐 **FRONTEND WEB APP COMPONENTS**

### **Main Application**
- **`web/src/App.js`** - React main application component
- **`web/src/index.js`** - Application entry point
- **`web/package.json`** - Node.js dependencies

### **Page Components** (`/web/src/pages/`)
- **`Dashboard/`** - Main dashboard and overview
  - `EnhancedDashboard.js` - Primary dashboard component
- **`Articles/`** - Article management and viewing
  - `EnhancedArticles.js` - Main articles page
  - `UnifiedArticlesAnalysis.js` - Article analysis tools
- **`Intelligence/`** - AI insights and analysis
  - `IntelligenceDashboard.js` - Intelligence overview
  - `IntelligenceInsights.js` - Detailed insights
- **`Stories/`** - Story tracking and management
- **`StoryDossiers/`** - Comprehensive story profiles
  - `UnifiedStoryDossiers.js` - Main story dossiers
- **`LivingStoryNarrator/`** - Dynamic story narration
  - `UnifiedLivingStoryNarrator.js` - Story narrator interface
- **`RSSManagement/`** - RSS feed management
- **`Deduplication/`** - Content deduplication tools
  - `DeduplicationManagement.js` - Deduplication interface
- **`Search/`** - Search and discovery
- **`Monitoring/`** - System monitoring dashboards
- **`MLProcessing/`** - Machine learning processing
- **`AutomationPipeline/`** - Automated workflows
- **`ContentPrioritization/`** - Content ranking tools
- **`DailyBriefings/`** - Automated digest generation
- **`AdvancedMonitoring/`** - Advanced system monitoring
- **`DataManagement/`** - Data management tools

### **Reusable Components** (`/web/src/components/`)
- **`Layout/`** - Main layout and navigation
- **`Notifications/`** - Notification system
  - `NotificationSystem.js` - Global notification provider
- **`ArticleViewer/`** - Article display components
- **`Breadcrumb/`** - Navigation breadcrumbs
- **`ContentPrioritization/`** - Content ranking components

### **Services and Contexts**
- **`services/newsSystemService.js`** - API service layer
- **`contexts/NewsSystemContext.js`** - React context for state management

---

## 🔧 **INFRASTRUCTURE COMPONENTS**

### **Docker Configuration**
- **`docker-compose.yml`** - Main Docker Compose configuration
- **`docker-compose.unified.yml`** - Unified deployment configuration
- **`Dockerfile`** - Backend container definition
- **`web/Dockerfile`** - Frontend container definition

### **Database**
- **PostgreSQL** - Primary database
- **Redis** - Caching layer
- **NAS Storage** - Persistent data storage

### **Monitoring Stack**
- **Prometheus** - Metrics collection
- **Grafana** - Visualization dashboards
- **Custom Dashboards** - Application-specific monitoring

---

## 🎯 **FUNCTIONAL AREAS**

### **Data Collection Pipeline**
- **RSS Collectors** - Automated news feed collection
- **Content Ingestion** - Processing and storing articles
- **Source Management** - Managing news sources and feeds

### **AI/ML Processing**
- **Article Analysis** - AI-powered content analysis
- **Story Classification** - Categorizing and grouping content
- **Sentiment Analysis** - Determining content sentiment
- **Entity Extraction** - Identifying key people, places, organizations
- **Content Summarization** - AI-generated summaries

### **Intelligence Delivery**
- **Real-time Dashboards** - Live system monitoring
- **Story Tracking** - Following story evolution
- **Search and Discovery** - Finding relevant content
- **Automated Briefings** - Daily digest generation

### **System Management**
- **Content Deduplication** - Removing duplicate content
- **Priority Management** - Ranking and filtering content
- **Automation Workflows** - Automated processing pipelines
- **System Monitoring** - Health and performance tracking

---

## 🚀 **DEPLOYMENT COMPONENTS**

### **Deployment Scripts** (`/scripts/deployment/`)
- **`deploy-unified.sh`** - Main deployment script
- **`deploy-v2.9.sh`** - Version-specific deployment
- **`deployment-dashboard.sh`** - Deployment monitoring
- **`setup_nas_admin.sh`** - NAS administration setup
- **`setup_nas_storage.sh`** - NAS storage configuration

### **Configuration Files**
- **`.env`** - Environment variables
- **`env.example`** - Environment template
- **`news-system.service`** - System service configuration

---

## 📊 **COMMON REFERENCE TERMS**

### **Backend References**
- **"API Server"** - The FastAPI backend (`/api/`)
- **"Backend Routes"** - API endpoints (`/api/routes/`)
- **"Business Logic"** - Core processing (`/api/modules/`)
- **"Database Layer"** - PostgreSQL and Redis

### **Frontend References**
- **"Web App"** - The React frontend (`/web/`)
- **"React Components"** - UI components (`/web/src/components/`)
- **"Page Components"** - Main pages (`/web/src/pages/`)
- **"Service Layer"** - API communication (`/web/src/services/`)

### **System References**
- **"News Intelligence System"** - The complete platform
- **"AI Engine"** - Llama 3.1 70B and ML models
- **"Data Pipeline"** - Collection → Processing → Delivery
- **"Infrastructure"** - Docker, NAS, monitoring stack

### **Functional References**
- **"Content Processing"** - AI analysis and categorization
- **"Story Tracking"** - Following story evolution
- **"Intelligence Delivery"** - Dashboards and insights
- **"System Monitoring"** - Health and performance tracking

---

## 🎯 **QUICK REFERENCE**

| **Component** | **Location** | **Purpose** |
|---------------|--------------|-------------|
| **API Server** | `/api/` | Backend FastAPI application |
| **Web App** | `/web/` | Frontend React application |
| **Dashboard** | `/web/src/pages/Dashboard/` | Main dashboard interface |
| **Articles** | `/web/src/pages/Articles/` | Article management |
| **Intelligence** | `/web/src/pages/Intelligence/` | AI insights and analysis |
| **Stories** | `/web/src/pages/Stories/` | Story tracking |
| **RSS Management** | `/web/src/pages/RSSManagement/` | Feed management |
| **Monitoring** | `/web/src/pages/Monitoring/` | System monitoring |
| **API Routes** | `/api/routes/` | Backend API endpoints |
| **Business Logic** | `/api/modules/` | Core processing logic |
| **Database** | `/api/database/` | Database configuration |
| **Deployment** | `/scripts/deployment/` | Deployment scripts |

This vocabulary provides a common language for referencing different parts of the News Intelligence System during development and maintenance.
