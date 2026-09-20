/**
 * News product layout — broadsheet content pane + shared AppShell chrome.
 */
import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import '../styles/broadsheet.css';
import { DomainFilter, useV2Domain, withDomainQuery } from '../hooks/useV2Domain';
import AppShell from '../../shell/AppShell';

const NAV = [
  { to: '/v2', label: 'Home', end: true },
  { to: '/v2/news', label: 'News' },
  { to: '/v2/current', label: 'Current' },
  { to: '/v2/one-offs', label: 'One-offs' },
];

export default function UserLayout() {
  const domain = useV2Domain();

  const sidebar = (
    <div className='ni-sidebar-section'>
      <div className='ni-sidebar-label'>Sections</div>
      {NAV.map(item => (
        <NavLink
          key={item.to}
          to={withDomainQuery(item.to, domain)}
          end={item.end}
          className={({ isActive }) => (isActive ? 'is-active' : undefined)}
        >
          {item.label}
        </NavLink>
      ))}
    </div>
  );

  return (
    <AppShell
      root='news'
      brandTo='/v2'
      headerActions={<DomainFilter />}
      sidebar={sidebar}
      sidebarLabel='News sections'
      className='v2-user'
    >
      <div className='ni-news-measure'>
        <Outlet />
      </div>
    </AppShell>
  );
}
