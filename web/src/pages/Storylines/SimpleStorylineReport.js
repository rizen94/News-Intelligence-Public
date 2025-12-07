import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../../services/apiService';

const SimpleStorylineReport = () => {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const load = async() => {
      try {
        const response = await api.get(
          `/api/v4/storyline-management/storylines/${id}`,
        );
        const payload = response.data;
        if (payload.success) setData(payload.data);
        else setError('Failed to load report');
      } catch (e) {
        setError(e.message || 'Failed to load');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  if (loading) return <div>Loading report...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div>
      <h2>Storyline Report</h2>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
};

export default SimpleStorylineReport;
