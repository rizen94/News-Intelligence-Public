/**
 * v2 Admin Monitor — compact adaptation of legacy Monitor APIs.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import apiService from '../../../services/apiService';

export default function AdminMonitorPage() {
  const [overview, setOverview] = useState<Record<string, unknown> | null>(null);
  const [pipeline, setPipeline] = useState<Record<string, unknown> | null>(null);
  const [automation, setAutomation] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [ov, pipe, auto] = await Promise.all([
        apiService.getMonitoringOverview(),
        apiService.getPipelineStatus(),
        apiService.getAutomationStatus(),
      ]);
      setOverview(ov as Record<string, unknown>);
      setPipeline(pipe as Record<string, unknown>);
      setAutomation(auto as Record<string, unknown>);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Monitor load failed';
      setError(msg);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Monitor</h1>
      <p className='v2-admin-muted'>
        Parallel to classic Monitor. Deep dive:{' '}
        <Link to='/v2/admin/work'>Work executed</Link> ·{' '}
        <Link to='/v2/admin/sql'>SQL</Link>
      </p>
      {error ? <p className='v2-admin-error'>{error}</p> : null}

      <div className='v2-admin-panel'>
        <h2>Overview</h2>
        <pre style={{ fontSize: '0.75rem', overflow: 'auto', maxHeight: 280 }}>
          {overview ? JSON.stringify(overview, null, 2).slice(0, 4000) : '…'}
        </pre>
      </div>

      <div className='v2-admin-panel'>
        <h2>Pipeline</h2>
        <pre style={{ fontSize: '0.75rem', overflow: 'auto', maxHeight: 240 }}>
          {pipeline ? JSON.stringify(pipeline, null, 2).slice(0, 3000) : '…'}
        </pre>
      </div>

      <div className='v2-admin-panel'>
        <h2>Automation</h2>
        <pre style={{ fontSize: '0.75rem', overflow: 'auto', maxHeight: 240 }}>
          {automation ? JSON.stringify(automation, null, 2).slice(0, 3000) : '…'}
        </pre>
      </div>
    </div>
  );
}
