// News Intelligence System v3.1.0 - Articles Service
// Handles all article-related API calls

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export interface Article {
  id: number;
  title: string;
  content: string;
  url: string;
  source: string;
  published_at: string;
  processing_status: string;
  created_at: string;
  processing_completed_at?: string;
  summary?: string;
  quality_score?: number;
  ml_data?: any;
  category?: string;
  sentiment_score?: number;
  entities_extracted?: string[];
  topics_extracted?: string[];
  key_points?: string[];
  readability_score?: number;
  engagement_score?: number;
}

export interface ArticleSearchParams {
  page?: number;
  per_page?: number;
  status?: string;
  source?: string;
  sort_by?: string;
  sort_order?: string;
  search?: string;
}

export interface ArticleResponse {
  success: boolean;
  data: {
    articles: Article[];
    pagination: {
      page: number;
      per_page: number;
      total: number;
      total_pages: number;
      has_next: boolean;
      has_prev: boolean;
    };
  };
  message: string;
  timestamp: string;
}

export enum SortField {
  CREATED_AT = 'created_at',
  PUBLISHED_AT = 'published_at',
  TITLE = 'title',
  SOURCE = 'source',
  QUALITY_SCORE = 'quality_score'
}

export enum SortOrder {
  ASC = 'asc',
  DESC = 'desc'
}

class ArticlesService {
  async makeRequest(endpoint: string, options: RequestInit = {}): Promise<any> {
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
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  // Get articles with filtering, sorting, and pagination
  async getArticles(params: ArticleSearchParams = {}): Promise<ArticleResponse> {
    const queryParams = new URLSearchParams();
    
    if (params.page) queryParams.append('page', params.page.toString());
    if (params.per_page) queryParams.append('per_page', params.per_page.toString());
    if (params.status) queryParams.append('status', params.status);
    if (params.source) queryParams.append('source', params.source);
    if (params.sort_by) queryParams.append('sort_by', params.sort_by);
    if (params.sort_order) queryParams.append('sort_order', params.sort_order);
    if (params.search) queryParams.append('search', params.search);

    const queryString = queryParams.toString();
    const endpoint = `/api/articles/${queryString ? `?${queryString}` : ''}`;
    
    return await this.makeRequest(endpoint);
  }

  // Get single article by ID
  async getArticle(id: number): Promise<any> {
    return await this.makeRequest(`/api/articles/${id}`);
  }

  // Get article categories
  async getCategories(): Promise<any> {
    return await this.makeRequest('/api/articles/categories');
  }

  // Get article sources
  async getSources(): Promise<any> {
    return await this.makeRequest('/api/articles/sources');
  }

  // Get article statistics
  async getStats(): Promise<any> {
    return await this.makeRequest('/api/articles/stats');
  }
}

export default new ArticlesService();
