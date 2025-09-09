// News Intelligence System v3.1.0 - RSS Service
// Handles all RSS feed-related API calls

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

class RSSService {
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

  // Get all RSS feeds
  async getFeeds() {
    return await this.makeRequest('/api/rss/feeds/');
  }

  // Get single RSS feed by ID
  async getFeed(id) {
    return await this.makeRequest(`/api/rss/feeds/${id}`);
  }

  // Create new RSS feed
  async createFeed(feedData) {
    return await this.makeRequest('/api/rss/feeds/', {
      method: 'POST',
      body: JSON.stringify(feedData),
    });
  }

  // Update RSS feed
  async updateFeed(id, feedData) {
    return await this.makeRequest(`/api/rss/feeds/${id}`, {
      method: 'PUT',
      body: JSON.stringify(feedData),
    });
  }

  // Delete RSS feed
  async deleteFeed(id) {
    return await this.makeRequest(`/api/rss/feeds/${id}`, {
      method: 'DELETE',
    });
  }

  // Test RSS feed
  async testFeed(id) {
    return await this.makeRequest(`/api/rss/feeds/${id}/test`, {
      method: 'POST',
    });
  }

  // Refresh all feeds
  async refreshFeeds() {
    return await this.makeRequest('/api/rss/refresh', {
      method: 'POST',
    });
  }

  // Get feed statistics
  async getFeedStats() {
    return await this.makeRequest('/api/rss/stats/');
  }
}

export default new RSSService();