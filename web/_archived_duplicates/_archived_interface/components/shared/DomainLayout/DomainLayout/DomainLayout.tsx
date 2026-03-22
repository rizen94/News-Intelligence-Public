/**
 * Domain Layout Component
 * Wraps domain-specific routes and provides domain context
 */

import React, { useEffect } from 'react';
import { Routes, Route, useParams, Navigate, useNavigate } from 'react-router-dom';
import { useDomain } from '../../../contexts/DomainContext';
import { isValidDomain } from '../../../utils/domainHelper';
import DomainRouteGuard from '../DomainRouteGuard/DomainRouteGuard';
import ErrorBoundary from '../../ErrorBoundary/ErrorBoundary';

// Import pages
import Dashboard from '../../../pages/Dashboard/Dashboard';
import Articles from '../../../pages/Articles/Articles';
import ArticleDeduplicationManager from '../../../pages/Articles/ArticleDeduplicationManager';
import FilteredArticles from '../../../pages/FilteredArticles/FilteredArticles';
import Storylines from '../../../pages/Storylines/Storylines';
import StorylineDetail from '../../../pages/Storylines/StorylineDetail';
import StorylineDiscovery from '../../../pages/Storylines/StorylineDiscovery';
import SynthesizedView from '../../../pages/Storylines/SynthesizedView';
import ArticleDetail from '../../../pages/Articles/ArticleDetail';
import RSSFeeds from '../../../pages/RSSFeeds/RSSFeeds';
import RSSDuplicateManager from '../../../pages/RSSFeeds/RSSDuplicateManager';
import Intelligence from '../../../pages/Intelligence/IntelligenceHub';
import IntelligenceAnalysis from '../../../pages/Intelligence/IntelligenceAnalysis';
import DomainRAG from '../../../pages/Intelligence/DomainRAG';
import EntityProfiles from '../../../pages/Intelligence/EntityProfiles';
import EntityProfileDetail from '../../../pages/Intelligence/EntityProfileDetail';
import ContextBrowser from '../../../pages/Intelligence/ContextBrowser';
import TrackedEvents from '../../../pages/Intelligence/TrackedEvents';
import TrackedEventDetail from '../../../pages/Intelligence/TrackedEventDetail';
import ContextCentricStatus from '../../../pages/Intelligence/ContextCentricStatus';
import EntityManagement from '../../../pages/Intelligence/EntityManagement';
import IntelligenceSearch from '../../../pages/Intelligence/IntelligenceSearch';
import CollectionWatch from '../../../pages/Intelligence/CollectionWatch';
import Topics from '../../../pages/Topics/Topics';
import TopicArticles from '../../../pages/Topics/TopicArticles';
import ConsolidationPanel from '../../../components/Storylines/ConsolidationPanel';

// Restored pages
import MLProcessing from '../../../pages/MLProcessing/MLProcessing';
import StoryControlDashboard from '../../../pages/StoryManagement/StoryControlDashboard';
import StorylineTracking from '../../../pages/StorylineTracking/StorylineTracking';
import Briefings from '../../../pages/Briefings/Briefings';
import StoryTimeline from '../../../pages/StoryTimeline/StoryTimeline';
import Events from '../../../pages/Events/Events';
import WatchlistPage from '../../../pages/Watchlist/Watchlist';

// Finance-specific pages
import MarketResearch from '../../../domains/Finance/MarketResearch/MarketResearch';
import CorporateAnnouncements from '../../../domains/Finance/CorporateAnnouncements/CorporateAnnouncements';
import MarketPatterns from '../../../domains/Finance/MarketPatterns/MarketPatterns';
// Finance Analysis (orchestrator)
import FinancialAnalysis from '../../../pages/Finance/FinancialAnalysis';
import FinancialAnalysisResult from '../../../pages/Finance/FinancialAnalysisResult';
import TaskTraceViewer from '../../../pages/Finance/TaskTraceViewer';
import EvidenceExplorer from '../../../pages/Finance/EvidenceExplorer';
import SourceHealth from '../../../pages/Finance/SourceHealth';
import RefreshSchedule from '../../../pages/Finance/RefreshSchedule';
import FactCheckViewer from '../../../pages/Finance/FactCheckViewer';

const DomainLayout: React.FC = () => {
  const { domain: urlDomain } = useParams<{ domain: string }>();
  const { domain: contextDomain, setDomain } = useDomain();
  const navigate = useNavigate();

  // Validate domain from URL and sync with context
  useEffect(() => {
    if (urlDomain) {
      if (isValidDomain(urlDomain)) {
        // Update context if URL domain is different
        if (urlDomain !== contextDomain) {
          setDomain(urlDomain as 'politics' | 'finance' | 'science-tech');
        }
      } else {
        // Invalid domain, redirect to default
        navigate('/politics/dashboard', { replace: true });
      }
    }
  }, [urlDomain, contextDomain, setDomain, navigate]);

  // If no domain in URL or invalid, redirect
  if (!urlDomain || !isValidDomain(urlDomain)) {
    return <Navigate to='/politics/dashboard' replace />;
  }

  return (
    <DomainRouteGuard>
      <Routes>
        {/* ============================================
            CORE FEATURES - AVAILABLE IN ALL DOMAINS
            Paths are relative to parent /:domain/* (splat = segment after domain)
            ============================================ */}

        {/* Dashboard - Domain-specific overview */}
        <Route path="dashboard" element={<Dashboard />} />

        {/* Articles - Core feature with AI summarization and enhancement */}
        <Route path="articles" element={<Articles />} />
        <Route path="articles/:id" element={<ArticleDetail />} />
        <Route path="articles/duplicates" element={<ArticleDeduplicationManager />} />
        <Route path="articles/filtered" element={<FilteredArticles />} />

        {/* Storylines - Core feature with RAG-enhanced discovery and AI analysis */}
        <Route path="storylines" element={<Storylines />} />
        <Route path="storylines/discover" element={<StorylineDiscovery />} />
        <Route path="storylines/consolidation" element={<ConsolidationPanel />} />
        <Route path="storylines/:id" element={
          <ErrorBoundary fallback={
            <div style={{ padding: 24, background: '#fff3e0', border: '2px solid #ff9800', borderRadius: 8 }}>
              <h2 style={{ color: '#e65100', marginTop: 0 }}>Storyline failed to load</h2>
              <p style={{ color: '#333' }}>Check the browser console (F12) for the error details.</p>
            </div>
          }>
            <StorylineDetail />
          </ErrorBoundary>
        } />
        <Route path="storylines/:id/synthesis" element={<SynthesizedView />} />
        <Route path="storylines/:id/timeline" element={<StoryTimeline />} />

        {/* Topics - Core feature with topic clustering and management */}
        <Route path="topics" element={<Topics />} />
        <Route path="topics/:topicName" element={<TopicArticles />} />

        {/* RSS Feeds - Core feature for feed management */}
        <Route path="rss-feeds" element={<RSSFeeds />} />
        <Route path="rss-feeds/duplicates" element={<RSSDuplicateManager />} />

        {/* Intelligence Hub - Core feature with AI-powered insights */}
        <Route path="intelligence" element={<Intelligence />} />
        <Route path="intelligence/analysis" element={<IntelligenceAnalysis />} />
        <Route path="intelligence/rag" element={<DomainRAG />} />
        <Route path="intelligence/tracking" element={<StorylineTracking />} />
        <Route path="intelligence/briefings" element={<Briefings />} />
        <Route path="intelligence/events" element={<Events />} />
        <Route path="intelligence/watchlist" element={<WatchlistPage />} />
        {/* Context-centric (Phase 4) */}
        <Route path="intelligence/entity-profiles" element={<EntityProfiles />} />
        <Route path="intelligence/entity-profiles/:id" element={<EntityProfileDetail />} />
        <Route path="intelligence/contexts" element={<ContextBrowser />} />
        <Route path="intelligence/tracked-events" element={<TrackedEvents />} />
        <Route path="intelligence/tracked-events/:id" element={<TrackedEventDetail />} />
        <Route path="intelligence/context-centric-status" element={<ContextCentricStatus />} />
        <Route path="intelligence/entity-management" element={<EntityManagement />} />
        <Route path="intelligence/search" element={<IntelligenceSearch />} />
        <Route path="intelligence/collection-watch" element={<CollectionWatch />} />

        {/* System Operations */}
        <Route path="ml-processing" element={<MLProcessing />} />
        <Route path="story-management" element={<StoryControlDashboard />} />

        {/* ============================================
            DOMAIN-SPECIFIC FEATURES (ADDITIONS ONLY)
            ============================================ */}

        {/* Finance-specific routes - Additional features for Finance domain */}
        {urlDomain === 'finance' && (
          <>
            <Route path="market-research" element={<MarketResearch />} />
            <Route path="corporate-announcements" element={<CorporateAnnouncements />} />
            <Route path="market-patterns" element={<MarketPatterns />} />
            {/* Financial Analysis (orchestrator) */}
            <Route path="analysis" element={<FinancialAnalysis />} />
            <Route path="analysis/:taskId" element={<FinancialAnalysisResult />} />
            <Route path="trace/:taskId" element={<TaskTraceViewer />} />
            <Route path="evidence" element={<EvidenceExplorer />} />
            <Route path="sources" element={<SourceHealth />} />
            <Route path="schedule" element={<RefreshSchedule />} />
            <Route path="fact-check" element={<FactCheckViewer />} />
          </>
        )}

        {/* Default redirect to dashboard */}
        <Route path="" element={<Navigate to={`/${urlDomain}/dashboard`} replace />} />
        <Route path="*" element={<Navigate to={`/${urlDomain}/dashboard`} replace />} />
      </Routes>
    </DomainRouteGuard>
  );
};

export default DomainLayout;
