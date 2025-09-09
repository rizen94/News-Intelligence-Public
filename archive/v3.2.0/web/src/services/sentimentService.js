// News Intelligence System v3.1.0 - Sentiment Analysis Service
// Handles sentiment analysis API calls

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

class SentimentService {
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

  // Analyze text sentiment
  async analyzeSentiment(text) {
    return await this.makeRequest('/api/sentiment/analyze', {
      method: 'POST',
      body: JSON.stringify({ text }),
    });
  }

  // Get sentiment statistics
  async getSentimentStats() {
    return await this.makeRequest('/api/sentiment/stats/');
  }

  // Get sentiment trends
  async getSentimentTrends(period = '7d') {
    return await this.makeRequest(`/api/sentiment/trends/?period=${period}`);
  }

  // Batch sentiment analysis
  async batchAnalyzeSentiment(texts) {
    return await this.makeRequest('/api/sentiment/batch', {
      method: 'POST',
      body: JSON.stringify({ texts }),
    });
  }
}

export default new SentimentService();