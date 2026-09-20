import React from 'react';
import { Link } from 'react-router-dom';

export default function FinanceHomePage() {
  return (
    <div>
      <section className='finance-hero'>
        <h1>Finance</h1>
        <p>
          Market-health trackers, commodity and macro series, and financial reporting —
          separate from the News reader so long-term trends can grow without bleeding into
          broadsheet home.
        </p>
      </section>
      <div className='finance-card-grid'>
        <Link className='finance-link-card' to='/finance/trackers'>
          <h2>Trackers</h2>
          <p>USD purchasing power and credit spreads — first-class market-health gauges.</p>
        </Link>
        <Link className='finance-link-card' to='/finance/markets'>
          <h2>Markets</h2>
          <p>Commodities and core FRED macro series already wired in the finance domain.</p>
        </Link>
        <Link className='finance-link-card' to='/finance/reporting'>
          <h2>Reporting</h2>
          <p>Analysis, evidence, and task traces — narrative/audit, not News home rails.</p>
        </Link>
      </div>
      <p className='finance-page-lede' style={{ marginTop: '1.75rem' }}>
        Future rails (equities, VIX, full FX, yield curve) stay here under Finance — not under
        News <code>/v2</code>. Classic <code>/finance/commodity/…</code> routes remain available
        for side-by-side review.
      </p>
    </div>
  );
}
