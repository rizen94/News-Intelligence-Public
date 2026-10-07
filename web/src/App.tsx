/**
 * News Intelligence — web SPA entry (React + Vite + MUI).
 *
 * Single live surface (v2 architecture; folder name unchanged):
 * - News (default): `/`, `/news`, `/current`, `/hubs`, `/research`, `/one-offs`,
 *   `/storylines/:domain/:id`, `/hubs/:idOrSlug` — broadsheet (`web/src/v2/`)
 * - Finance: `/finance/*` (`web/src/finance/`)
 * - Admin: `/admin/*` — ops (Monitor, Work, SQL, Audit)
 *
 * Public origin: https://news-intelligence-ag.duckdns.org
 * Legacy `/v2/*` and bare `/:domain/*` redirect into this map.
 * Classic UI cold-stored at archive/classic_web_ui/ (not mounted).
 */
import React, { Suspense, useEffect } from 'react';
import { Box, CircularProgress } from '@mui/material';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  useLocation,
  useParams,
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
import LegacyV2Redirect from './components/LegacyV2Redirect';
import { NEWS_HOME } from './paths';
import { isValidDomain, getDefaultDomainKey } from './utils/domainHelper';

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

/* Live News / Admin (implementation under web/src/v2/) */
const V2UserLayout = React.lazy(() => import('./v2/layouts/UserLayout'));
const V2AdminLayout = React.lazy(() => import('./v2/layouts/AdminLayout'));
const V2HomePage = React.lazy(() => import('./v2/pages/Home/HomePage'));
const V2NewsPage = React.lazy(() => import('./v2/pages/News/NewsPage'));
const V2CurrentPage = React.lazy(() => import('./v2/pages/Current/CurrentPage'));
const V2OneOffsPage = React.lazy(() => import('./v2/pages/OneOffs/OneOffsPage'));
const V2ResearchPage = React.lazy(() => import('./v2/pages/Research/ResearchPage'));
const V2StorylineReaderPage = React.lazy(
  () => import('./v2/pages/StorylineReader/StorylineReaderPage')
);
const V2HubPage = React.lazy(() => import('./v2/pages/Hub/HubPage'));
const V2SituationsPage = React.lazy(
  () => import('./v2/pages/Situations/SituationsPage')
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

/** Bare /:domain/* bookmarks → News home with ?domain= */
function LegacyDomainHomeRedirect() {
  const { domain } = useParams<{ domain: string }>();
  const { search, hash } = useLocation();
  const d =
    domain && isValidDomain(domain) ? domain : getDefaultDomainKey();
  const q = new URLSearchParams(search);
  if (!q.get('domain')) q.set('domain', d);
  const qs = q.toString();
  return (
    <Navigate to={`${NEWS_HOME}${qs ? `?${qs}` : ''}${hash}`} replace />
  );
}

function App() {
  useEffect(() => {
    errorHandler.initialize();
    loggingService.info('News Intelligence initialized', {
      version: '10.0',
      environment: import.meta.env.MODE || 'development',
      publicOrigin: 'https://news-intelligence-ag.duckdns.org',
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
                {/* News — primary domain */}
                <Route path='/' element={<V2UserLayout />}>
                  <Route index element={<V2HomePage />} />
                  <Route path='news' element={<V2NewsPage />} />
                  <Route path='current' element={<V2CurrentPage />} />
                  <Route path='one-offs' element={<V2OneOffsPage />} />
                  <Route path='research' element={<V2ResearchPage />} />
                  <Route path='hubs' element={<V2SituationsPage />} />
                  <Route
                    path='storylines/:domain/:id'
                    element={<V2StorylineReaderPage />}
                  />
                  <Route path='hubs/:idOrSlug' element={<V2HubPage />} />
                  <Route path='entities/:id' element={<V2EntityDossierPage />} />
                </Route>
                {/* Admin */}
                <Route path='/admin' element={<V2AdminLayout />}>
                  <Route index element={<V2AdminOverviewPage />} />
                  <Route path='monitor' element={<V2AdminMonitorPage />} />
                  <Route path='work' element={<V2AdminWorkPage />} />
                  <Route path='sql' element={<V2AdminSqlPage />} />
                  <Route path='audit' element={<V2AdminAuditPage />} />
                </Route>
                {/* Legacy /v2 → primary paths */}
                <Route path='/v2/*' element={<LegacyV2Redirect />} />
                <Route path='/v2' element={<LegacyV2Redirect />} />
                {/* Finance */}
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
                  <Route
                    path='credit-spread'
                    element={<Navigate to='/finance/trackers/credit-spreads' replace />}
                  />
                  <Route
                    path='credit-spreads'
                    element={<Navigate to='/finance/trackers/credit-spreads' replace />}
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
                {/* Retired classic paths → News home */}
                <Route path='/classic/*' element={<Navigate to={NEWS_HOME} replace />} />
                <Route path='/classic' element={<Navigate to={NEWS_HOME} replace />} />
                <Route path='/:domain/*' element={<LegacyDomainHomeRedirect />} />
                <Route path='/:domain' element={<LegacyDomainHomeRedirect />} />
                <Route path='*' element={<Navigate to={NEWS_HOME} replace />} />
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
