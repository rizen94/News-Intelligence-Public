import React, { useEffect } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from 'react-router-dom';
import './App.css';

// Import domain-agnostic pages
import Monitoring from './pages/Monitoring/Monitoring';
import Settings from './pages/Settings/Settings';

// Import domain layout
import DomainLayout from './components/shared/DomainLayout/DomainLayout';
import LegacyRedirect from './components/shared/LegacyRedirect/LegacyRedirect';

// Import components
import Navigation from './components/Navigation/Navigation';
import Header from './components/Header/Header';
import Footer from './components/Footer/Footer';
import StorylineManagementTest from './components/StorylineManagementTest';
import { DomainProvider } from './contexts/DomainContext';
import { getAPIConnectionManager } from './services/apiConnectionManager';
import { frontendHealthService } from './services/frontendHealthService';
import loggingService from './services/loggingService';
import errorHandler from './services/errorHandler';
import ErrorBoundary from './components/ErrorBoundary/ErrorBoundary';
// Import debug helpers (auto-initialized in development)
import './utils/debugHelper';
import './utils/featureTestHelper';

function App() {
  // Initialize logging and error handling on app start
  useEffect(() => {
    // Initialize error handler (already auto-initialized, but ensure it's ready)
    errorHandler.initialize();

    // Log app initialization
    loggingService.info('News Intelligence System initialized', {
      version: '4.0',
      environment: process.env.NODE_ENV,
      userAgent: navigator.userAgent,
      url: window.location.href,
    });

    // Initialize API connection manager
    const connectionManager = getAPIConnectionManager();

    // Test connection on mount
    connectionManager.testConnection().then((connected) => {
      if (connected) {
        loggingService.info('API connection established successfully');
      } else {
        loggingService.warn('API connection check failed - will retry automatically');
      }
    });

    // Initialize frontend health monitoring (optional - disabled to prevent false disconnects)
    // frontendHealthService.startMonitoring(30000); // Check every 30 seconds
    // loggingService.info('Frontend health monitoring started');

    // Report health to API periodically (optional)
    // const healthReportInterval = setInterval(() => {
    //   frontendHealthService.reportHealthToAPI();
    // }, 60000); // Report every minute

    // Cleanup on unmount
    return () => {
      connectionManager.cleanup();
      // frontendHealthService.stopMonitoring();
      // clearInterval(healthReportInterval);
    };
  }, []);

  return (
    <ErrorBoundary>
      <DomainProvider>
        <Router>
          <div className='App'>
            <Header />
            <div className='app-container'>
              <Navigation />
              <main className='main-content'>
                <Routes>
                  {/* Root redirect to default domain */}
                  <Route path='/' element={<Navigate to='/politics/dashboard' replace />} />

                  {/* Domain-agnostic routes (shared across all domains) */}
                  <Route path='/monitoring' element={<Monitoring />} />
                  <Route path='/settings' element={<Settings />} />
                  <Route
                    path='/test-storyline-management'
                    element={<StorylineManagementTest />}
                  />

                  {/* Legacy route redirects (backward compatibility) */}
                  <Route path='/dashboard' element={<LegacyRedirect to='/dashboard' />} />
                  <Route path='/articles' element={<LegacyRedirect to='/articles' />} />
                  <Route
                    path='/articles/duplicates'
                    element={<LegacyRedirect to='/articles/duplicates' />}
                  />
                  <Route
                    path='/articles/:id'
                    element={<LegacyRedirect to='/articles/:id' preserveParams />}
                  />
                  <Route path='/storylines' element={<LegacyRedirect to='/storylines' />} />
                  <Route
                    path='/storylines/discover'
                    element={<LegacyRedirect to='/storylines/discover' />}
                  />
                  <Route
                    path='/storylines/consolidation'
                    element={<LegacyRedirect to='/storylines/consolidation' />}
                  />
                  <Route
                    path='/storylines/:id'
                    element={<LegacyRedirect to='/storylines/:id' preserveParams />}
                  />
                  <Route path='/topics' element={<LegacyRedirect to='/topics' />} />
                  <Route
                    path='/topics/:topicName'
                    element={<LegacyRedirect to='/topics/:topicName' preserveParams />}
                  />
                  <Route path='/rss-feeds' element={<LegacyRedirect to='/rss-feeds' />} />
                  <Route
                    path='/rss-feeds/duplicates'
                    element={<LegacyRedirect to='/rss-feeds/duplicates' />}
                  />
                  <Route path='/intelligence' element={<LegacyRedirect to='/intelligence' />} />
                  <Route
                    path='/intelligence/analysis'
                    element={<LegacyRedirect to='/intelligence/analysis' />}
                  />
                  <Route
                    path='/intelligence/rag'
                    element={<LegacyRedirect to='/intelligence/rag' />}
                  />

                  {/* Domain-specific routes */}
                  <Route path='/:domain/*' element={<DomainLayout />} />
                </Routes>
              </main>
            </div>
            <Footer />
          </div>
        </Router>
      </DomainProvider>
    </ErrorBoundary>
  );
}

export default App;
