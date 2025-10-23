# Domain 2: Content Analysis Microservice

**Domain**: Content Analysis  
**Version**: 4.0  
**Status**: 🚧 **SPECIFICATION**  
**Business Owner**: AI/ML Team  
**Technical Owner**: Data Science Team

## 🎯 **Business Purpose**

The Content Analysis domain is the AI-powered brain of the News Intelligence System, responsible for extracting deep insights, patterns, and intelligence from news content. This domain transforms raw articles into actionable intelligence through advanced ML and LLM processing, enabling sophisticated storyline creation and trend analysis.

### **Strategic Objectives**
- **Intelligence Extraction**: Convert content into structured, actionable insights
- **Pattern Recognition**: Identify trends, anomalies, and emerging stories
- **Sentiment Intelligence**: Understand emotional and political undertones
- **Entity Intelligence**: Map relationships between people, organizations, and events
- **Predictive Analysis**: Forecast trends and potential story developments

## 🏗️ **Core Responsibilities**

### **1. Sentiment Analysis**
- **Multi-dimensional Sentiment**: Analyze emotional, political, and social sentiment
- **Contextual Sentiment**: Understand sentiment within specific contexts
- **Temporal Sentiment**: Track sentiment changes over time
- **Cross-source Sentiment**: Compare sentiment across different sources

### **2. Entity Extraction & Relationship Mapping**
- **Named Entity Recognition**: Extract people, organizations, locations, events
- **Relationship Extraction**: Map connections between entities
- **Entity Resolution**: Resolve entity references across sources
- **Entity Evolution**: Track how entities change over time

### **3. Content Summarization**
- **Abstractive Summarization**: Generate human-like summaries using LLMs
- **Extractive Summarization**: Extract key sentences and phrases
- **Multi-perspective Summarization**: Create summaries from different angles
- **Progressive Summarization**: Build summaries as stories evolve

### **4. Bias Detection & Analysis**
- **Political Bias Detection**: Identify political leanings and biases
- **Media Bias Analysis**: Assess source bias and perspective
- **Content Bias Scoring**: Rate content for various types of bias
- **Bias Trend Analysis**: Track bias patterns over time

### **5. Topic Modeling & Clustering**
- **Dynamic Topic Modeling**: Discover topics as they emerge
- **Topic Evolution**: Track how topics change and develop
- **Cross-topic Relationships**: Identify connections between topics
- **Topic Quality Assessment**: Evaluate topic coherence and relevance

## 🤖 **ML/LLM Integration**

### **Processing Architecture**

#### **Batch Processing Strategy**
- **Primary Mode**: Background batch processing for all content analysis
- **Processing Loop**: Continuous loop processing new articles as they arrive
- **Quality Focus**: Prioritize accuracy and quality over speed
- **Local Models**: Self-contained system using locally hosted LLM models
- **Resource Utilization**: Full system capacity for parallel processing

#### **Hybrid Processing Approach**
- **Batch Processing**: Article ingestion, summarization, clustering, entity extraction
- **Quick Processing**: Fast assessment for storyline updates (temporary)
- **Deep Processing**: Comprehensive storyline analysis with full context
- **Iterative Review**: Quick assessments followed by thorough background analysis

### **AI-Powered Features**

#### **1. Advanced Sentiment Analysis**
```python
class SentimentAnalyzer:
    """Multi-dimensional sentiment analysis using ensemble models"""
    
    async def analyze_sentiment(self, article: Article) -> SentimentAnalysis:
        """
        Comprehensive sentiment analysis:
        - Emotional sentiment (positive/negative/neutral)
        - Political sentiment (left/right/center)
        - Social sentiment (supportive/critical/neutral)
        - Temporal sentiment (trending up/down/stable)
        """
        pass
    
    async def analyze_contextual_sentiment(self, article: Article, context: str) -> ContextualSentiment:
        """Analyze sentiment within specific context (e.g., economic, social)"""
        pass
    
    async def track_sentiment_evolution(self, entity: str, timeframe: str) -> SentimentEvolution:
        """Track how sentiment toward an entity changes over time"""
        pass
```

**Business Value**: Provides nuanced understanding of public opinion and emotional responses to news events.

#### **2. Intelligent Entity Extraction**
```python
class EntityExtractor:
    """Advanced entity recognition and relationship mapping"""
    
    async def extract_entities(self, article: Article) -> EntityExtraction:
        """
        Extract and classify entities:
        - People (politicians, celebrities, experts)
        - Organizations (companies, governments, NGOs)
        - Locations (cities, countries, regions)
        - Events (elections, disasters, announcements)
        - Concepts (policies, technologies, trends)
        """
        pass
    
    async def map_relationships(self, entities: List[Entity]) -> RelationshipMap:
        """Map relationships between entities using graph neural networks"""
        pass
    
    async def resolve_entity_references(self, entity_mentions: List[str]) -> ResolvedEntity:
        """Resolve entity references across different sources"""
        pass
```

**Business Value**: Creates comprehensive knowledge graphs that reveal hidden connections and relationships.

#### **3. LLM-Powered Summarization**
```python
class ContentSummarizer:
    """Advanced content summarization using locally hosted LLM models"""
    
    async def generate_summary(self, article: Article, style: str = "journalistic") -> Summary:
        """
        Generate journalist-quality summaries using local LLM:
        - Journalistic summary (professional reporting style)
        - Analytical summary (with insights and analysis)
        - Executive summary (high-level key points)
        - Detailed summary (comprehensive coverage)
        """
        pass
    
    async def generate_multi_perspective_summary(self, articles: List[Article]) -> MultiPerspectiveSummary:
        """Generate summary showing multiple perspectives on the same story"""
        pass
    
    async def create_progressive_summary(self, storyline_id: str) -> ProgressiveSummary:
        """Create evolving summary as storyline develops"""
        pass
    
    async def generate_storyline_report(self, storyline_id: str) -> StorylineReport:
        """Generate comprehensive storyline report with full context"""
        pass
```

**Business Value**: Provides professional-quality summaries that rival what a journalist would write, with comprehensive context and analysis.

#### **4. RAG-Enhanced Analysis**
```python
class RAGAnalysisService:
    """RAG-enhanced analysis for storyline context and temporal mapping"""
    
    async def analyze_storyline_context(self, storyline_id: str, new_articles: List[Article]) -> ContextAnalysis:
        """
        Deep analysis of storyline with new context:
        - Incorporate new articles into storyline context
        - Generate comprehensive storyline report
        - Update temporal mapping and relationships
        - Provide journalist-quality narrative
        """
        pass
    
    async def quick_storyline_assessment(self, storyline_id: str, article: Article) -> QuickAssessment:
        """Quick assessment of what new article adds to storyline (temporary)"""
        pass
    
    async def deep_storyline_review(self, storyline_id: str) -> DeepReview:
        """Comprehensive background review of entire storyline"""
        pass
```

**Business Value**: Ensures storylines are comprehensive, well-researched, and professionally written with full context integration.

#### **4. Bias Detection & Analysis**
```python
class BiasDetector:
    """AI-powered bias detection and analysis"""
    
    async def detect_bias(self, article: Article) -> BiasAnalysis:
        """
        Detect various types of bias:
        - Political bias (left/right/center)
        - Media bias (sensationalist/balanced)
        - Confirmation bias (reinforcing existing beliefs)
        - Selection bias (choosing specific facts)
        - Framing bias (presenting information in specific way)
        """
        pass
    
    async def analyze_source_bias(self, source: Source) -> SourceBiasProfile:
        """Analyze historical bias patterns of a source"""
        pass
    
    async def track_bias_trends(self, timeframe: str) -> BiasTrendAnalysis:
        """Track bias trends across sources and topics"""
        pass
```

**Business Value**: Helps users understand potential biases and provides balanced perspectives on news events.

#### **5. Dynamic Topic Modeling**
```python
class TopicModeler:
    """Dynamic topic discovery and evolution tracking"""
    
    async def discover_topics(self, articles: List[Article]) -> List[Topic]:
        """
        Discover topics using advanced ML:
        - Latent Dirichlet Allocation (LDA)
        - BERT-based topic modeling
        - Dynamic topic modeling
        - Hierarchical topic modeling
        """
        pass
    
    async def track_topic_evolution(self, topic_id: str) -> TopicEvolution:
        """Track how topics change and develop over time"""
        pass
    
    async def find_topic_relationships(self, topics: List[Topic]) -> TopicRelationshipMap:
        """Find relationships and connections between topics"""
        pass
```

**Business Value**: Automatically discovers emerging topics and tracks their evolution, enabling proactive story identification.

## 🔌 **API Endpoints**

### **Sentiment Analysis**
```python
# Sentiment Analysis
POST   /api/v4/analysis/sentiment                    # Analyze article sentiment
GET    /api/v4/analysis/sentiment/{article_id}       # Get sentiment for article
POST   /api/v4/analysis/sentiment/contextual         # Contextual sentiment analysis
GET    /api/v4/analysis/sentiment/trends             # Sentiment trend analysis
POST   /api/v4/analysis/sentiment/evolution          # Track sentiment evolution
```

### **Entity Extraction**
```python
# Entity Management
POST   /api/v4/analysis/entities                     # Extract entities from article
GET    /api/v4/analysis/entities/{entity_id}         # Get entity details
POST   /api/v4/analysis/entities/relationships       # Map entity relationships
GET    /api/v4/analysis/entities/{entity_id}/mentions # Get entity mentions
POST   /api/v4/analysis/entities/resolve             # Resolve entity references
```

### **Content Summarization**
```python
# Summarization
POST   /api/v4/analysis/summarize                    # Generate article summary
POST   /api/v4/analysis/summarize/multi-perspective  # Multi-perspective summary
POST   /api/v4/analysis/summarize/progressive        # Progressive summary
GET    /api/v4/analysis/summarize/{summary_id}       # Get summary details
POST   /api/v4/analysis/summarize/custom             # Custom summary style
```

### **Bias Detection**
```python
# Bias Analysis
POST   /api/v4/analysis/bias                         # Detect content bias
GET    /api/v4/analysis/bias/{source_id}             # Get source bias profile
GET    /api/v4/analysis/bias/trends                  # Bias trend analysis
POST   /api/v4/analysis/bias/compare                 # Compare bias across sources
GET    /api/v4/analysis/bias/dashboard               # Bias analysis dashboard
```

### **Topic Modeling**
```python
# Topic Discovery
POST   /api/v4/analysis/topics/discover             # Discover topics
GET    /api/v4/analysis/topics                       # List topics
GET    /api/v4/analysis/topics/{topic_id}            # Get topic details
GET    /api/v4/analysis/topics/{topic_id}/evolution  # Topic evolution
POST   /api/v4/analysis/topics/relationships         # Find topic relationships
```

## 📊 **Data Models**

### **Core Entities**

#### **SentimentAnalysis Model**
```python
class SentimentAnalysis(BaseModel):
    id: int
    article_id: int
    emotional_sentiment: SentimentScore  # positive/negative/neutral
    political_sentiment: PoliticalSentiment  # left/right/center
    social_sentiment: SocialSentiment  # supportive/critical/neutral
    confidence_score: float
    context: str
    analyzed_at: datetime
    model_version: str
```

#### **Entity Model**
```python
class Entity(BaseModel):
    id: int
    name: str
    type: EntityType  # person/organization/location/event/concept
    category: str
    description: Optional[str]
    aliases: List[str]
    confidence_score: float
    first_mentioned: datetime
    last_mentioned: datetime
    mention_count: int
    source_count: int
    relationships: List[EntityRelationship]
```

#### **Summary Model**
```python
class Summary(BaseModel):
    id: int
    article_id: int
    content: str
    style: SummaryStyle  # neutral/analytical/executive/detailed
    length: int
    key_points: List[str]
    confidence_score: float
    generated_at: datetime
    model_version: str
    processing_time: float
```

#### **BiasAnalysis Model**
```python
class BiasAnalysis(BaseModel):
    id: int
    article_id: int
    political_bias: PoliticalBiasScore
    media_bias: MediaBiasScore
    confirmation_bias: float
    selection_bias: float
    framing_bias: float
    overall_bias_score: float
    bias_explanation: str
    analyzed_at: datetime
    model_version: str
```

#### **Topic Model**
```python
class Topic(BaseModel):
    id: int
    name: str
    description: str
    keywords: List[str]
    coherence_score: float
    relevance_score: float
    article_count: int
    first_mentioned: datetime
    last_mentioned: datetime
    evolution_timeline: List[TopicEvolution]
    related_topics: List[TopicRelationship]
```

## 🏛️ **Service Architecture**

### **Internal Services**

#### **1. SentimentService**
```python
class SentimentService:
    """Manages sentiment analysis operations"""
    
    async def analyze_article_sentiment(self, article: Article) -> SentimentAnalysis:
        """Analyze sentiment of a single article"""
        pass
    
    async def batch_sentiment_analysis(self, articles: List[Article]) -> List[SentimentAnalysis]:
        """Batch analyze sentiment for multiple articles"""
        pass
    
    async def track_sentiment_trends(self, entity: str, timeframe: str) -> SentimentTrend:
        """Track sentiment trends for specific entity"""
        pass
    
    async def compare_sentiment_across_sources(self, topic: str) -> SourceSentimentComparison:
        """Compare sentiment across different sources for same topic"""
        pass
```

#### **2. EntityService**
```python
class EntityService:
    """Manages entity extraction and relationship mapping"""
    
    async def extract_entities_from_article(self, article: Article) -> List[Entity]:
        """Extract entities from article content"""
        pass
    
    async def build_entity_relationships(self, entities: List[Entity]) -> List[EntityRelationship]:
        """Build relationships between entities"""
        pass
    
    async def resolve_entity_mentions(self, mentions: List[str]) -> List[ResolvedEntity]:
        """Resolve entity mentions to canonical entities"""
        pass
    
    async def track_entity_evolution(self, entity_id: int) -> EntityEvolution:
        """Track how entity information evolves over time"""
        pass
```

#### **3. SummarizationService**
```python
class SummarizationService:
    """Manages content summarization using LLMs"""
    
    async def generate_article_summary(self, article: Article, style: str) -> Summary:
        """Generate summary for single article"""
        pass
    
    async def create_multi_perspective_summary(self, articles: List[Article]) -> MultiPerspectiveSummary:
        """Create summary showing multiple perspectives"""
        pass
    
    async def generate_progressive_summary(self, storyline_id: str) -> ProgressiveSummary:
        """Generate evolving summary for storyline"""
        pass
    
    async def customize_summary_style(self, summary: Summary, style: str) -> CustomSummary:
        """Customize summary style and format"""
        pass
```

#### **4. BiasDetectionService**
```python
class BiasDetectionService:
    """Manages bias detection and analysis"""
    
    async def detect_article_bias(self, article: Article) -> BiasAnalysis:
        """Detect bias in article content"""
        pass
    
    async def analyze_source_bias_patterns(self, source: Source) -> SourceBiasProfile:
        """Analyze historical bias patterns of source"""
        pass
    
    async def track_bias_trends(self, timeframe: str) -> BiasTrendAnalysis:
        """Track bias trends across sources and topics"""
        pass
    
    async def compare_bias_across_sources(self, topic: str) -> SourceBiasComparison:
        """Compare bias across sources for same topic"""
        pass
```

#### **5. TopicModelingService**
```python
class TopicModelingService:
    """Manages topic discovery and evolution"""
    
    async def discover_topics_from_articles(self, articles: List[Article]) -> List[Topic]:
        """Discover topics from article collection"""
        pass
    
    async def track_topic_evolution(self, topic_id: int) -> TopicEvolution:
        """Track how topic evolves over time"""
        pass
    
    async def find_topic_relationships(self, topics: List[Topic]) -> List[TopicRelationship]:
        """Find relationships between topics"""
        pass
    
    async def predict_topic_trends(self, topic_id: int) -> TopicTrendPrediction:
        """Predict future trends for topic"""
        pass
```

## 📈 **Performance Metrics**

### **Target Performance (Hybrid Approach)**
- **Sentiment Analysis**: < 500ms per article (real-time operations)
- **Entity Extraction**: < 750ms per article (real-time operations)
- **Content Summarization**: < 2000ms per article (batch processing with local LLM)
- **Bias Detection**: < 400ms per article (real-time operations)
- **Topic Modeling**: < 5000ms per batch (100 articles) (batch processing)
- **Storyline RAG Analysis**: < 10000ms per storyline (comprehensive review with local LLM)

### **Processing Loops (Hybrid Approach)**
- **Article Processing Loop**: Continuous batch processing of new articles (30-second intervals)
- **Storyline Analysis Loop**: Deep RAG analysis when storylines are updated (5-minute intervals)
- **Quick Assessment**: < 200ms for temporary storyline updates (real-time)
- **Deep Review**: Background processing for comprehensive analysis (batch processing)

### **Scalability Targets**
- **Concurrent Analysis**: 100+ articles per batch (quality-focused)
- **Daily Processing**: 10K+ articles per day (thorough analysis)
- **Entity Database**: 100K+ unique entities
- **Topic Tracking**: 1,000+ active topics
- **Storyline Reports**: 500+ comprehensive reports per day

### **Quality Targets**
- **Sentiment Accuracy**: 95%+ accuracy (local model optimization)
- **Entity Extraction**: 98%+ precision, 95%+ recall
- **Summary Quality**: 90%+ human evaluation score (journalist-quality)
- **Bias Detection**: 85%+ accuracy
- **Storyline Coherence**: 90%+ narrative quality score

## 🔗 **Dependencies**

### **External Dependencies**
- **Local LLM Models**: Ollama-hosted Llama 3.1 8B (primary), Mistral 7B (secondary)
- **ML Models**: Custom trained models for sentiment, entities, bias (local inference)
- **Vector Databases**: Local vector storage for RAG and embeddings
- **GPU Resources**: Local GPU for real-time ML model inference
- **Database**: PostgreSQL for structured data storage
- **Cache**: Redis for performance optimization

### **Internal Dependencies**
- **News Aggregation Domain**: For article content
- **Storyline Management Domain**: For storyline context and RAG integration
- **Intelligence Hub Domain**: For advanced analytics
- **System Monitoring Domain**: For performance tracking

## 🧪 **Testing Strategy**

### **Unit Tests**
- Individual ML model accuracy
- API endpoint functionality
- Data model validation
- Service integration

### **Integration Tests**
- End-to-end analysis pipeline
- LLM integration testing
- Database operations
- Cross-domain communication

### **Performance Tests**
- Load testing with high article volume
- ML model inference performance
- LLM response time testing
- Memory usage optimization

### **Quality Tests**
- Sentiment analysis accuracy validation
- Entity extraction precision/recall
- Summary quality human evaluation
- Bias detection accuracy testing

## 📋 **Implementation Checklist**

### **Phase 1: Core ML Infrastructure**
- [ ] Set up ML model serving infrastructure
- [ ] Implement SentimentService
- [ ] Implement EntityService
- [ ] Create basic API endpoints

### **Phase 2: LLM Integration**
- [ ] Integrate LLM services for summarization
- [ ] Implement SummarizationService
- [ ] Add bias detection capabilities
- [ ] Create advanced analysis endpoints

### **Phase 3: Advanced Features**
- [ ] Implement dynamic topic modeling
- [ ] Add relationship mapping
- [ ] Create trend analysis capabilities
- [ ] Build analysis dashboards

### **Phase 4: Production Ready**
- [ ] Performance optimization
- [ ] Comprehensive testing
- [ ] Quality validation
- [ ] Documentation completion

---

**Next Domain**: Storyline Management Microservice  
**Review Status**: ✅ **COMPLETE**  
**Approval Required**: Technical Lead, Data Science Team Lead
