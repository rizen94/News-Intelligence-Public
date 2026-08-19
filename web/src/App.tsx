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
 * Layout: Hero status bar + sidebar IA (Overview, Corpus, Stories, Signals, Investigate, Arcs, Outputs, Finance, Operations).
 * Public demo: `PublicDemoProvider` + `DemoRouteGuard` hide watchlist, ops, and
 * other write-heavy routes — see `AppNav` filter and guarded routes below.
 */
import React, { Suspense, useEffect } from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';
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

const PageFallback = () => (
  <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
    <CircularProgress size={32} />
  </Box>
);

const Dashboard = React.lazy(() => import('./pages/Dashboard/Dashboard'));
const DailyPage = React.lazy(() => import('./pages/Daily/DailyPage'));
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
const SpineBrowserPage = React.lazy(() => import('./pages/Investigate/SpineBrowserPage'));
const HypothesesPage = React.lazy(() => import('./pages/Investigate/HypothesesPage'));
const EntityDossierPage = React.lazy(() => import('./pages/Investigate/EntityDossierPage'));
const ArcCatalogPage = React.lazy(() => import('./pages/Arcs/ArcCatalogPage'));
const ArcChroniclePage = React.lazy(() => import('./pages/Arcs/ArcChroniclePage'));
const ArcSpinePage = React.lazy(() => import('./pages/Arcs/ArcSpinePage'));
const ArcHeatmapPage = React.lazy(() => import('./pages/Arcs/ArcHeatmapPage'));
const ArcWeeklyBriefsPage = React.lazy(() => import('./pages/Arcs/ArcWeeklyBriefsPage'));
const RollingArcsPage = React.lazy(() => import('./pages/Arcs/RollingArcsPage'));
const ResearchSubjectPage = React.lazy(() => import('./pages/Research/ResearchSubjectPage'));
const KnowledgeProfilePage = React.lazy(() => import('./pages/Research/KnowledgeProfilePage'));
const MatterDocketPage = React.lazy(() => import('./pages/Legal/MatterDocketPage'));
const SignalsReviewPage = React.lazy(() => import('./pages/Finance/SignalsReviewPage'));
const InvestigationOpsPage = React.lazy(() => import('./pages/Operations/InvestigationOpsPage'));
const MonitorPage = React.lazy(() => import('./pages/Monitor/MonitorPage'));
const SqlExplorerPage = React.lazy(() => import('./pages/Monitor/SqlExplorerPage'));
const MLProcessing = React.lazy(() => import('./pages/MLProcessing/MLProcessing'));
const AuditChecklistPage = React.lazy(() => import('./pages/Audit/AuditChecklistPage'));
const CommodityDashboard = React.lazy(() => import('./pages/Finance/CommodityDashboard'));
const CreditSpreadDashboard = React.lazy(
  () => import('./pages/Finance/CreditSpreadDashboard')
);
const UsdPurchasingPowerTracker = React.lazy(
  () => import('./pages/Finance/UsdPurchasingPowerTracker')
);
const FinancialAnalysis = React.lazy(() => import('./pages/Finance/FinancialAnalysis'));
const FinancialAnalysisResult = React.lazy(() => import('./pages/Finance/FinancialAnalysisResult'));
const TaskTraceViewer = React.lazy(() => import('./pages/Finance/TaskTraceViewer'));
const CongressTradingDashboard = React.lazy(
  () => import('./pages/Politics/CongressTradingDashboard')
);
const Storylines = React.lazy(() => import('./pages/Storylines/Storylines'));
const StorylineDetail = React.lazy(() => import('./pages/Storylines/StorylineDetail'));
const StorylineReviewQueue = React.lazy(() => import('./pages/Storylines/StorylineReviewQueue'));
const SynthesizedView = React.lazy(() => import('./pages/Storylines/SynthesizedView'));
const LEGACY_DESK_UI =
  String(import.meta.env.VITE_LEGACY_DESK_UI ?? '0').toLowerCase() === '1' ||
  String(import.meta.env.VITE_LEGACY_DESK_UI ?? '').toLowerCase() === 'true';
const StoryTimeline = React.lazy(() => import('./pages/StoryTimeline/StoryTimeline'));
const Articles = React.lazy(() => import('./pages/Articles/Articles'));
const ArticleDetail = React.lazy(() => import('./pages/Articles/ArticleDetail'));
const ArticleDeduplicationManager = React.lazy(() => import('./pages/Articles/ArticleDeduplicationManager'));
const RSSFeeds = React.lazy(() => import('./pages/RSSFeeds/RSSFeeds'));
const Topics = React.lazy(() => import('./pages/Topics/Topics'));
const Watchlist = React.lazy(() => import('./pages/Watchlist/Watchlist'));
const Events = React.lazy(() => import('./pages/Events/Events'));
const ResearchModalPage = React.lazy(() => import('./pages/Editorial/ResearchModalPage'));
const NarrativeModalPage = React.lazy(() => import('./pages/Editorial/NarrativeModalPage'));
const ReductionModalPage = React.lazy(() => import('./pages/Editorial/ReductionModalPage'));
const EditorHomePage = React.lazy(() => import('./pages/Editorial/EditorHomePage'));
const PackageDetailPage = React.lazy(() => import('./pages/Editorial/PackageDetailPage'));
const NewsStoryPage = React.lazy(() => import('./pages/Editorial/NewsStoryPage'));

function FinanceTracePlaceholder() {
  return (
    <Box sx={{ p: 3 }}>
      <Typography variant='h6' gutterBottom>
        Task trace
      </Typography>
      <Typography color='text.secondary'>
        Open a completed analysis task to view its trace at{' '}
        <code>/trace/:taskId</code>.
      </Typography>
    </Box>
  );
}

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
  const defaultDomainPath = `/${getDefaultDomainKey()}/daily`;
  useEffect(() => {
    // Clear one-shot stale-chunk reload guard after a successful boot
    try {
      sessionStorage.removeItem('ni_spa_chunk_reload');
    } catch {
      /* ignore */
    }
    errorHandler.initialize();
    loggingService.info('News Intelligence (Dashboard) initialized', {
      version: '12.0.0',
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
                <Route path='/:domain' element={<MainLayout />}>
                  <Route index element={<Navigate to='daily' replace />} />
                  <Route path='daily' element={<DailyPage />} />
                  <Route path='dashboard' element={<Dashboard />} />
                  <Route path='discover' element={<DiscoverPage />} />
                  <Route
                    path='discover/contexts/:id'
                    element={<ContextDetailPage />}
                  />
                  <Route path='storylines' element={<Storylines />} />
                  <Route path='episodes' element={<Storylines />} />
                  <Route
                    path='storylines/review-queue'
                    element={
                      <DemoRouteGuard>
                        <StorylineReviewQueue />
                      </DemoRouteGuard>
                    }
                  />
                  <Route
                    path='storylines/discovery'
                    element={<Navigate to='../' relative='path' replace />}
                  />
                  {LEGACY_DESK_UI ? (
                    <Route
                      path='storylines/:id/synthesized'
                      element={<SynthesizedView />}
                    />
                  ) : (
                    <Route
                      path='storylines/:id/synthesized'
                      element={<Navigate to='../' relative='path' replace />}
                    />
                  )}
                  <Route
                    path='storylines/:id/timeline'
                    element={<StoryTimeline />}
                  />
                  <Route path='storylines/:id' element={<StorylineDetail />} />
                  <Route path='episodes/:id' element={<StorylineDetail />} />
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
                  <Route
                    path='briefings'
                    element={<Navigate to='../daily' relative='path' replace />}
                  />
                  <Route
                    path='report'
                    element={<Navigate to='../daily' relative='path' replace />}
                  />
                  <Route path='arcs' element={<ArcCatalogPage />} />
                  <Route path='arcs/rolling' element={<RollingArcsPage />} />
                  <Route path='arcs/reports' element={<ArcWeeklyBriefsPage />} />
                  <Route path='arcs/:arcId/chronicle' element={<ArcChroniclePage />} />
                  <Route path='arcs/:arcId/spine' element={<ArcSpinePage />} />
                  <Route path='arcs/:arcId/heatmap' element={<ArcHeatmapPage />} />
                  <Route path='research/subjects' element={<ResearchSubjectPage />} />
                  <Route
                    path='research/profiles/:profileId'
                    element={<KnowledgeProfilePage />}
                  />
                  <Route
                    path='research/entities/:entityId/profile'
                    element={<KnowledgeProfilePage />}
                  />
                  <Route path='research' element={<ResearchModalPage />} />
                  <Route path='narrative' element={<NarrativeModalPage />} />
                  <Route
                    path='reduction'
                    element={
                      <DemoRouteGuard>
                        <ReductionModalPage />
                      </DemoRouteGuard>
                    }
                  />
                  <Route path='editor' element={<EditorHomePage />} />
                  <Route path='editor/packages/:packageId' element={<PackageDetailPage />} />
                  <Route path='editor/stories/:storyId' element={<NewsStoryPage />} />
                  <Route
                    path='dockets/:storylineId'
                    element={<MatterDocketPage />}
                  />
                  <Route path='signals/review' element={<SignalsReviewPage />} />
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
                    path='investigate/spine-browser'
                    element={<SpineBrowserPage />}
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
                    path='operations/investigation-ops'
                    element={
                      <DemoRouteGuard>
                        <InvestigationOpsPage />
                      </DemoRouteGuard>
                    }
                  />
                  <Route
                    path='operations/nri-ops'
                    element={
                      <DemoRouteGuard>
                        <InvestigationOpsPage />
                      </DemoRouteGuard>
                    }
                  />
                  <Route
                    path='operations/llm-activity'
                    element={
                      <DemoRouteGuard>
                        <MLProcessing />
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
                    path='trace'
                    element={
                      <DemoRouteGuard>
                        <FinanceTracePlaceholder />
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
                  <Route
                    path='credit-spread'
                    element={
                      <DemoRouteGuard>
                        <CreditSpreadDashboard />
                      </DemoRouteGuard>
                    }
                  />
                  <Route
                    path='usd-purchasing-power-tracker'
                    element={
                      <DemoRouteGuard>
                        <UsdPurchasingPowerTracker />
                      </DemoRouteGuard>
                    }
                  />
                  <Route
                    path='congress-trading'
                    element={
                      <DemoRouteGuard>
                        <CongressTradingDashboard />
                      </DemoRouteGuard>
                    }
                  />
                  <Route
                    path='*'
                    element={<Navigate to={defaultDomainPath} replace />}
                  />
                </Route>
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
