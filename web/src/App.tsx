/**
 * News Intelligence — Intelligence Dashboard (rebuild).
 * React + Vite + MUI. Layout: Hero status bar + sidebar nav (Discover, Investigate, Monitor, Analyze).
 * See docs/WEB_PRODUCT_DISPLAY_PLAN.md.
 */
import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import './App.css';

import { DomainProvider } from './contexts/DomainContext';
import { getAPIConnectionManager } from './services/apiConnectionManager';
import loggingService from './services/loggingService';
import errorHandler from './services/errorHandler';
import ErrorBoundary from './components/ErrorBoundary/ErrorBoundary';
import './utils/debugHelper';
import './utils/featureTestHelper';

import MainLayout from './layout/MainLayout';
import Dashboard from './pages/Dashboard/Dashboard';
import DiscoverPage from './pages/Discover/DiscoverPage';
import ContextDetailPage from './pages/Discover/ContextDetailPage';
import InvestigatePage from './pages/Investigate/InvestigatePage';
import EventDetailPage from './pages/Investigate/EventDetailPage';
import EntityDetailPage from './pages/Investigate/EntityDetailPage';
import EntitiesListPage from './pages/Investigate/EntitiesListPage';
import SearchPage from './pages/Investigate/SearchPage';
import ProcessedDocumentsPage from './pages/Investigate/ProcessedDocumentsPage';
import NarrativeThreadsPage from './pages/Investigate/NarrativeThreadsPage';
import MonitorPage from './pages/Monitor/MonitorPage';
import AnalyzePage from './pages/Analyze/AnalyzePage';
import CommodityDashboard from './pages/Finance/CommodityDashboard';
import FinancialAnalysis from './pages/Finance/FinancialAnalysis';
import FinancialAnalysisResult from './pages/Finance/FinancialAnalysisResult';
import Storylines from './pages/Storylines/Storylines';
import StorylineDetail from './pages/Storylines/StorylineDetail';
import Briefings from './pages/Briefings/Briefings';
import ReportPage from './pages/Report/ReportPage';

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
  useEffect(() => {
    errorHandler.initialize();
    loggingService.info('News Intelligence (Dashboard) initialized', {
      version: '6.0',
      environment: import.meta.env.MODE || 'development',
    });
    const connectionManager = getAPIConnectionManager();
    connectionManager.testConnection().then((connected) => {
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
          <Router>
            <div className="App">
              <Routes>
                <Route path="/" element={<Navigate to="/politics/dashboard" replace />} />
                <Route path="/:domain" element={<MainLayout />}>
                  <Route index element={<Navigate to="dashboard" replace />} />
                  <Route path="dashboard" element={<Dashboard />} />
                  <Route path="discover" element={<DiscoverPage />} />
                  <Route path="discover/contexts/:id" element={<ContextDetailPage />} />
                  <Route path="storylines" element={<Storylines />} />
                  <Route path="storylines/:id" element={<StorylineDetail />} />
                  <Route path="briefings" element={<Briefings />} />
                  <Route path="report" element={<ReportPage />} />
                  <Route path="investigate" element={<InvestigatePage />} />
                  <Route path="investigate/events/:id" element={<EventDetailPage />} />
                  <Route path="investigate/entities" element={<EntitiesListPage />} />
                  <Route path="investigate/entities/:id" element={<EntityDetailPage />} />
                  <Route path="investigate/search" element={<SearchPage />} />
                  <Route path="investigate/documents" element={<ProcessedDocumentsPage />} />
                  <Route path="investigate/narrative-threads" element={<NarrativeThreadsPage />} />
                  <Route path="monitor" element={<MonitorPage />} />
                  <Route path="analyze" element={<AnalyzePage />} />
                  <Route path="analysis" element={<FinancialAnalysis />} />
                  <Route path="analysis/:taskId" element={<FinancialAnalysisResult />} />
                  <Route path="commodity" element={<Navigate to="commodity/gold" replace />} />
                  <Route path="commodity/:commodity" element={<CommodityDashboard />} />
                </Route>
                <Route path="*" element={<Navigate to="/politics/dashboard" replace />} />
              </Routes>
            </div>
          </Router>
        </DomainProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
