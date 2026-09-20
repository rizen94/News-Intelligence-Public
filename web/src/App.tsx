/**
 * News Intelligence — web SPA entry (React + Vite + MUI).
 *
 * Routing:
 * - Legacy (default): `/:domain/*` via MainLayout — unchanged until explicit cutover.
 * - v2 User: `/v2/*` (Modern Broadsheet reader) under `web/src/v2/`.
 * - v2 Admin: `/v2/admin/*` (utilitarian ops) — parallel to classic Operations.
 *
 * Domains come from the API (`/api/system_monitoring/registry_domains`) with a
 * static fallback — see `utils/domainHelper` and AGENTS.md.
 *
 * API calls: `apiConnectionManager` sets base URL and domain for `/api/{domain}/...`
 * and global `/api/...` routes (see docs/WEB_API_CONNECTIONS.md).
 *
 * Layout: Hero status bar + sidebar (Discover, Investigate, Monitor, Analyze).
 * Public demo: `PublicDemoProvider` + `DemoRouteGuard` hide watchlist, ops, and
 * other write-heavy routes — see `AppNav` filter and guarded routes below.
 * Product display notes (incorporation candidate): docs/archive/planning_incubator/WEB_PRODUCT_DISPLAY_PLAN.md
 */
import React, { Suspense, useEffect } from 'react';
import { Box, CircularProgress } from '@mui/material';
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

const FinanceLayout = React.lazy(() => import('./finance/layouts/FinanceLayout'));
const FinanceHomePage = React.lazy(() => import('./finance/pages/FinanceHomePage'));
const TrackersIndexPage = React.lazy(
  () => import('./finance/pages/trackers/TrackersIndexPage')
);
const UsdPurchasingPowerPage = React.lazy(
  () => import('./finance/pages/trackers/UsdPurchasingPowerPage')
);
const CreditSpreadsPage = React.lazy(
  () => import('./finance/pages/trackers/CreditSpreadsPage')
);
const MarketsIndexPage = React.lazy(
  () => import('./finance/pages/markets/MarketsIndexPage')
);
const CommodityMarketsPage = React.lazy(
  () => import('./finance/pages/markets/CommodityMarketsPage')
);
const MacroMarketsPage = React.lazy(
  () => import('./finance/pages/markets/MacroMarketsPage')
);
const ReportingIndexPage = React.lazy(
  () => import('./finance/pages/reporting/ReportingIndexPage')
);
const ReportingAnalysisPage = React.lazy(
  () => import('./finance/pages/reporting/ReportingAnalysisPage')
);
const ReportingAnalysisResultPage = React.lazy(
  () => import('./finance/pages/reporting/ReportingAnalysisResultPage')
);
const ReportingEvidencePage = React.lazy(
  () => import('./finance/pages/reporting/ReportingEvidencePage')
);
const ReportingTracesPage = React.lazy(
  () => import('./finance/pages/reporting/ReportingTracesPage')
);

const PageFallback = () => (
  <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
    <CircularProgress size={32} />
  </Box>
);

/* v2 parallel app — do not replace legacy /:domain routes */
const V2UserLayout = React.lazy(() => import('./v2/layouts/UserLayout'));
const V2AdminLayout = React.lazy(() => import('./v2/layouts/AdminLayout'));
const V2HomePage = React.lazy(() => import('./v2/pages/Home/HomePage'));
const V2NewsPage = React.lazy(() => import('./v2/pages/News/NewsPage'));
const V2CurrentPage = React.lazy(() => import('./v2/pages/Current/CurrentPage'));
const V2OneOffsPage = React.lazy(() => import('./v2/pages/OneOffs/OneOffsPage'));
const V2StorylineReaderPage = React.lazy(
  () => import('./v2/pages/StorylineReader/StorylineReaderPage')
);
const V2EntityDossierPage = React.lazy(
  () => import('./v2/pages/EntityDossier/EntityDossierPage')
);
const V2AdminOverviewPage = React.lazy(
  () => import('./v2/pages/admin/AdminOverviewPage')
);
const V2AdminMonitorPage = React.lazy(
  () => import('./v2/pages/admin/AdminMonitorPage')
);
const V2AdminWorkPage = React.lazy(() => import('./v2/pages/admin/AdminWorkPage'));
const V2AdminSqlPage = React.lazy(() => import('./v2/pages/admin/AdminSqlPage'));
const V2AdminAuditPage = React.lazy(
  () => import('./v2/pages/admin/AdminAuditPage')
);

const Dashboard = React.lazy(() => import('./pages/Dashboard/Dashboard'));
const DiscoverPage = React.lazy(() => import('./pages/Discover/DiscoverPage'));
const ContextDetailPage = React.lazy(() => import('./pages/Discover/ContextDetailPage'));
const InvestigatePage = React.lazy(() => import('./pages/Investigate/InvestigatePage'));
const EventDetailPage = React.lazy(() => import('./pages/Investigate/EventDetailPage'));
const EntityDetailPage = React.lazy(() => import('./pages/Investigate/EntityDetailPage'));
const EntitiesListPage = React.lazy(() => import('./pages/Investigate/EntitiesListPage'));
const SearchPage = React.lazy(() => import('./pages/Investigate/SearchPage'));
const ProcessedDocumentsPage = React.lazy(() => import('./pages/Investigate/ProcessedDocumentsPage'));
const ProcessedDocumentDetailPage = React.lazy(() => import('./pages/Investigate/ProcessedDocumentDetailPage'));
const NarrativeThreadsPage = React.lazy(() => import('./pages/Investigate/NarrativeThreadsPage'));
const EntityResolutionPage = React.lazy(() => import('./pages/Investigate/EntityResolutionPage'));
const HypothesesPage = React.lazy(() => import('./pages/Investigate/HypothesesPage'));
const EntityDossierPage = React.lazy(() => import('./pages/Investigate/EntityDossierPage'));
const MonitorPage = React.lazy(() => import('./pages/Monitor/MonitorPage'));
const SqlExplorerPage = React.lazy(() => import('./pages/Monitor/SqlExplorerPage'));
const AnalyzePage = React.lazy(() => import('./pages/Analyze/AnalyzePage'));
const AuditChecklistPage = React.lazy(() => import('./pages/Audit/AuditChecklistPage'));
const CommodityDashboard = React.lazy(() => import('./pages/Finance/CommodityDashboard'));
const FinancialAnalysis = React.lazy(() => import('./pages/Finance/FinancialAnalysis'));
const FinancialAnalysisResult = React.lazy(() => import('./pages/Finance/FinancialAnalysisResult'));
const TaskTraceViewer = React.lazy(() => import('./pages/Finance/TaskTraceViewer'));
const Storylines = React.lazy(() => import('./pages/Storylines/Storylines'));
const StorylineDetail = React.lazy(() => import('./pages/Storylines/StorylineDetail'));
const StorylineDiscovery = React.lazy(() => import('./pages/Storylines/StorylineDiscovery'));
const StorylineReviewQueue = React.lazy(() => import('./pages/Storylines/StorylineReviewQueue'));
const SynthesizedView = React.lazy(() => import('./pages/Storylines/SynthesizedView'));
const StoryTimeline = React.lazy(() => import('./pages/StoryTimeline/StoryTimeline'));
const Articles = React.lazy(() => import('./pages/Articles/Articles'));
const ArticleDetail = React.lazy(() => import('./pages/Articles/ArticleDetail'));
const ArticleDeduplicationManager = React.lazy(() => import('./pages/Articles/ArticleDeduplicationManager'));
const Briefings = React.lazy(() => import('./pages/Briefings/Briefings'));
const RSSFeeds = React.lazy(() => import('./pages/RSSFeeds/RSSFeeds'));
const Topics = React.lazy(() => import('./pages/Topics/Topics'));
const Watchlist = React.lazy(() => import('./pages/Watchlist/Watchlist'));
const Events = React.lazy(() => import('./pages/Events/Events'));

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
    return () => getAPIConnectionManager().cleanup();
  }, []);

  return (
    <ErrorBoundary>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <DomainProvider>
          <PublicDemoProvider>
            <Router>
              <div className='App'>
                <Suspense fallback={<PageFallback />}>
                <Routes>
                <Route
                  path='/'
                  element={<Navigate to={defaultDomainPath} replace />}
                />
                {/* News /v2 — registered before /:domain so "v2" is not a domain */}
                <Route path='/v2' element={<V2UserLayout />}>
                  <Route index element={<V2HomePage />} />
                  <Route path='news' element={<V2NewsPage />} />
                  <Route path='current' element={<V2CurrentPage />} />
                  <Route path='one-offs' element={<V2OneOffsPage />} />
                  <Route
                    path='storylines/:domain/:id'
                    element={<V2StorylineReaderPage />}
                  />
                  <Route path='entities/:id' element={<V2EntityDossierPage />} />
                </Route>
                {/* Admin — ops only; also aliased at /admin */}
                <Route path='/v2/admin' element={<V2AdminLayout />}>
                  <Route index element={<V2AdminOverviewPage />} />
                  <Route path='monitor' element={<V2AdminMonitorPage />} />
                  <Route path='work' element={<V2AdminWorkPage />} />
                  <Route path='sql' element={<V2AdminSqlPage />} />
                  <Route path='audit' element={<V2AdminAuditPage />} />
                </Route>
                <Route path='/admin' element={<V2AdminLayout />}>
                  <Route index element={<V2AdminOverviewPage />} />
                  <Route path='monitor' element={<V2AdminMonitorPage />} />
                  <Route path='work' element={<V2AdminWorkPage />} />
                  <Route path='sql' element={<V2AdminSqlPage />} />
                  <Route path='audit' element={<V2AdminAuditPage />} />
                </Route>
                {/* Finance product tree */}
                <Route path='/finance' element={<FinanceLayout />}>
                  <Route index element={<FinanceHomePage />} />
                  <Route path='trackers' element={<TrackersIndexPage />} />
                  <Route
                    path='trackers/usd-purchasing-power'
                    element={<UsdPurchasingPowerPage />}
                  />
                  <Route
                    path='trackers/credit-spreads'
                    element={<CreditSpreadsPage />}
                  />
                  <Route path='markets' element={<MarketsIndexPage />} />
                  <Route
                    path='markets/commodity'
                    element={<Navigate to='/finance/markets/commodity/gold' replace />}
                  />
                  <Route
                    path='markets/commodity/:commodity'
                    element={<CommodityMarketsPage />}
                  />
                  <Route path='markets/macro' element={<MacroMarketsPage />} />
                  <Route path='reporting' element={<ReportingIndexPage />} />
                  <Route
                    path='reporting/analysis'
                    element={
                      <DemoRouteGuard>
                        <ReportingAnalysisPage />
                      </DemoRouteGuard>
                    }
                  />
                  <Route
                    path='reporting/analysis/:taskId'
                    element={
                      <DemoRouteGuard>
                        <ReportingAnalysisResultPage />
                      </DemoRouteGuard>
                    }
                  />
                  <Route
                    path='reporting/evidence'
                    element={
                      <DemoRouteGuard>
                        <ReportingEvidencePage />
                      </DemoRouteGuard>
                    }
                  />
                  <Route
                    path='reporting/traces'
                    element={
                      <DemoRouteGuard>
                        <ReportingTracesPage />
                      </DemoRouteGuard>
                    }
                  />
                  <Route
                    path='reporting/traces/:taskId'
                    element={
                      <DemoRouteGuard>
                        <ReportingTracesPage />
                      </DemoRouteGuard>
                    }
                  />
                </Route>
                <Route path='/:domain' element={<MainLayout />}>
                  <Route index element={<Navigate to='dashboard' replace />} />
                  <Route path='dashboard' element={<Dashboard />} />
                  <Route path='discover' element={<DiscoverPage />} />
                  <Route
                    path='discover/contexts/:id'
                    element={<ContextDetailPage />}
                  />
                  <Route path='storylines' element={<Storylines />} />
                  <Route
                    path='storylines/review-queue'
                    element={
                      <DemoRouteGuard>
                        <StorylineReviewQueue />
                      </DemoRouteGuard>
                    }
                  />
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
                    path='storylines/:id/synthesized'
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
                    path='investigate/entity-resolution'
                    element={<EntityResolutionPage />}
                  />
                  <Route
                    path='investigate/hypotheses'
                    element={<HypothesesPage />}
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
                </Suspense>
            </div>
            </Router>
          </PublicDemoProvider>
        </DomainProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
