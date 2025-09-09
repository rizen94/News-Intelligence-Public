/**
 * useArticles Hook for News Intelligence System v3.0
 * Custom hook for article management with centralized state
 */

import { useEffect, useCallback } from 'react';
import { useArticlesStore, useArticlesActions } from '../stores/articlesStore';
import { articlesService } from '../services/articlesService';
import { ArticleSearchParams, Article } from '../types/articles';
import { ErrorHandler, getErrorMessage } from '../utils/errorHandling';

export const useArticles = (params: ArticleSearchParams = {}) => {
  const { articles, loading, error, pagination } = useArticlesStore();
  const { setArticles, setLoading, setError, setPagination } = useArticlesActions();

  const fetchArticles = useCallback(async (searchParams: ArticleSearchParams = {}) => {
    try {
      setLoading(true);
      setError(null);

      const response = await articlesService.getArticles({
        ...params,
        ...searchParams,
      });

      if (response.success) {
        setArticles(response.data);
        setPagination(response.pagination);
      } else {
        throw new Error(response.error || 'Failed to fetch articles');
      }
    } catch (error) {
      const appError = ErrorHandler.handle(error, { params: searchParams });
      setError(getErrorMessage(appError));
    } finally {
      setLoading(false);
    }
  }, [params, setArticles, setLoading, setError, setPagination]);

  const refetch = useCallback(() => {
    fetchArticles(params);
  }, [fetchArticles, params]);

  const updateParams = useCallback((newParams: Partial<ArticleSearchParams>) => {
    fetchArticles({ ...params, ...newParams });
  }, [fetchArticles, params]);

  // Initial fetch
  useEffect(() => {
    fetchArticles();
  }, []);

  return {
    data: articles,
    loading,
    error,
    refetch,
    updateParams,
    pagination: {
      page: pagination.page,
      totalPages: pagination.total_pages,
      hasNext: pagination.has_next,
      hasPrev: pagination.has_prev,
      goToPage: (page: number) => updateParams({ page }),
      nextPage: () => updateParams({ page: pagination.page + 1 }),
      prevPage: () => updateParams({ page: Math.max(1, pagination.page - 1) }),
    },
  };
};

export const useArticle = (id: number) => {
  const { currentArticle, loadingArticle, articleError } = useArticlesStore();
  const { setCurrentArticle, setLoadingArticle, setArticleError } = useArticlesActions();

  const fetchArticle = useCallback(async (articleId: number) => {
    try {
      setLoadingArticle(true);
      setArticleError(null);

      const response = await articlesService.getArticle(articleId);

      if (response.success) {
        setCurrentArticle(response.data);
      } else {
        throw new Error(response.error || 'Failed to fetch article');
      }
    } catch (error) {
      const appError = ErrorHandler.handle(error, { id: articleId });
      setArticleError(getErrorMessage(appError));
    } finally {
      setLoadingArticle(false);
    }
  }, [setCurrentArticle, setLoadingArticle, setArticleError]);

  const refetch = useCallback(() => {
    if (id) {
      fetchArticle(id);
    }
  }, [fetchArticle, id]);

  // Fetch article when ID changes
  useEffect(() => {
    if (id) {
      fetchArticle(id);
    }
  }, [id, fetchArticle]);

  return {
    data: currentArticle,
    loading: loadingArticle,
    error: articleError,
    refetch,
  };
};

export const useArticleSources = () => {
  const { sources, loadingSources } = useArticlesStore();
  const { setSources, setLoadingSources } = useArticlesActions();

  const fetchSources = useCallback(async () => {
    try {
      setLoadingSources(true);
      const response = await articlesService.getSources();
      
      if (response.success) {
        setSources(response.data.map(source => source.name));
      }
    } catch (error) {
      ErrorHandler.handle(error);
    } finally {
      setLoadingSources(false);
    }
  }, [setSources, setLoadingSources]);

  useEffect(() => {
    fetchSources();
  }, [fetchSources]);

  return {
    data: sources,
    loading: loadingSources,
    refetch: fetchSources,
  };
};

export const useArticleCategories = () => {
  const { categories, loadingCategories } = useArticlesStore();
  const { setCategories, setLoadingCategories } = useArticlesActions();

  const fetchCategories = useCallback(async () => {
    try {
      setLoadingCategories(true);
      const response = await articlesService.getCategories();
      
      if (response.success) {
        setCategories(response.data.map(category => category.name));
      }
    } catch (error) {
      ErrorHandler.handle(error);
    } finally {
      setLoadingCategories(false);
    }
  }, [setCategories, setLoadingCategories]);

  useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);

  return {
    data: categories,
    loading: loadingCategories,
    refetch: fetchCategories,
  };
};

