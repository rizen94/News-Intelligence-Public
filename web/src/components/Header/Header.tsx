import React from 'react';
import { useDomain } from '../../contexts/DomainContext';
import { Chip, Box } from '@mui/material';
import APIConnectionStatus from '../APIConnectionStatus/APIConnectionStatus';
import './Header.css';

const Header: React.FC = () => {
  const { domainName, domain } = useDomain();

  // Domain-specific styling
  const getDomainColor = () => {
    switch (domain) {
    case 'politics':
      return { bg: '#1976d2', text: '#fff' }; // Blue
    case 'finance':
      return { bg: '#2e7d32', text: '#fff' }; // Green
    case 'science-tech':
      return { bg: '#7b1fa2', text: '#fff' }; // Purple
    case 'legal':
      return { bg: '#455a64', text: '#fff' }; // Blue-grey
    default:
      return { bg: '#616161', text: '#fff' }; // Gray
    }
  };

  const domainColor = getDomainColor();

  return (
    <header className='header'>
      <div className='header-content'>
        <div className='header-left'>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <h1>News Intelligence System v5.0</h1>
            <Chip
              label={domainName}
              sx={{
                backgroundColor: domainColor.bg,
                color: domainColor.text,
                fontWeight: 600,
                fontSize: '0.875rem',
                height: '32px',
              }}
            />
          </Box>
          <p>AI-Powered Multi-Domain News Analysis Platform</p>
        </div>
        <div className='header-right'>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <APIConnectionStatus showDetails={false} />
            <div className='status-indicator'>
              <span className='status-dot online'></span>
              <span>System Online</span>
            </div>
          </Box>
        </div>
      </div>
    </header>
  );
};

export default Header;
