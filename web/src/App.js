import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { Box } from '@mui/material';

// Layout Components
import Layout from './components/Layout/Layout';

// Pages
import EnhancedDashboard from './pages/Dashboard/EnhancedDashboard';
import EnhancedArticles from './pages/Articles/EnhancedArticles';
import UnifiedStoryDossiers from './pages/StoryDossiers/UnifiedStoryDossiers';
import UnifiedLivingStoryNarrator from './pages/LivingStoryNarrator/UnifiedLivingStoryNarrator';
import UnifiedEnhancedArticleViewer from './pages/EnhancedArticleViewer/UnifiedEnhancedArticleViewer';

// Context
import { NewsSystemProvider } from './contexts/NewsSystemContext';

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
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <NewsSystemProvider>
        <Router>
          <Box sx={{ display: 'flex', minHeight: '100vh' }}>
            <Layout>
              <Routes>
                <Route path="/" element={<EnhancedDashboard />} />
                <Route path="/dashboard" element={<EnhancedDashboard />} />
                <Route path="/articles" element={<EnhancedArticles />} />
                <Route path="/story-dossiers" element={<UnifiedStoryDossiers />} />
                <Route path="/living-narrator" element={<UnifiedLivingStoryNarrator />} />
                <Route path="/article-viewer" element={<UnifiedEnhancedArticleViewer />} />
              </Routes>
            </Layout>
          </Box>
        </Router>
      </NewsSystemProvider>
    </ThemeProvider>
  );
}

export default App;
