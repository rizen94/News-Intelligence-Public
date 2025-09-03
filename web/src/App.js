import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { Box } from '@mui/material';

// Layout Components
import Layout from './components/Layout/Layout';

// Pages
import EnhancedDashboard from './pages/Dashboard/EnhancedDashboard';
import IntelligenceDashboard from './pages/Intelligence/IntelligenceDashboard';
import IntelligenceInsights from './pages/Intelligence/IntelligenceInsights';
import EnhancedArticles from './pages/Articles/EnhancedArticles';
import UnifiedStoryDossiers from './pages/StoryDossiers/UnifiedStoryDossiers';
import UnifiedLivingStoryNarrator from './pages/LivingStoryNarrator/UnifiedLivingStoryNarrator';
import UnifiedEnhancedArticleViewer from './pages/EnhancedArticleViewer/UnifiedEnhancedArticleViewer';
import MLProcessing from './pages/MLProcessing/MLProcessing';
import RSSManagement from './pages/RSSManagement/RSSManagement';
import DeduplicationManagement from './pages/Deduplication/DeduplicationManagement';
import RAGEnhanced from './pages/RAGEnhanced/RAGEnhanced';
import StorylineTracking from './pages/StorylineTracking/StorylineTracking';
import ContentPrioritization from './pages/ContentPrioritization/ContentPrioritization';
import DailyBriefings from './pages/DailyBriefings/DailyBriefings';
import AutomationPipeline from './pages/AutomationPipeline/AutomationPipeline';
import AdvancedMonitoring from './pages/AdvancedMonitoring/AdvancedMonitoring';
import DataManagement from './pages/DataManagement/DataManagement';

// Context
import { NewsSystemProvider } from './contexts/NewsSystemContext';
import { NotificationProvider } from './components/Notifications/NotificationSystem';
import ErrorBoundary from './components/ErrorBoundary/ErrorBoundary';

// Create theme
const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
    background: {
      default: '#f5f5f5',
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    h4: {
      fontWeight: 600,
    },
    h5: {
      fontWeight: 600,
    },
    h6: {
      fontWeight: 600,
    },
  },
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
          borderRadius: 8,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        },
      },
    },
  },
});

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <NotificationProvider>
          <NewsSystemProvider>
            <Router>
              <Box sx={{ display: 'flex', minHeight: '100vh' }}>
                <Layout>
                  <Routes>
                <Route path="/" element={<EnhancedDashboard />} />
                <Route path="/dashboard" element={<EnhancedDashboard />} />
                <Route path="/intelligence" element={<IntelligenceDashboard />} />
                <Route path="/intelligence/insights" element={<IntelligenceInsights />} />
                <Route path="/articles" element={<EnhancedArticles />} />
                <Route path="/story-dossiers" element={<UnifiedStoryDossiers />} />
                <Route path="/ml-processing" element={<MLProcessing />} />
                <Route path="/living-narrator" element={<UnifiedLivingStoryNarrator />} />
                <Route path="/article-viewer" element={<UnifiedEnhancedArticleViewer />} />
                
                {/* Phase 2 Routes - Now Implemented */}
                <Route path="/deduplication" element={<DeduplicationManagement />} />
                <Route path="/rss-management" element={<RSSManagement />} />
                <Route path="/rag-enhanced" element={<RAGEnhanced />} />
                <Route path="/storyline-tracking" element={<StorylineTracking />} />
                
                {/* Phase 2 Routes - Now Implemented */}
                <Route path="/prioritization" element={<ContentPrioritization />} />
                <Route path="/briefings" element={<DailyBriefings />} />
                <Route path="/automation" element={<AutomationPipeline />} />
                
                {/* Phase 3 Routes - Now Implemented */}
                <Route path="/monitoring" element={<AdvancedMonitoring />} />
                <Route path="/data-management" element={<DataManagement />} />
                  </Routes>
                </Layout>
              </Box>
            </Router>
          </NewsSystemProvider>
        </NotificationProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
