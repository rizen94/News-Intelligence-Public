import React, { createContext, useContext, useReducer, useEffect } from 'react';

import apiService from '../services/apiService';

// Initial state
const initialState = {
  articles: [],
  storylines: [],
  rssFeeds: [],
  systemHealth: null,
  loading: false,
  error: null,
  lastUpdated: null,
  stats: {
    articles: { total: 0, today: 0, thisWeek: 0 },
    storylines: { total: 0, active: 0 },
    rssFeeds: { total: 0, active: 0, errors: 0 },
  },
};

// Action types
const ActionTypes = {
  SET_LOADING: 'SET_LOADING',
  SET_ERROR: 'SET_ERROR',
  SET_ARTICLES: 'SET_ARTICLES',
  SET_STORYLINES: 'SET_STORYLINES',
  SET_RSS_FEEDS: 'SET_RSS_FEEDS',
  SET_SYSTEM_HEALTH: 'SET_SYSTEM_HEALTH',
  SET_STATS: 'SET_STATS',
  UPDATE_LAST_UPDATED: 'UPDATE_LAST_UPDATED',
  CLEAR_ERROR: 'CLEAR_ERROR',
};

// Reducer
function newsSystemReducer(state, action) {
  switch (action.type) {
  case ActionTypes.SET_LOADING:
    return { ...state, loading: action.payload };
  case ActionTypes.SET_ERROR:
    return { ...state, error: action.payload, loading: false };
  case ActionTypes.SET_ARTICLES:
    return { ...state, articles: action.payload, loading: false, error: null };
  case ActionTypes.SET_STORYLINES:
    return { ...state, storylines: action.payload, loading: false, error: null };
  case ActionTypes.SET_RSS_FEEDS:
    return { ...state, rssFeeds: action.payload, loading: false, error: null };
  case ActionTypes.SET_SYSTEM_HEALTH:
    return { ...state, systemHealth: action.payload, loading: false, error: null };
  case ActionTypes.SET_STATS:
    return { ...state, stats: action.payload, loading: false, error: null };
  case ActionTypes.UPDATE_LAST_UPDATED:
    return { ...state, lastUpdated: new Date().toISOString() };
  case ActionTypes.CLEAR_ERROR:
    return { ...state, error: null };
  default:
    return state;
  }
}

// Context
const NewsSystemContext = createContext();

// Provider component
export const NewsSystemProvider = ({ children }) => {
  const [state, dispatch] = useReducer(newsSystemReducer, initialState);

  // Load initial data
  useEffect(() => {
    loadSystemData();
  }, []);

  const loadSystemData = async() => {
    try {
      dispatch({ type: ActionTypes.SET_LOADING, payload: true });

      const [articlesData, storylinesData, rssFeedsData, healthData] = await Promise.all([
        apiService.getArticles().catch(err => ({ data: { articles: [], total_count: 0 } })),
        apiService.getStorylines().catch(err => ({ data: { storylines: [], total_count: 0 } })),
        apiService.getRSSFeeds().catch(err => ({ data: { feeds: [] } })),
        apiService.getHealth().catch(err => ({ data: { status: 'error' } })),
      ]);

      dispatch({ type: ActionTypes.SET_ARTICLES, payload: articlesData.data?.articles || [] });
      dispatch({ type: ActionTypes.SET_STORYLINES, payload: storylinesData.data?.storylines || [] });
      dispatch({ type: ActionTypes.SET_RSS_FEEDS, payload: rssFeedsData.data?.feeds || [] });
      dispatch({ type: ActionTypes.SET_SYSTEM_HEALTH, payload: healthData.data });

      // Update stats
      const stats = {
        articles: {
          total: articlesData.data?.total_count || 0,
          today: 0, // TODO: Calculate from date filtering
          thisWeek: 0, // TODO: Calculate from date filtering
        },
        storylines: {
          total: storylinesData.data?.total_count || 0,
          active: storylinesData.data?.storylines?.filter(s => s.status === 'active').length || 0,
        },
        rssFeeds: {
          total: rssFeedsData.data?.feeds?.length || 0,
          active: rssFeedsData.data?.feeds?.filter(f => f.is_active !== false).length || 0,
          errors: 0, // TODO: Calculate from error status
        },
      };

      dispatch({ type: ActionTypes.SET_STATS, payload: stats });
      dispatch({ type: ActionTypes.UPDATE_LAST_UPDATED });

    } catch (error) {
      console.error('Failed to load system data:', error);
      dispatch({ type: ActionTypes.SET_ERROR, payload: 'Failed to load system data' });
    }
  };

  const refreshData = async() => {
    await loadSystemData();
  };

  const refreshRSSFeeds = async() => {
    try {
      dispatch({ type: ActionTypes.SET_LOADING, payload: true });
      await apiService.updateRSSFeeds();
      await loadSystemData();
    } catch (error) {
      console.error('Failed to refresh RSS feeds:', error);
      dispatch({ type: ActionTypes.SET_ERROR, payload: 'Failed to refresh RSS feeds' });
    }
  };

  const runAIAnalysis = async() => {
    try {
      dispatch({ type: ActionTypes.SET_LOADING, payload: true });
      await apiService.runAIAnalysis();
      await loadSystemData();
    } catch (error) {
      console.error('Failed to run AI analysis:', error);
      dispatch({ type: ActionTypes.SET_ERROR, payload: 'Failed to run AI analysis' });
    }
  };

  const clearError = () => {
    dispatch({ type: ActionTypes.CLEAR_ERROR });
  };

  const value = {
    ...state,
    refreshData,
    refreshRSSFeeds,
    runAIAnalysis,
    clearError,
  };

  return (
    <NewsSystemContext.Provider value={value}>
      {children}
    </NewsSystemContext.Provider>
  );
};

// Hook to use the context
export function useNewsSystem() {
  const context = useContext(NewsSystemContext);
  if (!context) {
    throw new Error('useNewsSystem must be used within a NewsSystemProvider');
  }
  return context;
}

export default NewsSystemContext;
