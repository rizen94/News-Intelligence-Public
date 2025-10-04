import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import './App.css';

// Import pages
import Dashboard from './pages/Dashboard/EnhancedDashboard';
import Articles from './pages/Articles/EnhancedArticles';
import Storylines from './pages/Storylines/EnhancedStorylines';
import RSSFeeds from './pages/RSSFeeds/EnhancedRSSFeeds';
import Monitoring from './pages/Monitoring/EnhancedMonitoring';
import Intelligence from './pages/Intelligence/IntelligenceHub';
import Settings from './pages/Settings/Settings';

// Import components
import Navigation from './components/Navigation/Navigation';
import Header from './components/Header/Header';
import Footer from './components/Footer/Footer';

function App() {
  return (
    <Router>
      <div className="App">
        <Header />
        <div className="app-container">
          <Navigation />
          <main className="main-content">
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/articles" element={<Articles />} />
              <Route path="/storylines" element={<Storylines />} />
              <Route path="/rss-feeds" element={<RSSFeeds />} />
              <Route path="/monitoring" element={<Monitoring />} />
              <Route path="/intelligence" element={<Intelligence />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </main>
        </div>
        <Footer />
      </div>
    </Router>
  );
}

export default App;
