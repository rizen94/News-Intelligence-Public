// News Intelligence System v3.1.0 - Dashboard Service
// Handles dashboard data and system status

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

class DashboardService {
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

  // Get dashboard statistics
  async getDashboardStats() {
    return await this.makeRequest('/api/dashboard/stats/');
  }

  // Get system status
  async getSystemStatus() {
    return await this.makeRequest('/api/health/');
  }

  // Get recent activity
  async getRecentActivity(limit = 10) {
    return await this.makeRequest(`/api/dashboard/activity/?limit=${limit}`);
  }

  // Get system metrics
  async getSystemMetrics() {
    return await this.makeRequest('/api/monitoring/metrics/');
  }

  // Get trending topics
  async getTrendingTopics(limit = 10) {
    return await this.makeRequest(`/api/dashboard/trending/?limit=${limit}`);
  }

  // Get performance data
  async getPerformanceData() {
    return await this.makeRequest('/api/monitoring/performance/');
  }
}

export default new DashboardService();