/**
 * v2 Admin overview — entry to monitor / work / sql / audit.
 */
import React from 'react';
import { Link } from 'react-router-dom';

const LINKS = [
  {
    to: '/v2/admin/monitor',
    title: 'Monitor',
    hint: 'Health, pipeline, automation pulse',
  },
  {
    to: '/v2/admin/work',
    title: 'Work executed',
    hint: 'Process run summary, backlog, phase failures',
  },
  {
    to: '/v2/admin/sql',
    title: 'SQL explorer',
    hint: 'Read-only SELECT when enabled on API',
  },
  {
    to: '/v2/admin/audit',
    title: 'Audit checklist',
    hint: 'Weekly corpus / pipeline checklist',
  },
];

export default function AdminOverviewPage() {
  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Admin</h1>
      <p className='v2-admin-muted'>
        Utilitarian ops surface for the v2 app. Legacy Operations under{' '}
        <code>/:domain/monitor</code> remains unchanged.
      </p>
      {LINKS.map(l => (
        <div key={l.to} className='v2-admin-panel'>
          <h2>
            <Link to={l.to}>{l.title}</Link>
          </h2>
          <p className='v2-admin-muted' style={{ margin: 0 }}>
            {l.hint}
          </p>
        </div>
      ))}
    </div>
  );
}
