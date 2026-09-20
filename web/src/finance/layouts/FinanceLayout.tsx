/**
 * Finance product layout — denser content + shared product-root chrome.
 */
import React, { useEffect } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useDomain } from '../../contexts/DomainContext';
import { ProductRootSwitcher } from '../../shell/ProductRootSwitcher';
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

  useEffect(() => {
    setDomain('finance');
  }, [setDomain]);

  return (
    <div className='finance-app'>
      <header className='finance-header'>
        <ProductRootSwitcher subtitle='Finance' brandTo='/finance' />
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
