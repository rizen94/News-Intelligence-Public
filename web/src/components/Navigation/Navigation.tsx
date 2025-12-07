import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import './Navigation.css';

const Navigation: React.FC = () => {
  const location = useLocation();

  const navItems = [
    { path: '/dashboard', label: 'Dashboard', icon: '📊' },
    { path: '/articles', label: 'Articles', icon: '📰' },
    { path: '/storylines', label: 'Storylines', icon: '📚' },
    { path: '/topics', label: 'Topics', icon: '🏷️' },
    { path: '/rss-feeds', label: 'RSS Feeds', icon: '📡' },
    { path: '/monitoring', label: 'Monitoring', icon: '🔍' },
    { path: '/intelligence', label: 'Intelligence', icon: '🧠' },
    { path: '/settings', label: 'Settings', icon: '⚙️' },
  ];

  return (
    <nav className='navigation'>
      <div className='nav-header'>
        <h3>News Intelligence</h3>
      </div>
      <ul className='nav-list'>
        {navItems.map(item => (
          <li key={item.path} className='nav-item'>
            <Link
              to={item.path}
              className={`nav-link ${
                location.pathname === item.path ? 'active' : ''
              }`}
            >
              <span className='nav-icon'>{item.icon}</span>
              <span className='nav-label'>{item.label}</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
};

export default Navigation;
