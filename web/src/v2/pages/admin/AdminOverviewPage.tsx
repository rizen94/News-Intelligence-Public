/**
 * Admin overview — ops entry points only (no user-content destinations).
 */
import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { adminBaseFromPath } from '../../../shell/ProductRootSwitcher';
import { getGrafanaOpsUrl } from '../../../config/grafanaConfig';

export default function AdminOverviewPage() {
  const { pathname } = useLocation();
  const base = adminBaseFromPath(pathname);
  const grafanaUrl = getGrafanaOpsUrl();

  const links = [
    {
      to: `${base}/monitor`,
      title: 'Monitor',
      hint: 'Live Status / Now / Pulse / Actions',
    },
    {
      to: `${base}/work`,
      title: 'Work executed',
      hint: 'Process run summary, backlog, phase failures',
    },
    {
      to: `${base}/sql`,
      title: 'SQL explorer',
      hint: 'Read-only SELECT when enabled on API',
    },
    {
      to: `${base}/audit`,
      title: 'Audit checklist',
      hint: 'Weekly corpus / pipeline checklist',
    },
  ];

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Admin</h1>
      <p className='v2-admin-muted'>
        Operations surface only — Monitor, Work, SQL, Audit, and Grafana. User
        reading destinations (Dashboard, Storylines, Articles, Discover, …) live
        under News.
      </p>
      {links.map(l => (
        <div key={l.to} className='v2-admin-panel'>
          <h2>
            <Link to={l.to}>{l.title}</Link>
          </h2>
          <p className='v2-admin-muted' style={{ margin: 0 }}>
            {l.hint}
          </p>
        </div>
      ))}
      <div className='v2-admin-panel'>
        <h2>Grafana</h2>
        <p className='v2-admin-muted' style={{ margin: 0 }}>
          {grafanaUrl ? (
            <a href={grafanaUrl} target='_blank' rel='noopener noreferrer'>
              Open NI Ops dashboard
            </a>
          ) : (
            <>
              Set <code>VITE_NEWS_INTEL_GRAFANA_URL</code> or{' '}
              <code>localStorage.news_intel_grafana_url</code>.
            </>
          )}
        </p>
      </div>
    </div>
  );
}
