/**
 * v2 Admin SQL explorer — adapts legacy SqlExplorerPage patterns.
 */
import React, { useCallback, useEffect, useState } from 'react';
import apiService from '../../../services/apiService';

const DEFAULT_SQL = `SELECT phase_name, COUNT(*) AS runs,
  SUM(CASE WHEN success THEN 1 ELSE 0 END) AS ok
FROM automation_run_history
WHERE finished_at >= NOW() AT TIME ZONE 'UTC' - INTERVAL '4 days'
GROUP BY phase_name
ORDER BY runs DESC
LIMIT 50;`;

export default function AdminSqlPage() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [sql, setSql] = useState(DEFAULT_SQL);
  const [columns, setColumns] = useState<string[]>([]);
  const [rows, setRows] = useState<unknown[][]>([]);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    apiService
      .getSqlExplorerEnabled()
      .then(res => setEnabled(!!res.enabled))
      .catch(() => setEnabled(false));
  }, []);

  const run = useCallback(async () => {
    setRunning(true);
    setError(null);
    try {
      const res = (await apiService.postSqlExplorerQuery(sql, 500)) as {
        success?: boolean;
        columns?: string[];
        rows?: unknown[][];
        detail?: string;
        error?: string;
      };
      if (res.success === false || res.error) {
        setError(res.error || res.detail || 'Query failed');
        setColumns([]);
        setRows([]);
      } else {
        setColumns(res.columns || []);
        setRows(res.rows || []);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Query failed');
    } finally {
      setRunning(false);
    }
  }, [sql]);

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>SQL explorer</h1>
      <p className='v2-admin-muted'>
        Requires <code>NEWS_INTEL_SQL_EXPLORER=true</code> on the API. Read-only
        SELECT / EXPLAIN.
      </p>
      {enabled === false ? (
        <p className='v2-admin-error'>SQL explorer is disabled on this API.</p>
      ) : null}
      <div className='v2-admin-panel'>
        <textarea
          value={sql}
          onChange={e => setSql(e.target.value)}
          rows={10}
          style={{ width: '100%', fontFamily: 'monospace', fontSize: '0.8rem' }}
          disabled={enabled === false}
        />
        <button type='button' onClick={run} disabled={running || enabled === false}>
          {running ? 'Running…' : 'Run'}
        </button>
        {error ? <p className='v2-admin-error'>{error}</p> : null}
      </div>
      {columns.length > 0 ? (
        <div className='v2-admin-panel' style={{ overflow: 'auto' }}>
          <table className='v2-admin-table'>
            <thead>
              <tr>
                {columns.map(c => (
                  <th key={c}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  {(r as unknown[]).map((cell, j) => (
                    <td key={j}>{String(cell ?? '')}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
