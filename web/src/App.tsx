import React from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from 'react-router-dom';
import './App.css';

// Import pages
import Dashboard from './pages/Dashboard/EnhancedDashboard';
import Articles from './pages/Articles/EnhancedArticles';
import ArticleDeduplicationManager from './pages/Articles/ArticleDeduplicationManager';
import Storylines from './pages/Storylines/EnhancedStorylines';
import StorylineDetail from './pages/Storylines/StorylineDetail';
import ArticleDetail from './pages/Articles/ArticleDetail';
import RSSFeeds from './pages/RSSFeeds/EnhancedRSSFeeds';
import RSSDuplicateManager from './pages/RSSFeeds/RSSDuplicateManager';
import Monitoring from './pages/Monitoring/EnhancedMonitoring';
import Intelligence from './pages/Intelligence/IntelligenceHub';
import Topics from './pages/Topics/Topics';
import TopicArticles from './pages/Topics/TopicArticles';
import TopicManagement from './pages/Topics/TopicManagement';
import Settings from './pages/Settings/Settings';

// Import components
import Navigation from './components/Navigation/Navigation';
import Header from './components/Header/Header';
import Footer from './components/Footer/Footer';
import StorylineManagementTest from './components/StorylineManagementTest';

function App() {
  return (
    <Router>
      <div className='App'>
        <Header />
        <div className='app-container'>
          <Navigation />
          <main className='main-content'>
            <Routes>
              <Route path='/' element={<Navigate to='/dashboard' replace />} />
              <Route path='/dashboard' element={<Dashboard />} />
              <Route path='/articles' element={<Articles />} />
              <Route
                path='/articles/duplicates'
                element={<ArticleDeduplicationManager />}
              />
              <Route path='/storylines' element={<Storylines />} />
              <Route path='/storylines/:id' element={<StorylineDetail />} />
              <Route path='/articles/:id' element={<ArticleDetail />} />
              <Route path='/rss-feeds' element={<RSSFeeds />} />
              <Route
                path='/rss-feeds/duplicates'
                element={<RSSDuplicateManager />}
              />
              <Route path='/monitoring' element={<Monitoring />} />
              <Route path='/intelligence' element={<Intelligence />} />

              <Route path='/topics' element={<Topics />} />
              <Route path='/topics/manage' element={<Navigate to='/topics' replace />} />
              <Route path='/topics/:topicName' element={<TopicArticles />} />
              <Route path='/settings' element={<Settings />} />
              <Route
                path='/test-storyline-management'
                element={<StorylineManagementTest />}
              />
            </Routes>
          </main>
        </div>
        <Footer />
      </div>
    </Router>
  );
}

export default App;
