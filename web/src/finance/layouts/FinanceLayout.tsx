/**
 * Finance product layout — denser content pane + shared AppShell chrome.
 */
import React, { useEffect } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useDomain } from '../../contexts/DomainContext';
import AppShell from '../../shell/AppShell';
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

  const sidebar = (
    <>
      {NAV.map(section => (
        <div key={section.id} className='ni-sidebar-section'>
          <div className='ni-sidebar-label'>{section.label}</div>
          {section.items.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? 'is-active' : undefined)}
            >
              {item.label}
            </NavLink>
          ))}
        </div>
      ))}
    </>
  );

  return (
    <AppShell
      root='finance'
      subtitle='Finance'
      brandTo='/finance'
      sidebar={sidebar}
      sidebarLabel='Finance navigation'
      className='finance-app'
    >
      <Outlet />
    </AppShell>
  );
}
