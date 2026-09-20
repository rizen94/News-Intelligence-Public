/**
 * Admin product layout — ops sidebar + shared AppShell chrome.
 * Deliberately excludes user-content destinations (Dashboard, Storylines, …).
 */
import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import '../styles/broadsheet.css';
import {
  AdminOpsSidebar,
  adminBaseFromPath,
} from '../../shell/ProductRootSwitcher';
import AppShell from '../../shell/AppShell';

export default function AdminLayout() {
  const { pathname } = useLocation();
  const base = adminBaseFromPath(pathname);

  return (
    <AppShell
      root='admin'
      subtitle='Admin'
      brandTo={base}
      sidebar={<AdminOpsSidebar base={base} />}
      sidebarLabel='Admin operations'
      className='v2-admin'
    >
      <Outlet />
    </AppShell>
  );
}
