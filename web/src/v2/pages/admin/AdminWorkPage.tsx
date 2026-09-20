/**
 * Work executed — surfaces process_run_summary, backlog, processing progress
 * that classic Monitor intentionally stripped.
 */
import React, { useCallback, useEffect, useState } from 'react';
import apiService from '../../../services/apiService';

export default function AdminWorkPage() {
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [backlog, setBacklog] = useState<Record<string, unknown> | null>(null);
  const [progress, setProgress] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [sum, back, prog] = await Promise.all([
        apiService.getProcessRunSummary(24),
        apiService.getBacklogStatus(),
        apiService.getProcessingProgress({ includePendingMetrics: true }),
      ]);
      setSummary(sum as Record<string, unknown>);
      setBacklog(back as Record<string, unknown>);
      setProgress(prog as Record<string, unknown>);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Work load failed';
      setError(msg);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const phasesRecent =
    (summary?.phases_run_recently as Array<Record<string, unknown>>) || [];
  const phasesNot =
    (summary?.phases_not_run_recently as Array<Record<string, unknown>>) || [];

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Work executed</h1>
      <p className='v2-admin-muted'>
        Troubleshooting-first view of run history, backlog ETAs, and phase
        failure rates.
      </p>
      {error ? <p className='v2-admin-error'>{error}</p> : null}
      <button type='button' onClick={load} style={{ marginBottom: '1rem' }}>
        Refresh
      </button>

      <div className='v2-admin-panel'>
        <h2>Phases run (24h)</h2>
        {phasesRecent.length === 0 ? (
          <p className='v2-admin-muted'>None or summary unavailable.</p>
        ) : (
          <table className='v2-admin-table'>
            <thead>
              <tr>
                <th>Phase</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {phasesRecent.slice(0, 40).map((p, i) => (
                <tr key={i}>
                  <td>{String(p.phase_name || p.name || JSON.stringify(p))}</td>
                  <td>
                    <code style={{ fontSize: '0.7rem' }}>
                      {JSON.stringify(p).slice(0, 200)}
                    </code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className='v2-admin-panel'>
        <h2>Phases not run recently</h2>
        <ul>
          {phasesNot.slice(0, 30).map((p, i) => (
            <li key={i}>{String(p.phase_name || p.name || JSON.stringify(p))}</li>
          ))}
        </ul>
        {!phasesNot.length ? (
          <p className='v2-admin-muted'>Empty or unavailable.</p>
        ) : null}
      </div>

      <div className='v2-admin-panel'>
        <h2>Backlog</h2>
        <pre style={{ fontSize: '0.75rem', overflow: 'auto', maxHeight: 320 }}>
          {backlog ? JSON.stringify(backlog, null, 2).slice(0, 6000) : '…'}
        </pre>
      </div>

      <div className='v2-admin-panel'>
        <h2>Processing progress + failures</h2>
        <pre style={{ fontSize: '0.75rem', overflow: 'auto', maxHeight: 320 }}>
          {progress ? JSON.stringify(progress, null, 2).slice(0, 6000) : '…'}
        </pre>
      </div>
    </div>
  );
}
