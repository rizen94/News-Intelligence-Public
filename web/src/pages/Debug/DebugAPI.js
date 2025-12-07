import React, { useEffect, useState } from 'react';
import { api } from '../../services/apiService';

const DebugAPI = () => {
  const [articles, setArticles] = useState([]);
  const [storylines, setStorylines] = useState([]);

  useEffect(() => {
    const load = async() => {
      try {
        const ar = await api.get('/api/v4/news-aggregation/articles/recent', {
          params: { limit: 2 },
        });
        setArticles(ar.data?.data?.articles || ar.data?.data || []);
      } catch (e) {}
      try {
        const sr = await api.get('/api/v4/storyline-management/storylines', {
          params: { limit: 10 },
        });
        setStorylines(sr.data?.data?.storylines || sr.data?.data || []);
      } catch (e) {}
    };
    load();
  }, []);

  return (
    <div>
      <h3>Debug API</h3>
      <h4>Articles</h4>
      <pre>{JSON.stringify(articles, null, 2)}</pre>
      <h4>Storylines</h4>
      <pre>{JSON.stringify(storylines, null, 2)}</pre>
    </div>
  );
};

export default DebugAPI;
