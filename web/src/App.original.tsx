/**
 * Main App Component v3.0 for News Intelligence System
 * Refactored to use new architecture with TypeScript and error boundaries
 */

import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { Box } from '@mui/material';

// Layout Components
import NewspaperLayoutV3 from './components/Layout/NewspaperLayoutV3';

// Pages
import MorningBriefing from './pages/MorningBriefing/MorningBriefing';
import Articles from './pages/Articles/Articles';
import ArticlesV3 from './pages/Articles/ArticlesV3';
import ArticleDetail from './pages/Articles/ArticleDetail';
import Storylines from './pages/Storylines/Storylines';
import StorylineDetail from './pages/Storylines/StorylineDetail';
import StorylineTimeline from './pages/Timeline/StorylineTimeline';
import Discover from './pages/Discover/Discover';

// New v3.0 AI Pages
import AIAnalysisDashboard from './pages/AIAnalysis/AIAnalysisDashboard';
import TrendsAnalysis from './pages/Trends/TrendsAnalysis';
import ClusteringAnalysis from './pages/Clusters/ClusteringAnalysis';
import SystemMonitoring from './pages/Monitoring/SystemMonitoring';

// Context and Providers
import { NewsSystemProvider } from './contexts/NewsSystemContext';
import { NotificationProvider } from './components/Notifications/NotificationSystem';
import { ErrorBoundaryProvider } from './components/ErrorBoundary/ErrorBoundaryProvider';

// Create newspaper-style theme
const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1a1a1a', // Classic newspaper black
    },
    secondary: {
      main: '#d32f2f', // Classic newspaper red
    },
    background: {
      default: '#fafafa',
      paper: '#ffffff',
    },
    text: {
      primary: '#1a1a1a',
      secondary: '#666666',
    },
  },
  typography: {
    fontFamily: '"Georgia", "Times New Roman", serif',
    h1: {
      fontFamily: '"Times New Roman", serif',
      fontWeight: 700,
      fontSize: '2.5rem',
      lineHeight: 1.2,
    },
    h2: {
      fontFamily: '"Times New Roman", serif',
      fontWeight: 600,
      fontSize: '2rem',
      lineHeight: 1.3,
    },
    h3: {
      fontFamily: '"Times New Roman", serif',
      fontWeight: 600,
      fontSize: '1.5rem',
      lineHeight: 1.4,
    },
    h4: {
      fontFamily: '"Times New Roman", serif',
      fontWeight: 500,
      fontSize: '1.25rem',
      lineHeight: 1.4,
    },
    h5: {
      fontFamily: '"Times New Roman", serif',
      fontWeight: 500,
      fontSize: '1.1rem',
      lineHeight: 1.5,
    },
    h6: {
      fontFamily: '"Times New Roman", serif',
      fontWeight: 500,
      fontSize: '1rem',
      lineHeight: 1.5,
    },
    body1: {
      fontFamily: '"Georgia", serif',
      fontSize: '1rem',
      lineHeight: 1.6,
    },
    body2: {
      fontFamily: '"Georgia", serif',
      fontSize: '0.875rem',
      lineHeight: 1.6,
    },
    button: {
      fontFamily: '"Arial", sans-serif',
      fontWeight: 500,
      textTransform: 'none',
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
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 6,
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 16,
        },
      },
    },
  },
});

const App: React.FC = () => {
  return (
    <ErrorBoundaryProvider>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Router>
          <NewsSystemProvider>
            <NotificationProvider>
              <Box sx={{ minHeight: '100vh', backgroundColor: 'background.default' }}>
                <NewspaperLayoutV3>
                  <Routes>
                    {/* Main Navigation Routes */}
                    <Route path="/" element={<MorningBriefing />} />
                    <Route path="/morning-briefing" element={<MorningBriefing />} />
                    
                    {/* Articles Routes */}
                    <Route path="/articles" element={<Articles />} />
                    <Route path="/articles/v3" element={<ArticlesV3 />} />
                    <Route path="/articles/:id" element={<ArticleDetail />} />
                    
                    {/* Storylines Routes */}
                    <Route path="/storylines" element={<Storylines />} />
                    <Route path="/storylines/:id" element={<StorylineDetail />} />
                    <Route path="/storylines/:id/timeline" element={<StorylineTimeline />} />
                    
                    {/* Discover Route */}
                    <Route path="/discover" element={<Discover />} />
                    
                    {/* New v3.0 AI Routes */}
                    <Route path="/ai-analysis" element={<AIAnalysisDashboard />} />
                    <Route path="/trends" element={<TrendsAnalysis />} />
                    <Route path="/clusters" element={<ClusteringAnalysis />} />
                    <Route path="/monitoring" element={<SystemMonitoring />} />
                    
                    {/* Fallback Route */}
                    <Route path="*" element={<MorningBriefing />} />
                  </Routes>
                </NewspaperLayoutV3>
              </Box>
            </NotificationProvider>
          </NewsSystemProvider>
        </Router>
      </ThemeProvider>
    </ErrorBoundaryProvider>
  );
};

export default App;
