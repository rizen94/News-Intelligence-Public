/**
 * Top-level product root toggle: News (/) · Finance (/finance) · Admin (/admin).
 * Shared across broadsheet, finance, and admin shells.
 * Public site: https://news-intelligence-ag.duckdns.org
 */
import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import './productChrome.css';
import { getGrafanaOpsUrl } from '../config/grafanaConfig';
import {
  ADMIN_HOME,
  FINANCE_HOME,
  NEWS_HOME,
  newsHomePath,
} from '../paths';

export type ProductRoot = 'news' | 'finance' | 'admin';

const ROOTS: Array<{ id: ProductRoot; label: string; to: string }> = [
  { id: 'news', label: 'News', to: newsHomePath() },
  { id: 'finance', label: 'Finance', to: FINANCE_HOME },
  { id: 'admin', label: 'Admin', to: ADMIN_HOME },
];

export function detectProductRoot(pathname: string): ProductRoot | null {
  if (pathname === ADMIN_HOME || pathname.startsWith(`${ADMIN_HOME}/`)) {
    return 'admin';
  }
  if (
    pathname === FINANCE_HOME ||
    pathname.startsWith('/finance/trackers') ||
    pathname.startsWith('/finance/markets') ||
    pathname.startsWith('/finance/reporting')
  ) {
    return 'finance';
  }
  if (
    pathname === NEWS_HOME ||
    pathname === '/news' ||
    pathname.startsWith('/news/') ||
    pathname === '/current' ||
    pathname.startsWith('/current/') ||
    pathname === '/research' ||
    pathname.startsWith('/research/') ||
    pathname === '/one-offs' ||
    pathname.startsWith('/one-offs/') ||
    pathname.startsWith('/storylines/') ||
    pathname.startsWith('/entities/') ||
    pathname === '/v2' ||
    pathname.startsWith('/v2/')
  ) {
    return 'news';
  }
  return null;
}

export function adminBaseFromPath(_pathname?: string): typeof ADMIN_HOME {
  return ADMIN_HOME;
}

type SwitcherProps = {
  subtitle?: string;
  brandTo?: string;
  children?: React.ReactNode;
};

export function ProductRootSwitcher({
  subtitle,
  brandTo,
  children,
}: SwitcherProps) {
  const { pathname } = useLocation();
  const active = detectProductRoot(pathname) ?? 'news';
  const home =
    brandTo ??
    (active === 'finance'
      ? FINANCE_HOME
      : active === 'admin'
        ? ADMIN_HOME
        : newsHomePath());

  return (
    <div className='ni-product-chrome'>
      <Link to={home} className='ni-product-brand'>
        News Intelligence
        {subtitle ? <span className='ni-product-brand-sub'>{subtitle}</span> : null}
      </Link>
      <nav className='ni-root-switcher' aria-label='Product root'>
        {ROOTS.map(root => (
          <Link
            key={root.id}
            to={root.to}
            className={active === root.id ? 'is-active' : undefined}
            aria-current={active === root.id ? 'page' : undefined}
          >
            {root.label}
          </Link>
        ))}
      </nav>
      <div className='ni-chrome-spacer' />
      {children}
    </div>
  );
}

const ADMIN_NAV = [
  { segment: '', label: 'Overview', end: true },
  { segment: 'monitor', label: 'Monitor' },
  { segment: 'work', label: 'Work' },
  { segment: 'sql', label: 'SQL' },
  { segment: 'audit', label: 'Audit' },
] as const;

type AdminSidebarProps = {
  base?: typeof ADMIN_HOME;
};

export function AdminOpsSidebar({ base }: AdminSidebarProps) {
  const { pathname } = useLocation();
  const adminBase = base ?? adminBaseFromPath(pathname);
  const grafanaUrl = getGrafanaOpsUrl();

  return (
    <>
      <div className='ni-sidebar-section'>
        <div className='ni-sidebar-label'>Operations</div>
        {ADMIN_NAV.map(item => {
          const to = item.segment ? `${adminBase}/${item.segment}` : adminBase;
          const isEnd = 'end' in item && item.end;
          const isActive = isEnd
            ? pathname === adminBase || pathname === `${adminBase}/`
            : pathname === to || pathname.startsWith(`${to}/`);
          return (
            <Link
              key={item.label}
              to={to}
              className={isActive ? 'is-active' : undefined}
              aria-current={isActive ? 'page' : undefined}
            >
              {item.label}
            </Link>
          );
        })}
      </div>
      <div className='ni-sidebar-footer'>
        {grafanaUrl ? (
          <a href={grafanaUrl} target='_blank' rel='noopener noreferrer'>
            Open Grafana
          </a>
        ) : (
          <span className='ni-classic-link'>
            Grafana URL not set (VITE_NEWS_INTEL_GRAFANA_URL)
          </span>
        )}
      </div>
    </>
  );
}
