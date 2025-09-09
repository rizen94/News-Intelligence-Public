/**
 * Storylines Service for News Intelligence System v3.0
 * Domain-specific service for storyline management
 */

import { APIResponse, PaginatedResponse } from '../types/api';
import { ErrorHandler } from '../utils/errorHandling';

// Types
export interface Storyline {
  story_id: string;
  title: string;
  description: string;
  keywords: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
  priority: number;
  expected_duration_days: number;
  current_status: string;
  last_activity: string;
  article_count: number;
  engagement_score: number;
}

export interface StorylineEvent {
  event_id: string;
  story_id: string;
  title: string;
  description: string;
  event_type: string;
  importance_score: number;
  created_at: string;
  updated_at: string;
  source: string;
  metadata: Record<string, any>;
}

export interface StorylineTimeline {
  story_id: string;
  title: string;
  description: string;
  events: StorylineEvent[];
  recent_events: StorylineEvent[];
  timeline_summary: string;
  key_developments: string[];
  next_expected_events: string[];
  created_at: string;
  updated_at: string;
}

export interface StorylineFilters {
  page?: number;
  per_page?: number;
  search?: string;
  is_active?: boolean;
  priority?: number;
  status?: string;
  sort_by?: 'created_at' | 'updated_at' | 'title' | 'priority' | 'engagement_score';
  sort_order?: 'asc' | 'desc';
}

// API Base URL
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

class StorylinesService {
  private async makeRequest<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<APIResponse<T>> {
    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        ...options,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      const appError = ErrorHandler.handle(error, { endpoint, options });
      throw appError;
    }
  }

  // Get all storylines with filters
  async getStorylines(filters: StorylineFilters = {}): Promise<PaginatedResponse<Storyline>> {
    const params = new URLSearchParams();
    
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        params.append(key, value.toString());
      }
    });

    const queryString = params.toString();
    const endpoint = `/api/story-management/stories${queryString ? `?${queryString}` : ''}`;
    
    return this.makeRequest<Storyline[]>(endpoint);
  }

  // Get active storylines
  async getActiveStorylines(): Promise<APIResponse<Storyline[]>> {
    return this.makeRequest<Storyline[]>('/api/story-management/stories?is_active=true');
  }

  // Get single storyline
  async getStoryline(storyId: string): Promise<APIResponse<Storyline>> {
    return this.makeRequest<Storyline>(`/api/story-management/stories/${storyId}`);
  }

  // Get storyline timeline
  async getStorylineTimeline(storyId: string): Promise<APIResponse<StorylineTimeline>> {
    return this.makeRequest<StorylineTimeline>(`/api/storyline-timeline/${storyId}`);
  }

  // Get storyline events
  async getStorylineEvents(storyId: string, limit: number = 50): Promise<APIResponse<StorylineEvent[]>> {
    return this.makeRequest<StorylineEvent[]>(`/api/storyline-timeline/${storyId}/events?limit=${limit}`);
  }

  // Create new storyline
  async createStoryline(storyline: Partial<Storyline>): Promise<APIResponse<Storyline>> {
    return this.makeRequest<Storyline>('/api/story-management/stories', {
      method: 'POST',
      body: JSON.stringify(storyline),
    });
  }

  // Update storyline
  async updateStoryline(storyId: string, updates: Partial<Storyline>): Promise<APIResponse<Storyline>> {
    return this.makeRequest<Storyline>(`/api/story-management/stories/${storyId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  }

  // Delete storyline
  async deleteStoryline(storyId: string): Promise<APIResponse<void>> {
    return this.makeRequest<void>(`/api/story-management/stories/${storyId}`, {
      method: 'DELETE',
    });
  }

  // Activate/deactivate storyline
  async toggleStorylineStatus(storyId: string, isActive: boolean): Promise<APIResponse<Storyline>> {
    return this.updateStoryline(storyId, { is_active: isActive });
  }

  // Add event to storyline
  async addStorylineEvent(storyId: string, event: Partial<StorylineEvent>): Promise<APIResponse<StorylineEvent>> {
    return this.makeRequest<StorylineEvent>(`/api/storyline-timeline/${storyId}/events`, {
      method: 'POST',
      body: JSON.stringify(event),
    });
  }

  // Update storyline event
  async updateStorylineEvent(storyId: string, eventId: string, updates: Partial<StorylineEvent>): Promise<APIResponse<StorylineEvent>> {
    return this.makeRequest<StorylineEvent>(`/api/storyline-timeline/${storyId}/events/${eventId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  }

  // Delete storyline event
  async deleteStorylineEvent(storyId: string, eventId: string): Promise<APIResponse<void>> {
    return this.makeRequest<void>(`/api/storyline-timeline/${storyId}/events/${eventId}`, {
      method: 'DELETE',
    });
  }

  // Get storyline statistics
  async getStorylineStats(storyId: string): Promise<APIResponse<{
    total_events: number;
    recent_events_count: number;
    average_importance: number;
    engagement_trend: number[];
    key_developments_count: number;
    last_activity: string;
  }>> {
    return this.makeRequest(`/api/storyline-timeline/${storyId}/stats`);
  }

  // Search storylines
  async searchStorylines(query: string, filters: Omit<StorylineFilters, 'search'> = {}): Promise<PaginatedResponse<Storyline>> {
    return this.getStorylines({ ...filters, search: query });
  }

  // Get trending storylines
  async getTrendingStorylines(limit: number = 10): Promise<APIResponse<Storyline[]>> {
    return this.makeRequest<Storyline[]>(`/api/story-management/stories/trending?limit=${limit}`);
  }

  // Get storyline recommendations
  async getStorylineRecommendations(storyId: string, limit: number = 5): Promise<APIResponse<Storyline[]>> {
    return this.makeRequest<Storyline[]>(`/api/story-management/stories/${storyId}/recommendations?limit=${limit}`);
  }
}

// Export singleton instance
export const storylinesService = new StorylinesService();
export default storylinesService;

