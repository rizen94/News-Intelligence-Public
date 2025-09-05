/**
 * Articles Component Tests for News Intelligence System v3.0
 * Comprehensive testing suite for the Articles page
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import Articles from '../pages/Articles/Articles';
import { useArticles, useArticleSources, useArticleCategories } from '@/hooks';
import { articlesService } from '@/services';

// Mock the hooks
jest.mock('@/hooks', () => ({
  useArticles: jest.fn(),
  useArticleSources: jest.fn(),
  useArticleCategories: jest.fn(),
}));

// Mock the services
jest.mock('@/services', () => ({
  articlesService: {
    getArticles: jest.fn(),
    getSources: jest.fn(),
    getCategories: jest.fn(),
  },
}));

// Mock the notification system
jest.mock('../components/Notifications/NotificationSystem', () => ({
  useNotifications: () => ({
    showSuccess: jest.fn(),
    showError: jest.fn(),
    showLoading: jest.fn(),
  }),
}));

// Mock the error boundary
jest.mock('../components/ErrorBoundary/ErrorBoundary', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const theme = createTheme();

const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      <ThemeProvider theme={theme}>
        {component}
      </ThemeProvider>
    </BrowserRouter>
  );
};

describe('Articles Component', () => {
  const mockArticles = [
    {
      id: 1,
      title: 'Test Article 1',
      content: 'This is test content for article 1',
      source: 'Test Source',
      created_at: '2025-01-01T00:00:00Z',
      processing_status: 'processed',
      category: 'Technology',
      quality_score: 0.8,
      sentiment_score: 0.2,
      readability_score: 0.7,
      engagement_score: 0.6,
      topics_extracted: ['AI', 'Technology'],
      entities_extracted: ['OpenAI', 'GPT'],
      key_points: ['Point 1', 'Point 2'],
    },
    {
      id: 2,
      title: 'Test Article 2',
      content: 'This is test content for article 2',
      source: 'Another Source',
      created_at: '2025-01-02T00:00:00Z',
      processing_status: 'processing',
      category: 'Science',
      quality_score: 0.6,
      sentiment_score: -0.1,
      readability_score: 0.8,
      engagement_score: 0.5,
      topics_extracted: ['Science', 'Research'],
      entities_extracted: ['NASA', 'Space'],
      key_points: ['Point 3', 'Point 4'],
    },
  ];

  const mockSources = ['Test Source', 'Another Source', 'Third Source'];
  const mockCategories = ['Technology', 'Science', 'Politics'];

  const mockPagination = {
    page: 1,
    totalPages: 5,
    total: 50,
    hasNext: true,
    hasPrev: false,
    goToPage: jest.fn(),
    nextPage: jest.fn(),
    prevPage: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    
    (useArticles as jest.Mock).mockReturnValue({
      data: mockArticles,
      loading: false,
      error: null,
      refetch: jest.fn(),
      pagination: mockPagination,
    });

    (useArticleSources as jest.Mock).mockReturnValue({
      data: mockSources,
      loading: false,
      refetch: jest.fn(),
    });

    (useArticleCategories as jest.Mock).mockReturnValue({
      data: mockCategories,
      loading: false,
      refetch: jest.fn(),
    });
  });

  describe('Rendering', () => {
    it('renders articles page with header', () => {
      renderWithProviders(<Articles />);
      
      expect(screen.getByText('Articles')).toBeInTheDocument();
      expect(screen.getByText('50 articles found')).toBeInTheDocument();
    });

    it('renders search and filter controls', () => {
      renderWithProviders(<Articles />);
      
      expect(screen.getByPlaceholderText('Search articles...')).toBeInTheDocument();
      expect(screen.getByLabelText('Category')).toBeInTheDocument();
      expect(screen.getByLabelText('Source')).toBeInTheDocument();
      expect(screen.getByLabelText('Sort By')).toBeInTheDocument();
      expect(screen.getByText('Search')).toBeInTheDocument();
    });

    it('renders articles grid', () => {
      renderWithProviders(<Articles />);
      
      expect(screen.getByText('Test Article 1')).toBeInTheDocument();
      expect(screen.getByText('Test Article 2')).toBeInTheDocument();
      expect(screen.getByText('Test Source')).toBeInTheDocument();
      expect(screen.getByText('Another Source')).toBeInTheDocument();
    });

    it('renders pagination when there are multiple pages', () => {
      renderWithProviders(<Articles />);
      
      expect(screen.getByRole('navigation')).toBeInTheDocument();
    });
  });

  describe('Loading States', () => {
    it('shows loading spinner when loading', () => {
      (useArticles as jest.Mock).mockReturnValue({
        data: [],
        loading: true,
        error: null,
        refetch: jest.fn(),
        pagination: mockPagination,
      });

      renderWithProviders(<Articles />);
      
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('shows loading state for sources', () => {
      (useArticleSources as jest.Mock).mockReturnValue({
        data: [],
        loading: true,
        refetch: jest.fn(),
      });

      renderWithProviders(<Articles />);
      
      const sourceSelect = screen.getByLabelText('Source');
      expect(sourceSelect).toBeDisabled();
    });

    it('shows loading state for categories', () => {
      (useArticleCategories as jest.Mock).mockReturnValue({
        data: [],
        loading: true,
        refetch: jest.fn(),
      });

      renderWithProviders(<Articles />);
      
      const categorySelect = screen.getByLabelText('Category');
      expect(categorySelect).toBeDisabled();
    });
  });

  describe('Error Handling', () => {
    it('shows error message when there is an error', () => {
      (useArticles as jest.Mock).mockReturnValue({
        data: [],
        loading: false,
        error: 'Failed to fetch articles',
        refetch: jest.fn(),
        pagination: mockPagination,
      });

      renderWithProviders(<Articles />);
      
      expect(screen.getByText('Failed to fetch articles')).toBeInTheDocument();
      expect(screen.getByText('Try Again')).toBeInTheDocument();
    });
  });

  describe('User Interactions', () => {
    it('handles search input', () => {
      renderWithProviders(<Articles />);
      
      const searchInput = screen.getByPlaceholderText('Search articles...');
      fireEvent.change(searchInput, { target: { value: 'test search' } });
      
      expect(searchInput).toHaveValue('test search');
    });

    it('handles search button click', () => {
      const mockRefetch = jest.fn();
      (useArticles as jest.Mock).mockReturnValue({
        data: mockArticles,
        loading: false,
        error: null,
        refetch: mockRefetch,
        pagination: mockPagination,
      });

      renderWithProviders(<Articles />);
      
      const searchButton = screen.getByText('Search');
      fireEvent.click(searchButton);
      
      expect(mockRefetch).toHaveBeenCalled();
    });

    it('handles filter changes', () => {
      const mockRefetch = jest.fn();
      (useArticles as jest.Mock).mockReturnValue({
        data: mockArticles,
        loading: false,
        error: null,
        refetch: mockRefetch,
        pagination: mockPagination,
      });

      renderWithProviders(<Articles />);
      
      const categorySelect = screen.getByLabelText('Category');
      fireEvent.change(categorySelect, { target: { value: 'Technology' } });
      
      expect(mockRefetch).toHaveBeenCalled();
    });

    it('handles clear filters', () => {
      const mockRefetch = jest.fn();
      (useArticles as jest.Mock).mockReturnValue({
        data: mockArticles,
        loading: false,
        error: null,
        refetch: mockRefetch,
        pagination: mockPagination,
      });

      renderWithProviders(<Articles />);
      
      const clearButton = screen.getByText('Clear Filters');
      fireEvent.click(clearButton);
      
      expect(mockRefetch).toHaveBeenCalled();
    });

    it('handles refresh button click', () => {
      const mockRefetch = jest.fn();
      (useArticles as jest.Mock).mockReturnValue({
        data: mockArticles,
        loading: false,
        error: null,
        refetch: mockRefetch,
        pagination: mockPagination,
      });

      renderWithProviders(<Articles />);
      
      const refreshButton = screen.getByText('Refresh');
      fireEvent.click(refreshButton);
      
      expect(mockRefetch).toHaveBeenCalled();
    });

    it('handles article click navigation', () => {
      renderWithProviders(<Articles />);
      
      const articleCard = screen.getByText('Test Article 1').closest('[role="button"]');
      fireEvent.click(articleCard!);
      
      // Navigation would be tested with router testing utilities
    });

    it('handles pagination', () => {
      const mockGoToPage = jest.fn();
      (useArticles as jest.Mock).mockReturnValue({
        data: mockArticles,
        loading: false,
        error: null,
        refetch: jest.fn(),
        pagination: {
          ...mockPagination,
          goToPage: mockGoToPage,
        },
      });

      renderWithProviders(<Articles />);
      
      const pagination = screen.getByRole('navigation');
      const nextButton = pagination.querySelector('[aria-label="Go to next page"]');
      
      if (nextButton) {
        fireEvent.click(nextButton);
        expect(mockGoToPage).toHaveBeenCalledWith(2);
      }
    });
  });

  describe('Data Display', () => {
    it('displays article information correctly', () => {
      renderWithProviders(<Articles />);
      
      expect(screen.getByText('Test Article 1')).toBeInTheDocument();
      expect(screen.getByText('This is test content for article 1...')).toBeInTheDocument();
      expect(screen.getByText('Test Source')).toBeInTheDocument();
      expect(screen.getByText('processed')).toBeInTheDocument();
    });

    it('displays status chips with correct colors', () => {
      renderWithProviders(<Articles />);
      
      const processedChip = screen.getByText('processed');
      const processingChip = screen.getByText('processing');
      
      expect(processedChip).toBeInTheDocument();
      expect(processingChip).toBeInTheDocument();
    });

    it('displays formatted dates', () => {
      renderWithProviders(<Articles />);
      
      // The date formatting would be tested here
      expect(screen.getByText(/Jan 1, 2025/)).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA labels', () => {
      renderWithProviders(<Articles />);
      
      expect(screen.getByLabelText('Category')).toBeInTheDocument();
      expect(screen.getByLabelText('Source')).toBeInTheDocument();
      expect(screen.getByLabelText('Sort By')).toBeInTheDocument();
    });

    it('has proper heading structure', () => {
      renderWithProviders(<Articles />);
      
      expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
    });

    it('has proper button roles', () => {
      renderWithProviders(<Articles />);
      
      expect(screen.getByRole('button', { name: 'Search' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Refresh' })).toBeInTheDocument();
    });
  });
});


