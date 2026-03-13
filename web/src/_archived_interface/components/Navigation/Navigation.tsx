import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import DomainSelector from '../DomainSelector/DomainSelector';
import { useDomain } from '../../contexts/DomainContext';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import apiService from '../../services/apiService';
import './Navigation.css';

const Navigation: React.FC = () => {
  const location = useLocation();
  const { domainName, domain } = useDomain();
  const { getDomainPath, isInDomain } = useDomainRoute();
  const [unreadAlerts, setUnreadAlerts] = useState(0);

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const res = await apiService.getWatchlistAlerts(true, 100);
        if (res?.data) setUnreadAlerts(Array.isArray(res.data) ? res.data.length : 0);
      } catch { /* non-critical */ }
    };
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 60000);
    return () => clearInterval(interval);
  }, []);

  // Core navigation items - SAME FOR ALL DOMAINS
  // These features are available in Politics, Finance, and Science & Tech
  const coreNavItems = [
    { path: '/dashboard', label: 'Dashboard', icon: '📊' },
    { path: '/articles', label: 'Articles', icon: '📰' },
    { path: '/storylines', label: 'Storylines', icon: '📚' },
    { path: '/topics', label: 'Topics', icon: '🏷️' },
    { path: '/rss-feeds', label: 'RSS Feeds', icon: '📡' },
    { path: '/intelligence', label: 'Intelligence', icon: '🧠' },
  ];

  // Domain-specific navigation items (ADDITIONS ONLY, not replacements)
  // Finance domain gets these in addition to core features
  const financeNavItems = [
    { path: '/market-research', label: 'Market Research', icon: '📈' },
    { path: '/corporate-announcements', label: 'Corporate News', icon: '🏢' },
    { path: '/market-patterns', label: 'Market Patterns', icon: '📊' },
    { path: '/analysis', label: 'Financial Analysis', icon: '🔍' },
    { path: '/evidence', label: 'Evidence', icon: '📋' },
    { path: '/sources', label: 'Source Health', icon: '✅' },
    { path: '/schedule', label: 'Refresh Schedule', icon: '⏰' },
    { path: '/fact-check', label: 'Fact Check', icon: '✓' },
  ];

  // Intelligence sub-pages (only built-out features per docs)
  const intelligenceNavItems = [
    { path: '/intelligence/watchlist', label: 'Watchlist', icon: '👁️' },
    { path: '/intelligence/entity-profiles', label: 'Entity Profiles', icon: '👤' },
    { path: '/intelligence/entity-management', label: 'Entity Management', icon: '⚙️' },
    { path: '/intelligence/contexts', label: 'Context Browser', icon: '📄' },
    { path: '/intelligence/tracked-events', label: 'Tracked Events', icon: '📅' },
    { path: '/intelligence/search', label: 'Intelligence Search', icon: '🔍' },
    { path: '/intelligence/collection-watch', label: 'Collection & pipeline', icon: '▶️' },
    { path: '/intelligence/context-centric-status', label: 'Context Pipeline', icon: '📊' },
  ];

  // Admin/system navigation items
  const adminNavItems = [
    { path: '/ml-processing', label: 'ML Processing', icon: '⚙️' },
  ];

  // Domain-agnostic navigation items (shared across all domains)
  const sharedNavItems = [
    { path: '/settings', label: 'Settings', icon: '⚙️' },
  ];

  let navItems = [...coreNavItems, ...intelligenceNavItems];
  if (isInDomain('finance')) {
    navItems = [...coreNavItems, ...intelligenceNavItems, ...financeNavItems];
  }
  navItems = [...navItems, ...adminNavItems, ...sharedNavItems];

  // Check if a path is active (handles both domain-specific and shared routes)
  const isActive = (path: string): boolean => {
    const sharedPaths = ['/settings', '/ml-processing'];
    if (sharedPaths.includes(path)) {
      return location.pathname === path || location.pathname.startsWith(path + '/');
    }
    // For domain-specific routes, check if path matches with domain prefix
    const domainPath = getDomainPath(path);
    return location.pathname === domainPath || location.pathname.startsWith(domainPath + '/');
  };

  return (
    <nav className='navigation'>
      <div className='nav-header'>
        <h3>News Intelligence</h3>
        <div className='nav-domain-indicator'>
          <span className='nav-domain-badge' data-domain={domain}>
            {domainName}
          </span>
        </div>
      </div>
      <div className='nav-domain-selector'>
        <DomainSelector variant='tabs' orientation='vertical' showLabel={false} />
      </div>
      <ul className='nav-list'>
        {navItems.map(item => {
          // Use domain path for domain-specific items, direct path for shared items
          const sharedPaths = ['/settings', '/ml-processing'];
          const linkPath = sharedPaths.includes(item.path)
            ? item.path
            : getDomainPath(item.path);
          return (
            <li key={item.path} className='nav-item'>
              <Link
                to={linkPath}
                className={`nav-link ${isActive(item.path) ? 'active' : ''}`}
              >
                <span className='nav-icon'>{item.icon}</span>
                <span className='nav-label'>{item.label}</span>
                {item.path === '/intelligence/watchlist' && unreadAlerts > 0 && (
                  <span className='nav-badge'>{unreadAlerts > 9 ? '9+' : unreadAlerts}</span>
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
};

export default Navigation;
