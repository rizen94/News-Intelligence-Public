import React, { useState, useEffect } from 'react';
import './Storylines.css';

interface Storyline {
  id: number;
  title: string;
  description: string;
  article_count: number;
  created_at: string;
}

const Storylines: React.FC = () => {
  const [storylines, setStorylines] = useState<Storyline[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStorylines();
  }, []);

  const fetchStorylines = async() => {
    try {
      setLoading(true);
      const response = await fetch('http://localhost:8000/api/storylines/');
      const data = await response.json();

      if (data.success) {
        setStorylines(data.data || []);
      } else {
        setError('Failed to load storylines');
      }
    } catch (err) {
      setError('Failed to load storylines');
      console.error('Storylines error:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading storylines...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="storylines">
      <div className="storylines-header">
        <h1>Storylines</h1>
        <button className="button" onClick={fetchStorylines}>
          Refresh
        </button>
      </div>

      <div className="storylines-stats">
        <div className="stat-card">
          <h3>Total Storylines</h3>
          <div className="stat-number">{storylines.length}</div>
        </div>
      </div>

      <div className="storylines-list">
        {storylines.map((storyline) => (
          <div key={storyline.id} className="storyline-card">
            <div className="storyline-header">
              <h3 className="storyline-title">{storyline.title}</h3>
              <div className="storyline-meta">
                <span className="storyline-count">{storyline.article_count} articles</span>
                <span className="storyline-date">
                  {new Date(storyline.created_at).toLocaleDateString()}
                </span>
              </div>
            </div>
            <div className="storyline-description">
              <p>{storyline.description}</p>
            </div>
            <div className="storyline-actions">
              <button className="button">View Details</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Storylines;
