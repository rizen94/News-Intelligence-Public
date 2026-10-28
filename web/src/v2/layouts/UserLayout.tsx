/**
 * News product layout — broadsheet content pane + shared AppShell chrome.
 */
import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import '../styles/broadsheet.css';
import { DomainFilter, useV2Domain, withDomainQuery } from '../hooks/useV2Domain';
import AppShell from '../../shell/AppShell';
import { newsHomePath } from '../../paths';

const NAV = [
  { to: '/', label: 'Home', end: true },
  { to: '/news', label: 'News' },
  { to: '/current', label: 'Current' },
  { to: '/hubs', label: 'Situations' },
  { to: '/research', label: 'Research' },
  { to: '/one-offs', label: 'One-offs' },
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
      brandTo={newsHomePath(domain)}
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
