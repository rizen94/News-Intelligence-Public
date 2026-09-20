/**
 * Top-level Finance product layout — parallel to classic `/:domain` and News `/v2`.
 * Forces finance domain for API calls; leaves Admin / classic routes alone.
 */
import React, { useEffect } from 'react';
import { NavLink, Outlet, Link } from 'react-router-dom';
import { useDomain } from '../../contexts/DomainContext';
import { getDefaultDomainKey } from '../../utils/domainHelper';
import '../styles/finance.css';

const NAV = [
  {
    id: 'trackers',
    label: 'Trackers',
    items: [
      { to: '/finance/trackers', end: true, label: 'Overview' },
      { to: '/finance/trackers/usd-purchasing-power', label: 'USD purchasing power' },
      { to: '/finance/trackers/credit-spreads', label: 'Credit spreads' },
    ],
  },
  {
    id: 'markets',
    label: 'Markets',
    items: [
      { to: '/finance/markets', end: true, label: 'Overview' },
      { to: '/finance/markets/commodity/gold', label: 'Commodities' },
      { to: '/finance/markets/macro', label: 'FRED macro' },
    ],
  },
  {
    id: 'reporting',
    label: 'Reporting',
    items: [
      { to: '/finance/reporting', end: true, label: 'Overview' },
      { to: '/finance/reporting/analysis', label: 'Analysis' },
      { to: '/finance/reporting/evidence', label: 'Evidence' },
      { to: '/finance/reporting/traces', label: 'Traces' },
    ],
  },
];

export default function FinanceLayout() {
  const { setDomain } = useDomain();
  const newsHome = `/${getDefaultDomainKey()}/dashboard`;

  useEffect(() => {
    setDomain('finance');
  }, [setDomain]);

  return (
    <div className='finance-app'>
      <header className='finance-header'>
        <Link to='/finance' className='finance-brand'>
          News Intelligence · <span>Finance</span>
        </Link>
        <nav className='finance-cross-links' aria-label='Product cross links'>
          <Link to={newsHome}>News (classic)</Link>
          <Link to='/v2'>News (/v2)</Link>
          <Link to='/finance'>Finance home</Link>
          <Link to='/finance/commodity/gold'>Classic commodity</Link>
        </nav>
      </header>
      <div className='finance-shell'>
        <aside className='finance-nav' aria-label='Finance navigation'>
          {NAV.map(section => (
            <div key={section.id} className='finance-nav-section'>
              <div className='finance-nav-label'>{section.label}</div>
              {section.items.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) => (isActive ? 'active' : undefined)}
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
        </aside>
        <main className='finance-main'>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
