import React from 'react';
import { Link } from 'react-router-dom';

export default function MarketsIndexPage() {
  return (
    <div>
      <h1 className='finance-page-title'>Markets</h1>
      <p className='finance-page-lede'>
        Commodity dashboards and core FRED macro series. Classic{' '}
        <Link to='/finance/commodity/gold'>/:domain/commodity/…</Link> routes stay intact.
      </p>
      <div className='finance-card-grid'>
        <Link className='finance-link-card' to='/finance/markets/commodity/gold'>
          <h2>Commodities</h2>
          <p>Gold, silver, platinum, oil, and gas — spot, history, and context overlays.</p>
        </Link>
        <Link className='finance-link-card' to='/finance/markets/macro'>
          <h2>FRED macro</h2>
          <p>FEDFUNDS, DGS10, CPIAUCSL, DTWEXBGS, T10YIE, M2SL, UNRATE and related series.</p>
        </Link>
      </div>
    </div>
  );
}
