/**
 * Articles Store for News Intelligence System v3.0
 * Centralized state management for articles using Zustand
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { Article, ArticleSearchParams, ArticleStatus, SortField, SortOrder } from '../types/articles';

// Articles State Interface
interface ArticlesState {
  // Data
  articles: Article[];
  currentArticle: Article | null;
  sources: string[];
  categories: string[];
  
  // Loading States
  loading: boolean;
  loadingArticle: boolean;
  loadingSources: boolean;
  loadingCategories: boolean;
  
  // Error States
  error: string | null;
  articleError: string | null;
  
  // Pagination
  pagination: {
    page: number;
    per_page: number;
    total: number;
    total_pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
  
  // Filters
  filters: ArticleSearchParams;
  
  // Actions
  setArticles: (articles: Article[]) => void;
  setCurrentArticle: (article: Article | null) => void;
  setSources: (sources: string[]) => void;
  setCategories: (categories: string[]) => void;
  
  setLoading: (loading: boolean) => void;
  setLoadingArticle: (loading: boolean) => void;
  setLoadingSources: (loading: boolean) => void;
  setLoadingCategories: (loading: boolean) => void;
  
  setError: (error: string | null) => void;
  setArticleError: (error: string | null) => void;
  
  setPagination: (pagination: Partial<ArticlesState['pagination']>) => void;
  setFilters: (filters: Partial<ArticleSearchParams>) => void;
  
  // Computed Actions
  updateArticle: (id: number, updates: Partial<Article>) => void;
  removeArticle: (id: number) => void;
  clearErrors: () => void;
  reset: () => void;
}

// Initial State
const initialState = {
  articles: [],
  currentArticle: null,
  sources: [],
  categories: [],
  
  loading: false,
  loadingArticle: false,
  loadingSources: false,
  loadingCategories: false,
  
  error: null,
  articleError: null,
  
  pagination: {
    page: 1,
    per_page: 12,
    total: 0,
    total_pages: 0,
    has_next: false,
    has_prev: false,
  },
  
  filters: {
    page: 1,
    per_page: 12,
    sort_by: SortField.CREATED_AT,
    sort_order: SortOrder.DESC,
  },
};

// Articles Store
export const useArticlesStore = create<ArticlesState>()(
  devtools(
    (set, get) => ({
      ...initialState,
      
      // Data Setters
      setArticles: (articles) => set({ articles }),
      setCurrentArticle: (article) => set({ currentArticle: article }),
      setSources: (sources) => set({ sources }),
      setCategories: (categories) => set({ categories }),
      
      // Loading Setters
      setLoading: (loading) => set({ loading }),
      setLoadingArticle: (loading) => set({ loadingArticle: loading }),
      setLoadingSources: (loading) => set({ loadingSources: loading }),
      setLoadingCategories: (loading) => set({ loadingCategories: loading }),
      
      // Error Setters
      setError: (error) => set({ error }),
      setArticleError: (error) => set({ articleError: error }),
      
      // Pagination Setter
      setPagination: (pagination) => set((state) => ({
        pagination: { ...state.pagination, ...pagination }
      })),
      
      // Filters Setter
      setFilters: (filters) => set((state) => ({
        filters: { ...state.filters, ...filters }
      })),
      
      // Computed Actions
      updateArticle: (id, updates) => set((state) => ({
        articles: state.articles.map(article =>
          article.id === id ? { ...article, ...updates } : article
        ),
        currentArticle: state.currentArticle?.id === id
          ? { ...state.currentArticle, ...updates }
          : state.currentArticle
      })),
      
      removeArticle: (id) => set((state) => ({
        articles: state.articles.filter(article => article.id !== id),
        currentArticle: state.currentArticle?.id === id ? null : state.currentArticle
      })),
      
      clearErrors: () => set({
        error: null,
        articleError: null
      }),
      
      reset: () => set(initialState),
    }),
    {
      name: 'articles-store',
      partialize: (state) => ({
        // Only persist filters and pagination, not the actual data
        filters: state.filters,
        pagination: state.pagination,
      }),
    }
  )
);

// Selectors for common use cases
export const useArticles = () => useArticlesStore((state) => ({
  articles: state.articles,
  loading: state.loading,
  error: state.error,
}));

export const useCurrentArticle = () => useArticlesStore((state) => ({
  article: state.currentArticle,
  loading: state.loadingArticle,
  error: state.articleError,
}));

export const usePagination = () => useArticlesStore((state) => state.pagination);

export const useFilters = () => useArticlesStore((state) => state.filters);

export const useArticlesActions = () => useArticlesStore((state) => ({
  setArticles: state.setArticles,
  setCurrentArticle: state.setCurrentArticle,
  setLoading: state.setLoading,
  setError: state.setError,
  setPagination: state.setPagination,
  setFilters: state.setFilters,
  updateArticle: state.updateArticle,
  removeArticle: state.removeArticle,
  clearErrors: state.clearErrors,
}));

