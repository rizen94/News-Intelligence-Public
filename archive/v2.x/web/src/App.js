import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { Box } from '@mui/material';

// Layout Components
import NewspaperLayout from './components/Layout/NewspaperLayout';

// New Newspaper-Style Pages
import MorningBriefing from './pages/MorningBriefing/MorningBriefing';
import Articles from './pages/Articles/Articles';
import ArticleDetail from './pages/Articles/ArticleDetail';
import Storylines from './pages/Storylines/Storylines';
import StorylineDetail from './pages/Storylines/StorylineDetail';
import StorylineTimeline from './pages/Timeline/StorylineTimeline';
import Discover from './pages/Discover/Discover';
// import DebugAPI from './pages/Debug/DebugAPI'; // Debug component - not for production

// Context
import { NewsSystemProvider } from './contexts/NewsSystemContext';
import { NotificationProvider } from './components/Notifications/NotificationSystem';
import ErrorBoundary from './components/ErrorBoundary/ErrorBoundary';

// Create newspaper-style theme
const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1a1a1a', // Classic newspaper black
    },
    secondary: {
      main: '#d32f2f', // Newspaper red for accents
    },
    background: {
      default: '#fafafa', // Clean white background
      paper: '#ffffff',
    },
    text: {
      primary: '#1a1a1a',
      secondary: '#666666',
    },
  },
  typography: {
    fontFamily: '"Georgia", "Times New Roman", serif', // Classic newspaper font
    h1: {
      fontFamily: '"Helvetica Neue", "Arial", sans-serif',
      fontWeight: 700,
      fontSize: '2.5rem',
      lineHeight: 1.2,
    },
    h2: {
      fontFamily: '"Helvetica Neue", "Arial", sans-serif',
      fontWeight: 600,
      fontSize: '2rem',
      lineHeight: 1.3,
    },
    h3: {
      fontFamily: '"Helvetica Neue", "Arial", sans-serif',
      fontWeight: 600,
      fontSize: '1.5rem',
      lineHeight: 1.4,
    },
    h4: {
      fontFamily: '"Helvetica Neue", "Arial", sans-serif',
      fontWeight: 600,
      fontSize: '1.25rem',
      lineHeight: 1.4,
    },
    h5: {
      fontFamily: '"Helvetica Neue", "Arial", sans-serif',
      fontWeight: 600,
      fontSize: '1.1rem',
      lineHeight: 1.4,
    },
    h6: {
      fontFamily: '"Helvetica Neue", "Arial", sans-serif',
      fontWeight: 600,
      fontSize: '1rem',
      lineHeight: 1.4,
    },
    body1: {
      fontFamily: '"Georgia", "Times New Roman", serif',
      fontSize: '1rem',
      lineHeight: 1.6,
    },
    body2: {
      fontFamily: '"Georgia", "Times New Roman", serif',
      fontSize: '0.875rem',
      lineHeight: 1.5,
    },
  },
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24)',
          borderRadius: 4,
          border: '1px solid #e0e0e0',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          boxShadow: '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24)',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 500,
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
              <Box sx={{ display: 'flex', minHeight: '100vh', backgroundColor: '#fafafa' }}>
                <NewspaperLayout>
                  <Routes>
                    {/* Main Newspaper Routes */}
                    <Route path="/" element={<MorningBriefing />} />
                    <Route path="/briefing" element={<MorningBriefing />} />
                    
                    {/* Articles */}
                    <Route path="/articles" element={<Articles />} />
                    <Route path="/articles/:id" element={<ArticleDetail />} />
                    
                    {/* Storylines */}
                    <Route path="/storylines" element={<Storylines />} />
                    <Route path="/storylines/:storylineId" element={<StorylineDetail />} />
                    <Route path="/storylines/:storylineId/timeline" element={<StorylineTimeline />} />
                    
                    {/* Debug - Commented out for production */}
                    {/* <Route path="/debug" element={<DebugAPI />} /> */}
                    
                    {/* Discover */}
                    <Route path="/discover" element={<Discover />} />
                  </Routes>
                </NewspaperLayout>
              </Box>
            </Router>
          </NewsSystemProvider>
        </NotificationProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;