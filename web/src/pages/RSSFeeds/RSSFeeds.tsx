import React, { useState, useEffect } from 'react';
import './RSSFeeds.css';
import { apiService } from '../../services/apiService';

interface RSSFeed {
  id: number;
  name: string;
  url: string;
  is_active: boolean;
  last_fetch: string;
}

const RSSFeeds: React.FC = () => {
  const [feeds, setFeeds] = useState<RSSFeed[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchFeeds();
  }, []);

  const fetchFeeds = async() => {
    try {
      setLoading(true);
      const response = await apiService.getRSSFeeds();

      if (response.success) {
        const items = (response.data?.feeds || response.data || []).map(
          (f: any) => ({
            id: f.id,
            name: f.feed_name || f.name,
            url: f.feed_url || f.url,
            is_active: !!f.is_active,
            last_fetch: f.last_fetched_at || f.last_fetch || null,
          }),
        );
        setFeeds(items);
      } else {
        setError('Failed to load RSS feeds');
      }
    } catch (err) {
      setError('Failed to load RSS feeds');
      console.error('RSS Feeds error:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className='loading'>Loading RSS feeds...</div>;
  }

  if (error) {
    return <div className='error'>{error}</div>;
  }

  return (
    <div className='rss-feeds'>
      <div className='rss-feeds-header'>
        <h1>RSS Feeds</h1>
        <button className='button' onClick={fetchFeeds}>
          Refresh
        </button>
      </div>

      <div className='rss-feeds-stats'>
        <div className='stat-card'>
          <h3>Total Feeds</h3>
          <div className='stat-number'>{feeds.length}</div>
        </div>
      </div>

      <div className='rss-feeds-list'>
        {feeds.map(feed => (
          <div key={feed.id} className='feed-card'>
            <div className='feed-header'>
              <h3 className='feed-name'>{feed.name}</h3>
              <div
                className={`feed-status ${
                  feed.is_active ? 'active' : 'inactive'
                }`}
              >
                {feed.is_active ? 'Active' : 'Inactive'}
              </div>
            </div>
            <div className='feed-url'>
              <a href={feed.url} target='_blank' rel='noopener noreferrer'>
                {feed.url}
              </a>
            </div>
            <div className='feed-meta'>
              <span>
                Last fetch:{' '}
                {feed.last_fetch
                  ? new Date(feed.last_fetch).toLocaleString()
                  : 'N/A'}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default RSSFeeds;
