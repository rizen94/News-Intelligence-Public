/**
 * Domain Layout Component
 * Wraps domain-specific routes and provides domain context
 */

import React, { useEffect } from 'react';
import { Routes, Route, useParams, Navigate, useNavigate } from 'react-router-dom';
import { useDomain } from '../../../contexts/DomainContext';
import { isValidDomain } from '../../../utils/domainHelper';
import DomainRouteGuard from '../DomainRouteGuard/DomainRouteGuard';

// Import pages
import Dashboard from '../../../pages/Dashboard/Dashboard';
import Articles from '../../../pages/Articles/Articles';
import ArticleDeduplicationManager from '../../../pages/Articles/ArticleDeduplicationManager';
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
import Topics from '../../../pages/Topics/Topics';
import TopicArticles from '../../../pages/Topics/TopicArticles';
import ConsolidationPanel from '../../../components/Storylines/ConsolidationPanel';

// Finance-specific pages
import MarketResearch from '../../../domains/Finance/MarketResearch/MarketResearch';
import CorporateAnnouncements from '../../../domains/Finance/CorporateAnnouncements/CorporateAnnouncements';
import MarketPatterns from '../../../domains/Finance/MarketPatterns/MarketPatterns';

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
            These routes are the same for Politics, Finance, and Science & Tech
            ============================================ */}

        {/* Dashboard - Domain-specific overview */}
        <Route path="dashboard" element={<Dashboard />} />

        {/* Articles - Core feature with AI summarization and enhancement */}
        <Route path="articles" element={<Articles />} />
        <Route path="articles/:id" element={<ArticleDetail />} />
        <Route path="articles/duplicates" element={<ArticleDeduplicationManager />} />

        {/* Storylines - Core feature with RAG-enhanced discovery and AI analysis */}
        <Route path="storylines" element={<Storylines />} />
        <Route path="storylines/discover" element={<StorylineDiscovery />} />
        <Route path="storylines/consolidation" element={<ConsolidationPanel />} />
        <Route path="storylines/:id" element={<StorylineDetail />} />
        <Route path="storylines/:id/synthesis" element={<SynthesizedView />} />

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

        {/* ============================================
            DOMAIN-SPECIFIC FEATURES (ADDITIONS ONLY)
            These are additions to core features, not replacements
            ============================================ */}

        {/* Finance-specific routes - Additional features for Finance domain */}
        {urlDomain === 'finance' && (
          <>
            <Route path="market-research" element={<MarketResearch />} />
            <Route path="corporate-announcements" element={<CorporateAnnouncements />} />
            <Route path="market-patterns" element={<MarketPatterns />} />
          </>
        )}

        {/* Future: Add other domain-specific routes here */}
        {/* Example: Science & Tech specific features */}
        {/* {urlDomain === 'science-tech' && (
          <>
            <Route path="research-papers" element={<ResearchPapers />} />
            <Route path="tech-trends" element={<TechTrends />} />
          </>
        )} */}

        {/* Default redirect to dashboard */}
        <Route path="" element={<Navigate to={`/${urlDomain}/dashboard`} replace />} />
        <Route path="*" element={<Navigate to={`/${urlDomain}/dashboard`} replace />} />
      </Routes>
    </DomainRouteGuard>
  );
};

export default DomainLayout;
