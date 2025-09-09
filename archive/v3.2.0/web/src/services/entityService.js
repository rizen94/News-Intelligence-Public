// News Intelligence System v3.1.0 - Entity Extraction Service
// Handles entity extraction API calls

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

class EntityService {
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

  // Extract entities from text
  async extractEntities(text) {
    return await this.makeRequest('/api/entities/extract', {
      method: 'POST',
      body: JSON.stringify({ text }),
    });
  }

  // Get entity statistics
  async getEntityStats() {
    return await this.makeRequest('/api/entities/stats/');
  }

  // Get entity trends
  async getEntityTrends(period = '7d') {
    return await this.makeRequest(`/api/entities/trends/?period=${period}`);
  }

  // Search entities
  async searchEntities(query, filters = {}) {
    const queryParams = new URLSearchParams();
    queryParams.append('q', query);
    
    Object.entries(filters).forEach(([key, value]) => {
      if (value) queryParams.append(key, value);
    });

    return await this.makeRequest(`/api/entities/search?${queryParams.toString()}`);
  }

  // Get entity details
  async getEntityDetails(entityId) {
    return await this.makeRequest(`/api/entities/${entityId}`);
  }
}

export default new EntityService();