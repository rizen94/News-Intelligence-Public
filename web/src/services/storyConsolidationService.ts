/**
 * Story Consolidation Service
 * Handles AI-powered consolidation of multiple news sources into comprehensive story timelines
 * and professional journalistic reports
 */

export interface StoryTimeline {
  id: string;
  title: string;
  summary: string;
  timeline: TimelineEvent[];
  sources: number;
  lastUpdated: string;
  status: 'developing' | 'breaking' | 'concluded' | 'monitoring';
  sentiment: 'positive' | 'negative' | 'neutral' | 'mixed';
  impact: 'low' | 'medium' | 'high' | 'critical';
  confidence: number;
}

export interface TimelineEvent {
  id: string;
  timestamp: string;
  title: string;
  description: string;
  source: string;
  confidence: number;
  type: 'initial' | 'development' | 'update' | 'conclusion';
  entities?: string[];
  sentiment?: 'positive' | 'negative' | 'neutral';
}

export interface StoryConsolidation {
  id: string;
  headline: string;
  consolidatedSummary: string;
  keyPoints: string[];
  timeline: TimelineEvent[];
  sources: string[];
  aiAnalysis: {
    sentiment: string;
    entities: string[];
    topics: string[];
    credibility: number;
    bias: string;
    factCheck: number;
  };
  professionalReport: string;
  executiveSummary: string;
  recommendations: string[];
}

export interface ConsolidationRequest {
  storyId: string;
  sources: string[];
  timeframe?: string;
  focus?: string[];
  reportType?: 'breaking' | 'analysis' | 'comprehensive' | 'executive';
}

class StoryConsolidationService {
  private baseUrl: string;

  constructor() {
    this.baseUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
  }

  /**
   * Get all active story timelines
   */
  async getStoryTimelines(): Promise<StoryTimeline[]> {
    try {
      const response = await fetch(`${this.baseUrl}/api/stories/timelines/`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      return data.data || [];
    } catch (error) {
      console.error('Error fetching story timelines:', error);
      // Return mock data for development
      return this.getMockStoryTimelines();
    }
  }

  /**
   * Get consolidated story reports
   */
  async getConsolidatedStories(): Promise<StoryConsolidation[]> {
    try {
      const response = await fetch(`${this.baseUrl}/api/stories/consolidated/`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      return data.data || [];
    } catch (error) {
      console.error('Error fetching consolidated stories:', error);
      // Return mock data for development
      return this.getMockConsolidatedStories();
    }
  }

  /**
   * Generate a new consolidated story report
   */
  async generateConsolidatedReport(request: ConsolidationRequest): Promise<StoryConsolidation> {
    try {
      const response = await fetch(`${this.baseUrl}/api/stories/consolidate/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data.data;
    } catch (error) {
      console.error('Error generating consolidated report:', error);
      throw error;
    }
  }

  /**
   * Update story timeline with new events
   */
  async updateStoryTimeline(storyId: string, events: TimelineEvent[]): Promise<StoryTimeline> {
    try {
      const response = await fetch(`${this.baseUrl}/api/stories/${storyId}/timeline/`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ events }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data.data;
    } catch (error) {
      console.error('Error updating story timeline:', error);
      throw error;
    }
  }

  /**
   * Get AI analysis for a specific story
   */
  async getStoryAnalysis(storyId: string): Promise<{
    sentiment: string;
    entities: string[];
    topics: string[];
    credibility: number;
    bias: string;
    factCheck: number;
    keyInsights: string[];
  }> {
    try {
      const response = await fetch(`${this.baseUrl}/api/stories/${storyId}/analysis/`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      return data.data;
    } catch (error) {
      console.error('Error fetching story analysis:', error);
      // Return mock analysis for development
      return this.getMockStoryAnalysis();
    }
  }

  /**
   * Export consolidated report in various formats
   */
  async exportReport(storyId: string, format: 'pdf' | 'docx' | 'html' | 'json'): Promise<Blob> {
    try {
      const response = await fetch(`${this.baseUrl}/api/stories/${storyId}/export/?format=${format}`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.blob();
    } catch (error) {
      console.error('Error exporting report:', error);
      throw error;
    }
  }

  /**
   * Get real-time story updates
   */
  async getStoryUpdates(storyId: string): Promise<TimelineEvent[]> {
    try {
      const response = await fetch(`${this.baseUrl}/api/stories/${storyId}/updates/`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      return data.data || [];
    } catch (error) {
      console.error('Error fetching story updates:', error);
      return [];
    }
  }

  // Mock data for development
  private getMockStoryTimelines(): StoryTimeline[] {
    return [
      {
        id: '1',
        title: 'Global Climate Summit 2024',
        summary: 'International climate negotiations reach critical phase with new emissions targets',
        timeline: [
          {
            id: '1-1',
            timestamp: '2024-09-05T10:00:00Z',
            title: 'Summit Opens',
            description: 'World leaders gather for climate summit with ambitious goals',
            source: 'Reuters',
            confidence: 0.95,
            type: 'initial',
            entities: ['Climate Summit', 'UN', 'World Leaders'],
            sentiment: 'positive'
          },
          {
            id: '1-2',
            timestamp: '2024-09-05T14:30:00Z',
            title: 'New Emissions Targets',
            description: 'Major economies announce revised carbon reduction commitments',
            source: 'AP News',
            confidence: 0.88,
            type: 'development',
            entities: ['Emissions', 'Carbon Reduction', 'G7'],
            sentiment: 'positive'
          }
        ],
        sources: 15,
        lastUpdated: '2024-09-05T15:30:00Z',
        status: 'developing',
        sentiment: 'positive',
        impact: 'high',
        confidence: 0.92
      },
      {
        id: '2',
        title: 'Tech Industry AI Regulation',
        summary: 'Government announces new AI safety regulations affecting major tech companies',
        timeline: [
          {
            id: '2-1',
            timestamp: '2024-09-05T09:00:00Z',
            title: 'Regulation Announcement',
            description: 'New AI safety framework unveiled by regulatory body',
            source: 'TechCrunch',
            confidence: 0.92,
            type: 'initial',
            entities: ['AI Regulation', 'Tech Companies', 'Safety Framework'],
            sentiment: 'neutral'
          }
        ],
        sources: 8,
        lastUpdated: '2024-09-05T11:15:00Z',
        status: 'breaking',
        sentiment: 'mixed',
        impact: 'medium',
        confidence: 0.87
      }
    ];
  }

  private getMockConsolidatedStories(): StoryConsolidation[] {
    return [
      {
        id: '1',
        headline: 'Climate Summit Reaches Historic Agreement on Emissions',
        consolidatedSummary: 'After three days of intensive negotiations, world leaders have reached a landmark agreement on climate action, with major economies committing to more ambitious emissions targets and establishing a new global carbon trading system.',
        keyPoints: [
          'New emissions targets 40% more ambitious than previous commitments',
          'Global carbon trading system established with 95% participation',
          '$500 billion climate finance fund created for developing nations',
          'Binding enforcement mechanisms with international oversight'
        ],
        timeline: [
          {
            id: '1-1',
            timestamp: '2024-09-05T10:00:00Z',
            title: 'Summit Opens',
            description: 'World leaders gather for climate summit with ambitious goals',
            source: 'Reuters',
            confidence: 0.95,
            type: 'initial',
            entities: ['Climate Summit', 'UN', 'World Leaders'],
            sentiment: 'positive'
          },
          {
            id: '1-2',
            timestamp: '2024-09-05T14:30:00Z',
            title: 'New Emissions Targets',
            description: 'Major economies announce revised carbon reduction commitments',
            source: 'AP News',
            confidence: 0.88,
            type: 'development',
            entities: ['Emissions', 'Carbon Reduction', 'G7'],
            sentiment: 'positive'
          }
        ],
        sources: ['Reuters', 'AP News', 'BBC', 'CNN', 'The Guardian'],
        aiAnalysis: {
          sentiment: 'positive',
          entities: ['Climate Summit', 'UN', 'G7', 'G20', 'Carbon Trading'],
          topics: ['Climate Change', 'International Relations', 'Environmental Policy'],
          credibility: 0.94,
          bias: 'neutral',
          factCheck: 0.91
        },
        professionalReport: 'The 2024 Global Climate Summit has concluded with what many are calling the most significant climate agreement in history. The comprehensive deal includes unprecedented commitments from major economies, with the United States, European Union, and China all pledging to reduce emissions by 50% by 2030. The agreement also establishes a global carbon trading system that will allow countries to trade emissions credits, potentially reducing the overall cost of climate action by $2 trillion over the next decade.',
        executiveSummary: 'Historic climate agreement reached with 50% emissions reduction by 2030 and $500B climate fund.',
        recommendations: [
          'Monitor implementation of new emissions targets',
          'Track progress on climate finance fund',
          'Analyze impact on carbon markets',
          'Follow up on enforcement mechanisms'
        ]
      }
    ];
  }

  private getMockStoryAnalysis() {
    return {
      sentiment: 'positive',
      entities: ['Climate Summit', 'UN', 'G7', 'Carbon Trading'],
      topics: ['Climate Change', 'International Relations'],
      credibility: 0.94,
      bias: 'neutral',
      factCheck: 0.91,
      keyInsights: [
        'Unprecedented level of international cooperation',
        'Strong enforcement mechanisms included',
        'Significant financial commitments made',
        'High confidence in implementation success'
      ]
    };
  }
}

export const storyConsolidationService = new StoryConsolidationService();
export default storyConsolidationService;

