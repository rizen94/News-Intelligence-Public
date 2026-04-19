/**
 * News Intelligence — web SPA entry (React + Vite + MUI).
 *
 * Routing: React Router wraps the app; routes live under `/:domain/*` (e.g.
 * `/{domain}/dashboard`) via MainLayout. Domains come from the API
 * (`/api/system_monitoring/registry_domains`) with a static fallback — see `utils/domainHelper` and AGENTS.md.
 *
 * API calls: `apiConnectionManager` sets base URL and domain for `/api/{domain}/...`
 * and global `/api/...` routes (see docs/WEB_API_CONNECTIONS.md).
 *
 * Layout: Hero status bar + sidebar (Discover, Investigate, Monitor, Analyze).
 * Public demo: `PublicDemoProvider` + `DemoRouteGuard` hide watchlist, ops, and
 * other write-heavy routes — see `AppNav` filter and guarded routes below.
 * Product display notes (incorporation candidate): docs/archive/planning_incubator/WEB_PRODUCT_DISPLAY_PLAN.md
 */
import React, { useEffect } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from 'react-router-dom';
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import './App.css';

import { DomainProvider } from './contexts/DomainContext';
import { PublicDemoProvider } from './contexts/PublicDemoContext';
import { DemoRouteGuard } from './components/DemoRouteGuard/DemoRouteGuard';
import { getAPIConnectionManager } from './services/apiConnectionManager';
import loggingService from './services/loggingService';
import errorHandler from './services/errorHandler';
import ErrorBoundary from './components/ErrorBoundary/ErrorBoundary';
import './utils/debugHelper';
import './utils/featureTestHelper';

import MainLayout from './layout/MainLayout';
import { getDefaultDomainKey } from './utils/domainHelper';
import Dashboard from './pages/Dashboard/Dashboard';
import DiscoverPage from './pages/Discover/DiscoverPage';
import ContextDetailPage from './pages/Discover/ContextDetailPage';
import InvestigatePage from './pages/Investigate/InvestigatePage';
import EventDetailPage from './pages/Investigate/EventDetailPage';
import EntityDetailPage from './pages/Investigate/EntityDetailPage';
import EntitiesListPage from './pages/Investigate/EntitiesListPage';
import SearchPage from './pages/Investigate/SearchPage';
import ProcessedDocumentsPage from './pages/Investigate/ProcessedDocumentsPage';
import ProcessedDocumentDetailPage from './pages/Investigate/ProcessedDocumentDetailPage';
import NarrativeThreadsPage from './pages/Investigate/NarrativeThreadsPage';
import EntityDossierPage from './pages/Investigate/EntityDossierPage';
import MonitorPage from './pages/Monitor/MonitorPage';
import SqlExplorerPage from './pages/Monitor/SqlExplorerPage';
import AnalyzePage from './pages/Analyze/AnalyzePage';
import AuditChecklistPage from './pages/Audit/AuditChecklistPage';
import CommodityDashboard from './pages/Finance/CommodityDashboard';
import FinancialAnalysis from './pages/Finance/FinancialAnalysis';
import FinancialAnalysisResult from './pages/Finance/FinancialAnalysisResult';
import TaskTraceViewer from './pages/Finance/TaskTraceViewer';
import Storylines from './pages/Storylines/Storylines';
import StorylineDetail from './pages/Storylines/StorylineDetail';
import StorylineDiscovery from './pages/Storylines/StorylineDiscovery';
import SynthesizedView from './pages/Storylines/SynthesizedView';
import StoryTimeline from './pages/StoryTimeline/StoryTimeline';
import Articles from './pages/Articles/Articles';
import ArticleDetail from './pages/Articles/ArticleDetail';
import ArticleDeduplicationManager from './pages/Articles/ArticleDeduplicationManager';
import Briefings from './pages/Briefings/Briefings';
import RSSFeeds from './pages/RSSFeeds/RSSFeeds';
import Topics from './pages/Topics/Topics';
import Watchlist from './pages/Watchlist/Watchlist';
import Events from './pages/Events/Events';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#1565c0' },
    secondary: { main: '#9c27b0' },
    error: { main: '#d32f2f' },
    warning: { main: '#ed6c02' },
    info: { main: '#0288d1' },
    success: { main: '#2e7d32' },
  },
});

function App() {
  const defaultDomainPath = `/${getDefaultDomainKey()}/dashboard`;
  useEffect(() => {
    errorHandler.initialize();
    loggingService.info('News Intelligence (Dashboard) initialized', {
      version: '9.0',
      environment: import.meta.env.MODE || 'development',
    });
    const connectionManager = getAPIConnectionManager();
    connectionManager.testConnection().then(connected => {
      if (connected) loggingService.info('API connection established');
      else loggingService.warn('API connection check failed');
    });
    return () => connectionManager.cleanup();
  }, []);

  return (
    <ErrorBoundary>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <DomainProvider>
          <PublicDemoProvider>
            <Router>
              <div className='App'>
                <Routes>
                <Route
                  path='/'
                  element={<Navigate to={defaultDomainPath} replace />}
                />
                <Route path='/:domain' element={<MainLayout />}>
                  <Route index element={<Navigate to='dashboard' replace />} />
                  <Route path='dashboard' element={<Dashboard />} />
                  <Route path='discover' element={<DiscoverPage />} />
                  <Route
                    path='discover/contexts/:id'
                    element={<ContextDetailPage />}
                  />
                  <Route path='storylines' element={<Storylines />} />
                  {/* Static segments before :id — otherwise "discovery" / "synthesized" match as storyline ids */}
                  <Route
                    path='storylines/discovery'
                    element={
                      <DemoRouteGuard>
                        <StorylineDiscovery />
                      </DemoRouteGuard>
                    }
                  />
                  <Route
                    path='storylines/synthesized'
                    element={<SynthesizedView />}
                  />
                  <Route
                    path='storylines/:id/timeline'
                    element={<StoryTimeline />}
                  />
                  <Route path='storylines/:id' element={<StorylineDetail />} />
                  <Route path='articles' element={<Articles />} />
                  <Route
                    path='articles/deduplication'
                    element={
                      <DemoRouteGuard>
                        <ArticleDeduplicationManager />
                      </DemoRouteGuard>
                    }
                  />
                  <Route path='articles/:id' element={<ArticleDetail />} />
                  <Route path='briefings' element={<Briefings />} />
                  <Route
                    path='report'
                    element={<Navigate to='../briefings' replace />}
                  />
                  <Route
                    path='rss_feeds'
                    element={
                      <DemoRouteGuard>
                        <RSSFeeds />
                      </DemoRouteGuard>
                    }
                  />
                  <Route path='topics' element={<Topics />} />
                  <Route
                    path='watchlist'
                    element={
                      <DemoRouteGuard>
                        <Watchlist />
                      </DemoRouteGuard>
                    }
                  />
                  <Route path='events' element={<Events />} />
                  <Route path='investigate' element={<InvestigatePage />} />
                  <Route
                    path='investigate/events/:id'
                    element={<EventDetailPage />}
                  />
                  <Route
                    path='investigate/entities'
                    element={<EntitiesListPage />}
                  />
                  <Route
                    path='investigate/entities/:id'
                    element={<EntityDetailPage />}
                  />
                  <Route
                    path='investigate/entities/:entityId/dossier'
                    element={<EntityDossierPage />}
                  />
                  <Route path='investigate/search' element={<SearchPage />} />
                  <Route
                    path='investigate/documents'
                    element={<ProcessedDocumentsPage />}
                  />
                  <Route
                    path='investigate/documents/:documentId'
                    element={<ProcessedDocumentDetailPage />}
                  />
                  <Route
                    path='investigate/narrative-threads'
                    element={<NarrativeThreadsPage />}
                  />
                  <Route
                    path='monitor'
                    element={
                      <DemoRouteGuard>
                        <MonitorPage />
                      </DemoRouteGuard>
                    }
                  />
                  <Route
                    path='monitor/sql-explorer'
                    element={
                      <DemoRouteGuard>
                        <SqlExplorerPage />
                      </DemoRouteGuard>
                    }
                  />
                  <Route
                    path='audit-checklist'
                    element={
                      <DemoRouteGuard>
                        <AuditChecklistPage />
                      </DemoRouteGuard>
                    }
                  />
                  <Route
                    path='analyze'
                    element={
                      <DemoRouteGuard>
                        <AnalyzePage />
                      </DemoRouteGuard>
                    }
                  />
                  <Route
                    path='analysis'
                    element={
                      <DemoRouteGuard>
                        <FinancialAnalysis />
                      </DemoRouteGuard>
                    }
                  />
                  <Route
                    path='analysis/:taskId'
                    element={
                      <DemoRouteGuard>
                        <FinancialAnalysisResult />
                      </DemoRouteGuard>
                    }
                  />
                  <Route
                    path='trace/:taskId'
                    element={
                      <DemoRouteGuard>
                        <TaskTraceViewer />
                      </DemoRouteGuard>
                    }
                  />
                  <Route
                    path='commodity'
                    element={<Navigate to='commodity/gold' replace />}
                  />
                  <Route
                    path='commodity/:commodity'
                    element={
                      <DemoRouteGuard>
                        <CommodityDashboard />
                      </DemoRouteGuard>
                    }
                  />
                </Route>
                <Route
                  path='*'
                  element={<Navigate to={defaultDomainPath} replace />}
                />
              </Routes>
            </div>
            </Router>
          </PublicDemoProvider>
        </DomainProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
