/**
 * News Intelligence System v3.1.0 - Production API Service
 * Centralized API communication with robust error handling
 */

const API_BASE_URL = 'http://localhost:8000/api';

export interface APIResponse<T = any> {
  success: boolean;
  data: T;
  message: string;
  error?: string;
  meta?: any;
  timestamp: string;
}

export interface Article {
  id: string;
  title: string;
  content?: string;
  url?: string;
  source?: string;
  published_at?: string;
  created_at: string;
  updated_at: string;
  status: string;
  category?: string;
  tags: string[];
  sentiment_score?: number;
  entities?: any;
  readability_score?: number;
  quality_score?: number;
  processing_status: string;
  processing_completed_at?: string;
  summary?: string;
  ml_data?: any;
  language: string;
  word_count: number;
  reading_time: number;
  feed_id?: number;
}

export interface ArticleList {
  items: Article[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface ArticleSearch {
  query?: string;
  source?: string;
  category?: string;
  date_from?: string;
  date_to?: string;
  tags?: string[];
  min_quality_score?: number;
  page: number;
  limit: number;
}

export interface RSSFeed {
  id: number;
  name: string;
  url: string;
  description?: string;
  tier: number;
  priority: number;
  language: string;
  country?: string;
  category: string;
  subcategory?: string;
  is_active: boolean;
  status: string;
  update_frequency: number;
  max_articles_per_update: number;
  success_rate: number;
  avg_response_time: number;
  reliability_score: number;
  created_at: string;
  updated_at: string;
}

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  services: Record<string, string>;
  details?: any;
}

class APIService {
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<APIResponse<T>> {
    const url = `${API_BASE_URL}${endpoint}`;
    
    const defaultOptions: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, { ...defaultOptions, ...options });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error(`API Error for ${endpoint}:`, error);
      throw error;
    }
  }

  // Articles API
  async getArticles(params: {
    page?: number;
    limit?: number;
    source?: string;
    category?: string;
    status?: string;
  } = {}): Promise<APIResponse<ArticleList>> {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        searchParams.append(key, value.toString());
      }
    });
    
    const queryString = searchParams.toString();
    return this.request<ArticleList>(`/articles/?${queryString}`);
  }

  async getArticle(id: string): Promise<APIResponse<Article>> {
    return this.request<Article>(`/articles/${id}`);
  }

  async createArticle(article: Partial<Article>): Promise<APIResponse<Article>> {
    return this.request<Article>('/articles/', {
      method: 'POST',
      body: JSON.stringify(article),
    });
  }

  async updateArticle(id: string, article: Partial<Article>): Promise<APIResponse<Article>> {
    return this.request<Article>(`/articles/${id}`, {
      method: 'PUT',
      body: JSON.stringify(article),
    });
  }

  async deleteArticle(id: string): Promise<APIResponse<null>> {
    return this.request<null>(`/articles/${id}`, {
      method: 'DELETE',
    });
  }

  async searchArticles(searchData: ArticleSearch): Promise<APIResponse<ArticleList>> {
    return this.request<ArticleList>('/articles/search', {
      method: 'POST',
      body: JSON.stringify(searchData),
    });
  }

  async getArticleSources(): Promise<APIResponse<string[]>> {
    return this.request<string[]>('/articles/sources');
  }

  async getArticleCategories(): Promise<APIResponse<string[]>> {
    return this.request<string[]>('/articles/categories');
  }

  async analyzeArticle(id: string): Promise<APIResponse<any>> {
    return this.request<any>(`/articles/${id}/analyze`, {
      method: 'POST',
    });
  }

  async getRelatedArticles(id: string, limit: number = 10): Promise<APIResponse<Article[]>> {
    return this.request<Article[]>(`/articles/${id}/related?limit=${limit}`);
  }

  async getArticleStats(): Promise<APIResponse<any>> {
    return this.request<any>('/articles/stats/overview');
  }

  // RSS Feeds API
  async getRSSFeeds(activeOnly: boolean = false): Promise<APIResponse<RSSFeed[]>> {
    return this.request<RSSFeed[]>(`/rss/feeds/?active_only=${activeOnly}`);
  }

  async getRSSFeed(id: number): Promise<APIResponse<RSSFeed>> {
    return this.request<RSSFeed>(`/rss/feeds/${id}`);
  }

  async createRSSFeed(feed: Partial<RSSFeed>): Promise<APIResponse<RSSFeed>> {
    return this.request<RSSFeed>('/rss/feeds/', {
      method: 'POST',
      body: JSON.stringify(feed),
    });
  }

  async updateRSSFeed(id: number, feed: Partial<RSSFeed>): Promise<APIResponse<RSSFeed>> {
    return this.request<RSSFeed>(`/rss/feeds/${id}`, {
      method: 'PUT',
      body: JSON.stringify(feed),
    });
  }

  async deleteRSSFeed(id: number): Promise<APIResponse<null>> {
    return this.request<null>(`/rss/feeds/${id}`, {
      method: 'DELETE',
    });
  }

  async testRSSFeed(id: number): Promise<APIResponse<any>> {
    return this.request<any>(`/rss/feeds/${id}/test`, {
      method: 'POST',
    });
  }

  async refreshRSSFeed(id: number): Promise<APIResponse<any>> {
    return this.request<any>(`/rss/feeds/${id}/refresh`, {
      method: 'POST',
    });
  }

  async toggleRSSFeed(id: number): Promise<APIResponse<RSSFeed>> {
    return this.request<RSSFeed>(`/rss/feeds/${id}/toggle`, {
      method: 'PATCH',
    });
  }

  async getRSSStats(): Promise<APIResponse<any>> {
    return this.request<any>('/rss/feeds/stats/overview');
  }

  // Dashboard API
  async getDashboard(): Promise<APIResponse<any>> {
    return this.request<any>('/dashboard/');
  }

  // Health API
  async getSystemHealth(): Promise<APIResponse<HealthStatus>> {
    return this.request<HealthStatus>('/health/');
  }

  async getDatabaseHealth(): Promise<APIResponse<any>> {
    return this.request<any>('/health/database');
  }

  async getReadinessStatus(): Promise<APIResponse<{ ready: boolean }>> {
    return this.request<{ ready: boolean }>('/health/ready');
  }

  async getLivenessStatus(): Promise<APIResponse<{ live: boolean }>> {
    return this.request<{ live: boolean }>('/health/live');
  }
}

export const apiService = new APIService();
export default apiService;
