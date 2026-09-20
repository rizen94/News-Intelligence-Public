import React from 'react';
import { Link } from 'react-router-dom';

export default function TrackersIndexPage() {
  return (
    <div>
      <h1 className='finance-page-title'>Trackers</h1>
      <p className='finance-page-lede'>
        First-class financial tracking spine for market health and long-term USD / credit stress.
      </p>
      <div className='finance-card-grid'>
        <Link className='finance-link-card' to='/finance/trackers/usd-purchasing-power'>
          <h2>USD purchasing power</h2>
          <p>CPI, core CPI, trade-weighted dollar, gold, and PDOLLAR vs 2020 baseline.</p>
        </Link>
        <Link className='finance-link-card' to='/finance/trackers/credit-spreads'>
          <h2>Credit spreads</h2>
          <p>HY/IG OAS with recession shading, plus HYG−TLT / LQD−TLT ETF yield spreads.</p>
        </Link>
      </div>
    </div>
  );
}
