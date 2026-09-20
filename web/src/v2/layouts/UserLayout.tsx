/**
 * Fix NavLink active styling — use className callback.
 */
import React from 'react';
import { Link, NavLink, Outlet } from 'react-router-dom';
import '../styles/broadsheet.css';
import { DomainFilter, useV2Domain, withDomainQuery } from '../hooks/useV2Domain';
import { getDefaultDomainKey } from '../../utils/domainHelper';

const NAV = [
  { to: '/v2', label: 'Home', end: true },
  { to: '/v2/news', label: 'News' },
  { to: '/v2/current', label: 'Current' },
  { to: '/v2/one-offs', label: 'One-offs' },
  { to: '/v2/admin', label: 'Admin' },
];

export default function UserLayout() {
  const domain = useV2Domain();
  const classic = `/${getDefaultDomainKey()}/dashboard`;

  return (
    <div className='v2-user'>
      <header className='v2-masthead'>
        <div className='v2-masthead-inner'>
          <Link to={withDomainQuery('/v2', domain)} className='v2-brand'>
            News Intelligence
          </Link>
          <nav aria-label='Primary'>
            <ul className='v2-nav-primaries'>
              {NAV.map(item => (
                <li key={item.to}>
                  <NavLink
                    to={withDomainQuery(item.to, domain)}
                    end={item.end}
                    style={({ isActive }) => ({
                      textDecoration: 'none',
                      color: isActive ? 'var(--v2-ink)' : undefined,
                      borderBottomColor: isActive
                        ? 'var(--v2-accent)'
                        : undefined,
                    })}
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
          <div className='v2-chrome-actions'>
            <DomainFilter />
            <div className='v2-switcher' aria-label='User Admin switcher'>
              <span className='is-active'>User</span>
              <Link to={withDomainQuery('/v2/admin', domain)}>Admin</Link>
            </div>
            <Link className='v2-classic-link' to={classic}>
              Classic app
            </Link>
          </div>
        </div>
      </header>
      <main className='v2-page'>
        <Outlet />
      </main>
    </div>
  );
}
