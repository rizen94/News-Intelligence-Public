/**
 * Top-level product root toggle: News (/v2) · Finance (/finance) · Admin (/v2/admin).
 * Shared across broadsheet, finance, and admin shells so switching feels like one product.
 */
import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import './productChrome.css';
import { getDefaultDomainKey } from '../utils/domainHelper';
import { getGrafanaOpsUrl } from '../config/grafanaConfig';

export type ProductRoot = 'news' | 'finance' | 'admin';

const ROOTS: Array<{ id: ProductRoot; label: string; to: string }> = [
  { id: 'news', label: 'News', to: '/v2' },
  { id: 'finance', label: 'Finance', to: '/finance' },
  { id: 'admin', label: 'Admin', to: '/v2/admin' },
];

export function detectProductRoot(pathname: string): ProductRoot | null {
  if (
    pathname === '/admin' ||
    pathname.startsWith('/admin/') ||
    pathname === '/v2/admin' ||
    pathname.startsWith('/v2/admin/')
  ) {
    return 'admin';
  }
  if (
    pathname === '/finance' ||
    pathname.startsWith('/finance/trackers') ||
    pathname.startsWith('/finance/markets') ||
    pathname.startsWith('/finance/reporting')
  ) {
    return 'finance';
  }
  if (pathname === '/v2' || pathname.startsWith('/v2/')) {
    return 'news';
  }
  return null;
}

/** Admin base path — prefer /v2/admin; /admin is an alias. */
export function adminBaseFromPath(pathname: string): '/v2/admin' | '/admin' {
  return pathname === '/admin' || pathname.startsWith('/admin/')
    ? '/admin'
    : '/v2/admin';
}

type SwitcherProps = {
  /** Optional brand subtitle (e.g. Finance, Admin). */
  subtitle?: string;
  /** Brand link target; defaults to active root home. */
  brandTo?: string;
  /** Extra actions rendered after the switcher (domain filter, etc.). */
  children?: React.ReactNode;
  /** Show Classic app link (default true). */
  showClassic?: boolean;
  classicTo?: string;
};

export function ProductRootSwitcher({
  subtitle,
  brandTo,
  children,
  showClassic = true,
  classicTo,
}: SwitcherProps) {
  const { pathname } = useLocation();
  const active = detectProductRoot(pathname) ?? 'news';
  const home =
    brandTo ??
    (active === 'finance' ? '/finance' : active === 'admin' ? '/v2/admin' : '/v2');
  const classic =
    classicTo ??
    (active === 'admin'
      ? `/${getDefaultDomainKey()}/monitor`
      : `/${getDefaultDomainKey()}/dashboard`);

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
      {showClassic ? (
        <Link className='ni-classic-link' to={classic}>
          Classic app
        </Link>
      ) : null}
    </div>
  );
}

/** Ops-only Admin sidebar — no Dashboard / Storylines / Articles / etc. */
const ADMIN_NAV = [
  { segment: '', label: 'Overview', end: true },
  { segment: 'monitor', label: 'Monitor' },
  { segment: 'work', label: 'Work' },
  { segment: 'sql', label: 'SQL' },
  { segment: 'audit', label: 'Audit' },
] as const;

type AdminSidebarProps = {
  base?: '/v2/admin' | '/admin';
};

export function AdminOpsSidebar({ base }: AdminSidebarProps) {
  const { pathname } = useLocation();
  const adminBase = base ?? adminBaseFromPath(pathname);
  const grafanaUrl = getGrafanaOpsUrl();

  return (
    <aside className='ni-admin-sidebar' aria-label='Admin operations'>
      <div className='ni-admin-sidebar-label'>Operations</div>
      {ADMIN_NAV.map(item => {
        const to = item.segment ? `${adminBase}/${item.segment}` : adminBase;
        const isActive = item.end
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
      <div className='ni-admin-grafana'>
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
    </aside>
  );
}
