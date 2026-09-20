/**
 * Admin product layout — ops-only sidebar + shared product-root chrome.
 * Deliberately excludes user-content destinations (Dashboard, Storylines, Articles, …).
 */
import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import '../styles/broadsheet.css';
import {
  AdminOpsSidebar,
  ProductRootSwitcher,
  adminBaseFromPath,
} from '../../shell/ProductRootSwitcher';

export default function AdminLayout() {
  const { pathname } = useLocation();
  const base = adminBaseFromPath(pathname);

  return (
    <div className='v2-admin'>
      <header className='v2-admin-nav'>
        <ProductRootSwitcher subtitle='Admin' brandTo={base} />
      </header>
      <div className='ni-admin-shell'>
        <AdminOpsSidebar base={base} />
        <main className='ni-admin-main'>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
