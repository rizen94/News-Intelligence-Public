import React, { useState, useEffect } from 'react';
import './Dashboard.css';
import { apiService } from '../../services/apiService';

interface DashboardData {
  articles: any[];
  storylines: any[];
  rssFeeds: any[];
  systemHealth: any;
  totalArticles: number;
  totalStorylines: number;
  totalRssFeeds: number;
}

const Dashboard: React.FC = () => {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async() => {
    try {
      setLoading(true);
      setError(null);

      const [articlesRes, storylinesRes, rssFeedsRes, healthRes] =
        await Promise.all([
          apiService.getArticles({ limit: 10 }),
          apiService.getStorylines({ limit: 10 }),
          apiService.getRSSFeeds({ limit: 10 }),
          apiService.getHealth(),
        ]);

      setData({
        articles: articlesRes.data?.articles || [],
        storylines: storylinesRes.data?.storylines || [],
        rssFeeds: rssFeedsRes.data?.feeds || [],
        systemHealth: healthRes,
        totalArticles: articlesRes.data?.total || 0,
        totalStorylines: storylinesRes.data?.total || 0,
        totalRssFeeds: rssFeedsRes.data?.total || 0,
      });
    } catch (err) {
      setError('Failed to load dashboard data');
      console.error('Dashboard error:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className='loading'>Loading dashboard...</div>;
  }

  if (error) {
    return <div className='error'>{error}</div>;
  }

  return (
    <div className='dashboard'>
      <div className='dashboard-header'>
        <h1>Dashboard</h1>
        <button className='button' onClick={fetchDashboardData}>
          Refresh Data
        </button>
      </div>

      <div className='dashboard-grid'>
        <div className='dashboard-card'>
          <div className='card-header'>
            <h3 className='card-title'>System Health</h3>
          </div>
          <div className='health-status'>
            <div
              className={`status-indicator ${
                data?.systemHealth?.success ? 'healthy' : 'unhealthy'
              }`}
            >
              <span className='status-dot'></span>
              <span>
                {data?.systemHealth?.success
                  ? 'System Healthy'
                  : 'System Issues'}
              </span>
            </div>
          </div>
        </div>

        <div className='dashboard-card'>
          <div className='card-header'>
            <h3 className='card-title'>Articles</h3>
          </div>
          <div className='stat-number'>{data?.totalArticles || 0}</div>
          <p>Total articles processed</p>
        </div>

        <div className='dashboard-card'>
          <div className='card-header'>
            <h3 className='card-title'>Storylines</h3>
          </div>
          <div className='stat-number'>{data?.totalStorylines || 0}</div>
          <p>Active storylines</p>
        </div>

        <div className='dashboard-card'>
          <div className='card-header'>
            <h3 className='card-title'>RSS Feeds</h3>
          </div>
          <div className='stat-number'>{data?.totalRssFeeds || 0}</div>
          <p>Configured feeds</p>
        </div>
      </div>

      <div className='dashboard-content'>
        <div className='dashboard-card'>
          <div className='card-header'>
            <h3 className='card-title'>Recent Articles</h3>
          </div>
          <div className='articles-list'>
            {data?.articles?.slice(0, 5).map((article: any) => (
              <div key={article.id} className='article-item'>
                <h4>{article.title}</h4>
                <p className='article-meta'>
                  {article.source} •{' '}
                  {new Date(article.published_at).toLocaleDateString()}
                </p>
              </div>
            ))}
          </div>
        </div>

        <div className='dashboard-card'>
          <div className='card-header'>
            <h3 className='card-title'>Active Storylines</h3>
          </div>
          <div className='storylines-list'>
            {data?.storylines?.slice(0, 5).map((storyline: any) => (
              <div key={storyline.id} className='storyline-item'>
                <h4>{storyline.title}</h4>
                <p className='storyline-meta'>
                  {storyline.article_count} articles
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
