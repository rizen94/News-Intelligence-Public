// News Intelligence System v3.1.0 - Articles Service
// Handles all article-related API calls

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

class ArticlesService {
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

  // Get articles with pagination and filters
  async getArticles(params = {}) {
    const queryParams = new URLSearchParams();
    
    if (params.page) queryParams.append('page', params.page);
    if (params.limit) queryParams.append('limit', params.limit);
    if (params.search) queryParams.append('search', params.search);
    if (params.category) queryParams.append('category', params.category);
    if (params.date_from) queryParams.append('date_from', params.date_from);
    if (params.date_to) queryParams.append('date_to', params.date_to);
    if (params.sort_by) queryParams.append('sort_by', params.sort_by);
    if (params.sort_order) queryParams.append('sort_order', params.sort_order);
    if (params.source) queryParams.append('source', params.source);

    const queryString = queryParams.toString();
    const endpoint = `/api/articles/${queryString ? `?${queryString}` : ''}`;
    
    return await this.makeRequest(endpoint);
  }

  // Get single article by ID
  async getArticle(id) {
    return await this.makeRequest(`/api/articles/${id}`);
  }

  // Get article sources
  async getSources() {
    return await this.makeRequest('/api/sources/');
  }

  // Get article categories
  async getCategories() {
    return await this.makeRequest('/api/articles/categories/');
  }

  // Search articles
  async searchArticles(query, filters = {}) {
    return await this.getArticles({
      search: query,
      ...filters,
    });
  }

  // Get trending articles
  async getTrendingArticles(limit = 10) {
    return await this.getArticles({
      limit,
      sort_by: 'published_at',
      sort_order: 'desc',
    });
  }

  // Get articles by category
  async getArticlesByCategory(category, limit = 20) {
    return await this.getArticles({
      category,
      limit,
      sort_by: 'published_at',
      sort_order: 'desc',
    });
  }

  // Get recent articles
  async getRecentArticles(limit = 10) {
    const today = new Date().toISOString().split('T')[0];
    return await this.getArticles({
      date_from: today,
      limit,
      sort_by: 'published_at',
      sort_order: 'desc',
    });
  }
}

export default new ArticlesService();