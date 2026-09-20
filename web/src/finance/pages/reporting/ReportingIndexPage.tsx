import React from 'react';
import { Link } from 'react-router-dom';

export default function ReportingIndexPage() {
  return (
    <div>
      <h1 className='finance-page-title'>Financial reporting</h1>
      <p className='finance-page-lede'>
        Analysis results, evidence, and task traces live here — not on the News{' '}
        <code>/v2</code> broadsheet home. Expand later without mixing into News IA.
      </p>
      <div className='finance-card-grid'>
        <Link className='finance-link-card' to='/finance/reporting/analysis'>
          <h2>Analysis</h2>
          <p>Orchestrator research tasks and saved finance research topics.</p>
        </Link>
        <Link className='finance-link-card' to='/finance/reporting/evidence'>
          <h2>Evidence</h2>
          <p>Evidence index from FRED, EDGAR, and analysis provenance.</p>
        </Link>
        <Link className='finance-link-card' to='/finance/reporting/traces'>
          <h2>Traces</h2>
          <p>Span-level task traces for completed analysis runs.</p>
        </Link>
      </div>
    </div>
  );
}
