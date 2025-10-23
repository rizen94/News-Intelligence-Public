import React from 'react';
import './Footer.css';

const Footer: React.FC = () => {
  return (
    <footer className="footer">
      <div className="footer-content">
        <div className="footer-left">
          <p>&copy; 2025 News Intelligence System. All rights reserved.</p>
        </div>
        <div className="footer-right">
          <p>Version 3.3.0 | Powered by AI</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
