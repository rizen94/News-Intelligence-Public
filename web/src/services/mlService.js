// News Intelligence System v3.1.0 - ML Service
// Handles machine learning and AI analysis

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

class MLService {
  async makeRequest(endpoint, options = {}) {
    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        ...options,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        data: data,
        error: null,
      };
    } catch (error) {
      console.error('API request failed:', error);
      return {
        success: false,
        data: null,
        error: error.message,
      };
    }
  }

  // Get ML analysis for article
  async analyzeArticle(articleId) {
    return await this.makeRequest(`/api/advanced-ml/analyze/${articleId}`, {
      method: 'POST',
    });
  }

  // Get topic clustering
  async getTopicClusters(limit = 20) {
    return await this.makeRequest(`/api/clusters/?limit=${limit}`);
  }

  // Get readability analysis
  async getReadabilityAnalysis(text) {
    return await this.makeRequest('/api/readability/analyze', {
      method: 'POST',
      body: JSON.stringify({ text }),
    });
  }

  // Get quality metrics
  async getQualityMetrics(articleId) {
    return await this.makeRequest(`/api/readability/quality/${articleId}`);
  }

  // Get trend analysis
  async getTrendAnalysis(period = '7d') {
    return await this.makeRequest(`/api/advanced-ml/trends/?period=${period}`);
  }

  // Get impact prediction
  async getImpactPrediction(articleId) {
    return await this.makeRequest(`/api/advanced-ml/impact/${articleId}`);
  }
}

export default new MLService();