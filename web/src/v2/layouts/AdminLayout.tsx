/**
 * v2 Admin layout — utilitarian ops shell (not broadsheet).
 */
import React from 'react';
import { Link, NavLink, Outlet } from 'react-router-dom';
import '../styles/broadsheet.css';
import { getDefaultDomainKey } from '../../utils/domainHelper';

const NAV = [
  { to: '/v2/admin', label: 'Overview', end: true },
  { to: '/v2/admin/monitor', label: 'Monitor' },
  { to: '/v2/admin/work', label: 'Work executed' },
  { to: '/v2/admin/sql', label: 'SQL' },
  { to: '/v2/admin/audit', label: 'Audit' },
];

export default function AdminLayout() {
  const classic = `/${getDefaultDomainKey()}/monitor`;

  return (
    <div className='v2-admin'>
      <header className='v2-admin-nav'>
        <strong style={{ marginRight: '0.5rem' }}>NI Admin</strong>
        {NAV.map(item => (
          <NavLink key={item.to} to={item.to} end={item.end}>
            {({ isActive }) => (
              <span aria-current={isActive ? 'page' : undefined}>{item.label}</span>
            )}
          </NavLink>
        ))}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.75rem' }}>
          <div className='v2-switcher' aria-label='User Admin switcher'>
            <Link to='/v2'>User</Link>
            <span className='is-active'>Admin</span>
          </div>
          <Link to={classic} style={{ fontSize: '0.8rem' }}>
            Classic app
          </Link>
        </div>
      </header>
      <main className='v2-admin-main'>
        <Outlet />
      </main>
    </div>
  );
}
