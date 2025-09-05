import React, { createContext, useContext, useReducer, useEffect } from 'react';
import newsSystemService from '../services/newsSystemService';

const NewsSystemContext = createContext();

const initialState = {
  // System Status
  systemStatus: {
    isOnline: false,
    lastUpdate: null,
    version: 'v3.1.0',
  },
  
  // Dashboard Data
  dashboard: {
    articleCount: 0,
    clusterCount: 0,
    entityCount: 0,
    sourceCount: 0,
    recentArticles: [],
    topSources: [],
    topEntities: [],
    feedHealth: [],
  },
  
  // Articles
  articles: {
    list: [],
    total: 0,
    loading: false,
    filters: {
      dateRange: null,
      source: '',
      category: '',
      language: '',
    },
  },
  
  // Clusters
  clusters: {
    list: [],
    total: 0,
    loading: false,
    selectedCluster: null,
  },
  
  // Entities
  entities: {
    list: [],
    total: 0,
    loading: false,
    types: ['PERSON', 'ORG', 'GPE', 'LOCATION'],
    selectedType: 'PERSON',
  },
  
  // Sources
  sources: {
    list: [],
    total: 0,
    loading: false,
    healthMetrics: [],
  },
  
  // Pipeline Status
  pipeline: {
    status: 'idle',
    currentStep: null,
    progress: 0,
    lastRun: null,
    statistics: {
      articlesProcessed: 0,
      duplicatesRemoved: 0,
      entitiesExtracted: 0,
      clustersCreated: 0,
    },
  },
  
  // Search
  search: {
    query: '',
    results: [],
    loading: false,
    filters: {},
  },
  
  // Monitoring
  monitoring: {
    logs: [],
    errors: [],
    performance: {},
    alerts: [],
  },
  
  // UI State
  ui: {
    sidebarOpen: true,
    theme: 'light',
    notifications: [],
  },
};

const actionTypes = {
  // System Status
  SET_SYSTEM_STATUS: 'SET_SYSTEM_STATUS',
  UPDATE_SYSTEM_STATUS: 'UPDATE_SYSTEM_STATUS',
  
  // Dashboard
  SET_DASHBOARD_DATA: 'SET_DASHBOARD_DATA',
  UPDATE_DASHBOARD_DATA: 'UPDATE_DASHBOARD_DATA',
  
  // Articles
  SET_ARTICLES: 'SET_ARTICLES',
  SET_ARTICLES_LOADING: 'SET_ARTICLES_LOADING',
  SET_ARTICLES_FILTERS: 'SET_ARTICLES_FILTERS',
  ADD_ARTICLE: 'ADD_ARTICLE',
  UPDATE_ARTICLE: 'UPDATE_ARTICLE',
  
  // Clusters
  SET_CLUSTERS: 'SET_CLUSTERS',
  SET_CLUSTERS_LOADING: 'SET_CLUSTERS_LOADING',
  SET_SELECTED_CLUSTER: 'SET_SELECTED_CLUSTER',
  
  // Entities
  SET_ENTITIES: 'SET_ENTITIES',
  SET_ENTITIES_LOADING: 'SET_ENTITIES_LOADING',
  SET_ENTITIES_TYPE: 'SET_ENTITIES_TYPE',
  
  // Sources
  SET_SOURCES: 'SET_SOURCES',
  SET_SOURCES_LOADING: 'SET_SOURCES_LOADING',
  UPDATE_SOURCE_HEALTH: 'UPDATE_SOURCE_HEALTH',
  
  // Pipeline
  SET_PIPELINE_STATUS: 'SET_PIPELINE_STATUS',
  UPDATE_PIPELINE_PROGRESS: 'UPDATE_PIPELINE_PROGRESS',
  SET_PIPELINE_STATISTICS: 'SET_PIPELINE_STATISTICS',
  
  // Search
  SET_SEARCH_QUERY: 'SET_SEARCH_QUERY',
  SET_SEARCH_RESULTS: 'SET_SEARCH_RESULTS',
  SET_SEARCH_LOADING: 'SET_SEARCH_LOADING',
  
  // Monitoring
  ADD_LOG: 'ADD_LOG',
  ADD_ERROR: 'ADD_ERROR',
  SET_PERFORMANCE: 'SET_PERFORMANCE',
  ADD_ALERT: 'ADD_ALERT',
  
  // UI
  TOGGLE_SIDEBAR: 'TOGGLE_SIDEBAR',
  SET_THEME: 'SET_THEME',
  ADD_NOTIFICATION: 'ADD_NOTIFICATION',
  REMOVE_NOTIFICATION: 'REMOVE_NOTIFICATION',
};

function newsSystemReducer(state, action) {
  switch (action.type) {
    case actionTypes.SET_SYSTEM_STATUS:
      return {
        ...state,
        systemStatus: { ...state.systemStatus, ...action.payload },
      };
      
    case actionTypes.SET_DASHBOARD_DATA:
      return {
        ...state,
        dashboard: { ...state.dashboard, ...action.payload },
      };
      
    case actionTypes.SET_ARTICLES:
      return {
        ...state,
        articles: {
          ...state.articles,
          list: action.payload.articles || [],
          total: action.payload.total || 0,
        },
      };
      
    case actionTypes.SET_ARTICLES_LOADING:
      return {
        ...state,
        articles: { ...state.articles, loading: action.payload },
      };
      
    case actionTypes.SET_ARTICLES_FILTERS:
      return {
        ...state,
        articles: {
          ...state.articles,
          filters: { ...state.articles.filters, ...action.payload },
        },
      };
      
    case actionTypes.SET_CLUSTERS:
      return {
        ...state,
        clusters: {
          ...state.clusters,
          list: action.payload.clusters || [],
          total: action.payload.total || 0,
        },
      };
      
    case actionTypes.SET_CLUSTERS_LOADING:
      return {
        ...state,
        clusters: { ...state.clusters, loading: action.payload },
      };
      
    case actionTypes.SET_SELECTED_CLUSTER:
      return {
        ...state,
        clusters: { ...state.clusters, selectedCluster: action.payload },
      };
      
    case actionTypes.SET_ENTITIES:
      return {
        ...state,
        entities: {
          ...state.entities,
          list: action.payload.entities || [],
          total: action.payload.total || 0,
        },
      };
      
    case actionTypes.SET_ENTITIES_LOADING:
      return {
        ...state,
        entities: { ...state.entities, loading: action.payload },
      };
      
    case actionTypes.SET_ENTITIES_TYPE:
      return {
        ...state,
        entities: { ...state.entities, selectedType: action.payload },
      };
      
    case actionTypes.SET_SOURCES:
      return {
        ...state,
        sources: {
          ...state.sources,
          list: action.payload.sources || [],
          total: action.payload.total || 0,
        },
      };
      
    case actionTypes.SET_SOURCES_LOADING:
      return {
        ...state,
        sources: { ...state.sources, loading: action.payload },
      };
      
    case actionTypes.SET_PIPELINE_STATUS:
      return {
        ...state,
        pipeline: { ...state.pipeline, ...action.payload },
      };
      
    case actionTypes.SET_PIPELINE_STATISTICS:
      return {
        ...state,
        pipeline: {
          ...state.pipeline,
          statistics: { ...state.pipeline.statistics, ...action.payload },
        },
      };
      
    case actionTypes.SET_SEARCH_QUERY:
      return {
        ...state,
        search: { ...state.search, query: action.payload },
      };
      
    case actionTypes.SET_SEARCH_RESULTS:
      return {
        ...state,
        search: {
          ...state.search,
          results: action.payload.results || [],
          filters: action.payload.filters || {},
        },
      };
      
    case actionTypes.SET_SEARCH_LOADING:
      return {
        ...state,
        search: { ...state.search, loading: action.payload },
      };
      
    case actionTypes.ADD_LOG:
      return {
        ...state,
        monitoring: {
          ...state.monitoring,
          logs: [...state.monitoring.logs.slice(-99), action.payload],
        },
      };
      
    case actionTypes.ADD_ERROR:
      return {
        ...state,
        monitoring: {
          ...state.monitoring,
          errors: [...state.monitoring.errors.slice(-49), action.payload],
        },
      };
      
    case actionTypes.TOGGLE_SIDEBAR:
      return {
        ...state,
        ui: { ...state.ui, sidebarOpen: !state.ui.sidebarOpen },
      };
      
    case actionTypes.SET_THEME:
      return {
        ...state,
        ui: { ...state.ui, theme: action.payload },
      };
      
    case actionTypes.ADD_NOTIFICATION:
      return {
        ...state,
        ui: {
          ...state.ui,
          notifications: [...state.ui.notifications, action.payload],
        },
      };
      
    case actionTypes.REMOVE_NOTIFICATION:
      return {
        ...state,
        ui: {
          ...state.ui,
          notifications: state.ui.notifications.filter(
            (n) => n.id !== action.payload
          ),
        },
      };
      
    default:
      return state;
  }
}

export function NewsSystemProvider({ children }) {
  const [state, dispatch] = useReducer(newsSystemReducer, initialState);

  // Initialize system on mount
  useEffect(() => {
    initializeSystem();
    const interval = setInterval(updateSystemStatus, 30000); // Update every 30 seconds
    
    return () => clearInterval(interval);
  }, []);

  const initializeSystem = async () => {
    try {
      dispatch({ type: actionTypes.ADD_LOG, payload: { level: 'info', message: 'Initializing News Intelligence System...', timestamp: new Date() } });
      
      // Get system status
      const status = await newsSystemService.getSystemStatus();
      dispatch({ type: actionTypes.SET_SYSTEM_STATUS, payload: status });
      
      // Get dashboard data
      const dashboardData = await newsSystemService.getDashboardData();
      dispatch({ type: actionTypes.SET_DASHBOARD_DATA, payload: dashboardData });
      
      dispatch({ type: actionTypes.ADD_LOG, payload: { level: 'info', message: 'System initialized successfully', timestamp: new Date() } });
    } catch (error) {
      dispatch({ type: actionTypes.ADD_ERROR, payload: { message: 'Failed to initialize system', error: error.message, timestamp: new Date() } });
    }
  };

  const updateSystemStatus = async () => {
    try {
      const status = await newsSystemService.getSystemStatus();
      dispatch({ type: actionTypes.UPDATE_SYSTEM_STATUS, payload: status });
    } catch (error) {
      dispatch({ type: actionTypes.ADD_ERROR, payload: { message: 'Failed to update system status', error: error.message, timestamp: new Date() } });
    }
  };

  const value = {
    state,
    dispatch,
    actions: {
      // Articles
      fetchArticles: async (filters = {}) => {
        dispatch({ type: actionTypes.SET_ARTICLES_LOADING, payload: true });
        try {
          const result = await newsSystemService.getArticles(filters);
          dispatch({ type: actionTypes.SET_ARTICLES, payload: result });
        } catch (error) {
          dispatch({ type: actionTypes.ADD_ERROR, payload: { message: 'Failed to fetch articles', error: error.message, timestamp: new Date() } });
        } finally {
          dispatch({ type: actionTypes.SET_ARTICLES_LOADING, payload: false });
        }
      },
      
      // Clusters
      fetchClusters: async () => {
        dispatch({ type: actionTypes.SET_CLUSTERS_LOADING, payload: true });
        try {
          const result = await newsSystemService.getClusters();
          dispatch({ type: actionTypes.SET_CLUSTERS, payload: result });
        } catch (error) {
          dispatch({ type: actionTypes.ADD_ERROR, payload: { message: 'Failed to fetch clusters', error: error.message, timestamp: new Date() } });
        } finally {
          dispatch({ type: actionTypes.SET_CLUSTERS_LOADING, payload: false });
        }
      },
      
      // Entities
      fetchEntities: async (type = 'PERSON') => {
        dispatch({ type: actionTypes.SET_ENTITIES_LOADING, payload: true });
        try {
          const result = await newsSystemService.getEntities(type);
          dispatch({ type: actionTypes.SET_ENTITIES, payload: result });
        } catch (error) {
          dispatch({ type: actionTypes.ADD_ERROR, payload: { message: 'Failed to fetch entities', error: error.message, timestamp: new Date() } });
        } finally {
          dispatch({ type: actionTypes.SET_ENTITIES_LOADING, payload: false });
        }
      },
      
      // Sources
      fetchSources: async () => {
        dispatch({ type: actionTypes.SET_SOURCES_LOADING, payload: true });
        try {
          const result = await newsSystemService.getSources();
          dispatch({ type: actionTypes.SET_SOURCES, payload: result });
        } catch (error) {
          dispatch({ type: actionTypes.ADD_ERROR, payload: { message: 'Failed to fetch sources', error: error.message, timestamp: new Date() } });
        } finally {
          dispatch({ type: actionTypes.SET_SOURCES_LOADING, payload: false });
        }
      },
      
      // Search
      performSearch: async (query, filters = {}) => {
        dispatch({ type: actionTypes.SET_SEARCH_LOADING, payload: true });
        try {
          const result = await newsSystemService.search(query, filters);
          dispatch({ type: actionTypes.SET_SEARCH_RESULTS, payload: result });
        } catch (error) {
          dispatch({ type: actionTypes.ADD_ERROR, payload: { message: 'Search failed', error: error.message, timestamp: new Date() } });
        } finally {
          dispatch({ type: actionTypes.SET_SEARCH_LOADING, payload: false });
        }
      },
      
      // Pipeline
      runPipeline: async () => {
        dispatch({ type: actionTypes.SET_PIPELINE_STATUS, payload: { status: 'running', currentStep: 'Starting pipeline...', progress: 0 } });
        try {
          const result = await newsSystemService.runPipeline();
          dispatch({ type: actionTypes.SET_PIPELINE_STATUS, payload: { status: 'completed', currentStep: 'Pipeline completed', progress: 100 } });
          dispatch({ type: actionTypes.SET_PIPELINE_STATISTICS, payload: result.statistics });
        } catch (error) {
          dispatch({ type: actionTypes.SET_PIPELINE_STATUS, payload: { status: 'error', currentStep: 'Pipeline failed', progress: 0 } });
          dispatch({ type: actionTypes.ADD_ERROR, payload: { message: 'Pipeline execution failed', error: error.message, timestamp: new Date() } });
        }
      },
      
      // UI
      toggleSidebar: () => dispatch({ type: actionTypes.TOGGLE_SIDEBAR }),
      setTheme: (theme) => dispatch({ type: actionTypes.SET_THEME, payload: theme }),
      addNotification: (notification) => dispatch({ type: actionTypes.ADD_NOTIFICATION, payload: { ...notification, id: Date.now() } }),
      removeNotification: (id) => dispatch({ type: actionTypes.REMOVE_NOTIFICATION, payload: id }),
    },
  };

  return (
    <NewsSystemContext.Provider value={value}>
      {children}
    </NewsSystemContext.Provider>
  );
}

export function useNewsSystem() {
  const context = useContext(NewsSystemContext);
  if (!context) {
    throw new Error('useNewsSystem must be used within a NewsSystemProvider');
  }
  return context;
}

export { actionTypes };
