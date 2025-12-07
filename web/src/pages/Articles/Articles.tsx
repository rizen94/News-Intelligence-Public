import React, { useState, useEffect } from 'react';
import './Articles.css';
import { apiService } from '../../services/apiService';

interface Article {
  id: number;
  title: string;
  content: string;
  source: string;
  published_at: string;
  url: string;
  summary?: string;
}

const Articles: React.FC = () => {
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchArticles();
  }, []);

  const fetchArticles = async() => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiService.getArticles({ limit: 20 });

      if (response.success) {
        setArticles(response.data?.articles || []);
      } else {
        setError('Failed to load articles');
      }
    } catch (err) {
      setError('Failed to load articles');
      console.error('Articles error:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className='loading'>Loading articles...</div>;
  }

  if (error) {
    return <div className='error'>{error}</div>;
  }

  return (
    <div className='articles'>
      <div className='articles-header'>
        <h1>Articles</h1>
        <button className='button' onClick={fetchArticles}>
          Refresh
        </button>
      </div>

      <div className='articles-stats'>
        <div className='stat-card'>
          <h3>Total Articles</h3>
          <div className='stat-number'>{articles.length}</div>
        </div>
      </div>

      <div className='articles-list'>
        {articles.map(article => (
          <div key={article.id} className='article-card'>
            <div className='article-header'>
              <h3 className='article-title'>{article.title}</h3>
              <div className='article-meta'>
                <span className='article-source'>{article.source}</span>
                <span className='article-date'>
                  {new Date(article.published_at).toLocaleDateString()}
                </span>
              </div>
            </div>
            <div className='article-content'>
              <p>{article.summary || article.content.substring(0, 200)}...</p>
            </div>
            <div className='article-actions'>
              <a
                href={article.url}
                target='_blank'
                rel='noopener noreferrer'
                className='button'
              >
                Read Full Article
              </a>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Articles;
