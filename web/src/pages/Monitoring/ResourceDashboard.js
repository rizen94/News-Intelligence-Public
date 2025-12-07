import React, { useEffect, useState } from 'react';
import { api } from '../../services/apiService';

const ResourceDashboard = () => {
  const [data, setData] = useState([]);
  const [timeRange, setTimeRange] = useState(24);
  const [error, setError] = useState(null);

  useEffect(() => {
    const load = async() => {
      try {
        const resp = await api.get('/api/v4/system-monitoring/metrics', {
          params: { hours: timeRange, limit: 100 },
        });
        const payload = resp.data;
        if (payload.success) setData(payload.data?.metrics || []);
        else setError('Failed to load metrics');
      } catch (e) {
        setError(e.message || 'Failed to load metrics');
      }
    };
    load();
  }, [timeRange]);

  return (
    <div>
      <h2>Resource Dashboard</h2>
      {error && <div style={{ color: 'red' }}>{error}</div>}
      <pre>{JSON.stringify(data.slice(0, 5), null, 2)}</pre>
    </div>
  );
};

export default ResourceDashboard;
