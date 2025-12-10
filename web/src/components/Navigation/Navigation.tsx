import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import DomainSelector from '../DomainSelector/DomainSelector';
import { useDomain } from '../../contexts/DomainContext';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import './Navigation.css';

const Navigation: React.FC = () => {
  const location = useLocation();
  const { domainName, domain } = useDomain();
  const { getDomainPath, isInDomain } = useDomainRoute();

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
  ];

  // Domain-agnostic navigation items (shared across all domains)
  const sharedNavItems = [
    { path: '/monitoring', label: 'Monitoring', icon: '🔍' },
    { path: '/settings', label: 'Settings', icon: '⚙️' },
  ];

  // Combine navigation items: Core features + Domain-specific additions + Shared items
  // All domains get the same core features, with domain-specific additions
  let navItems = [...coreNavItems];
  if (isInDomain('finance')) {
    navItems = [...coreNavItems, ...financeNavItems];
  }
  // Future: Add other domain-specific items here (e.g., science-tech specific features)
  navItems = [...navItems, ...sharedNavItems];

  // Check if a path is active (handles both domain-specific and shared routes)
  const isActive = (path: string): boolean => {
    // For shared routes (monitoring, settings), check exact match
    if (path === '/monitoring' || path === '/settings') {
      return location.pathname === path;
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
          const linkPath = (item.path === '/monitoring' || item.path === '/settings')
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
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
};

export default Navigation;
