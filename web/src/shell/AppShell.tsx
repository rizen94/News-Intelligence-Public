/**
 * Shared product shell — one chrome frame for News / Finance / Admin.
 * Root-specific tokens belong in the content pane, not the outer frame.
 */
import React from 'react';
import { ProductRootSwitcher, type ProductRoot } from './ProductRootSwitcher';
import './productChrome.css';

export type AppShellProps = {
  root: ProductRoot;
  /** Brand subtitle (Finance, Admin). News omits. */
  subtitle?: string;
  brandTo?: string;
  /** Extra header actions (e.g. domain filter). */
  headerActions?: React.ReactNode;
  /** Section nav (sidebar). Omit for full-bleed content. */
  sidebar?: React.ReactNode;
  /** Optional sidebar aria-label. */
  sidebarLabel?: string;
  /** Content pane — may set root-specific paper/tokens. */
  children: React.ReactNode;
  /** Extra class on the outer shell (e.g. content-token scopes). */
  className?: string;
  /** Extra class on the main content pane. */
  contentClassName?: string;
  showClassic?: boolean;
  classicTo?: string;
};

export default function AppShell({
  root,
  subtitle,
  brandTo,
  headerActions,
  sidebar,
  sidebarLabel = 'Section navigation',
  children,
  className,
  contentClassName,
  showClassic,
  classicTo,
}: AppShellProps) {
  const shellClass = ['ni-app-shell', `ni-app-shell--${root}`, className]
    .filter(Boolean)
    .join(' ');
  const mainClass = ['ni-app-main', contentClassName].filter(Boolean).join(' ');

  return (
    <div className={shellClass} data-product-root={root}>
      <header className='ni-app-header'>
        <div className='ni-app-header-inner'>
          <ProductRootSwitcher
            subtitle={subtitle}
            brandTo={brandTo}
            showClassic={showClassic}
            classicTo={classicTo}
          >
            {headerActions}
          </ProductRootSwitcher>
        </div>
      </header>
      <div className={sidebar ? 'ni-app-body' : 'ni-app-body ni-app-body--solo'}>
        {sidebar ? (
          <aside className='ni-app-sidebar' aria-label={sidebarLabel}>
            {sidebar}
          </aside>
        ) : null}
        <main className={mainClass}>{children}</main>
      </div>
    </div>
  );
}
