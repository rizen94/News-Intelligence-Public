import React from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from 'react-router-dom';
import './App.css';

// Import domain-agnostic pages
import Monitoring from './pages/Monitoring/EnhancedMonitoring';
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

function App() {
  return (
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

                {/* Domain-specific routes */}
                <Route path='/:domain/*' element={<DomainLayout />} />
              </Routes>
            </main>
          </div>
          <Footer />
        </div>
      </Router>
    </DomainProvider>
  );
}

export default App;
