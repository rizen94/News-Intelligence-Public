/**
 * News product layout — broadsheet content + shared product-root chrome.
 */
import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import '../styles/broadsheet.css';
import { DomainFilter, useV2Domain, withDomainQuery } from '../hooks/useV2Domain';
import { ProductRootSwitcher } from '../../shell/ProductRootSwitcher';

const NAV = [
  { to: '/v2', label: 'Home', end: true },
  { to: '/v2/news', label: 'News' },
  { to: '/v2/current', label: 'Current' },
  { to: '/v2/one-offs', label: 'One-offs' },
];

export default function UserLayout() {
  const domain = useV2Domain();

  return (
    <div className='v2-user'>
      <header className='v2-masthead'>
        <div className='v2-masthead-inner'>
          <ProductRootSwitcher>
            <DomainFilter />
          </ProductRootSwitcher>
          <nav aria-label='News sections' style={{ width: '100%' }}>
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
        </div>
      </header>
      <main className='v2-page'>
        <Outlet />
      </main>
    </div>
  );
}
