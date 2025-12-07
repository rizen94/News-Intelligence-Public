import React from 'react';
import './Header.css';

const Header: React.FC = () => {
  return (
    <header className='header'>
      <div className='header-content'>
        <div className='header-left'>
          <h1>News Intelligence System v3.0</h1>
          <p>AI-Powered News Analysis Platform</p>
        </div>
        <div className='header-right'>
          <div className='status-indicator'>
            <span className='status-dot online'></span>
            <span>System Online</span>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
