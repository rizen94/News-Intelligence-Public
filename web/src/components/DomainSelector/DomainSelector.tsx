/**
 * Domain Selector Component
 * Allows users to switch between domains (Politics, Finance, Science & Technology)
 */

import React from 'react';
import { Tabs, Tab, Box, Typography, Chip } from '@mui/material';
import { useDomain } from '../../contexts/DomainContext';
import { useDomainNavigation } from '../../hooks/useDomainNavigation';
import { DomainKey, isValidDomain } from '../../utils/domainHelper';
import './DomainSelector.css';

interface DomainSelectorProps {
  variant?: 'tabs' | 'chips' | 'select';
  orientation?: 'horizontal' | 'vertical';
  showLabel?: boolean;
}

const DomainSelector: React.FC<DomainSelectorProps> = ({
  variant = 'tabs',
  orientation = 'horizontal',
  showLabel = true,
}) => {
  const { domain, setDomain, availableDomains } = useDomain();
  const { switchDomain } = useDomainNavigation();

  const handleDomainChange = (
    _event: React.SyntheticEvent,
    newDomain: string
  ) => {
    if (isValidDomain(newDomain) && newDomain !== domain) {
      setDomain(newDomain as DomainKey);
      // Navigate to the same path in the new domain
      switchDomain(newDomain as DomainKey, true);
    }
  };

  const handleChipClick = (newDomain: DomainKey) => {
    if (newDomain !== domain) {
      setDomain(newDomain);
      switchDomain(newDomain, true);
    }
  };

  const handleSelectChange = (newDomain: string) => {
    if (isValidDomain(newDomain) && newDomain !== domain) {
      setDomain(newDomain as DomainKey);
      switchDomain(newDomain as DomainKey, true);
    }
  };

  if (variant === 'tabs') {
    return (
      <Box className='domain-selector'>
        {showLabel && (
          <Typography
            variant='caption'
            color='text.secondary'
            sx={{ mb: 1, display: 'block' }}
          >
            Domain
          </Typography>
        )}
        <Tabs
          value={domain}
          onChange={handleDomainChange}
          orientation={orientation}
          variant='fullWidth'
          sx={{
            borderBottom: 1,
            borderColor: 'divider',
            minHeight: 'auto',
            '& .MuiTab-root': {
              minHeight: 40,
              textTransform: 'none',
              fontSize: '0.875rem',
              fontWeight: 500,
            },
          }}
        >
          {availableDomains.map(d => (
            <Tab
              key={d.key}
              label={d.name}
              value={d.key}
              sx={{
                '&.Mui-selected': {
                  color: 'primary.main',
                  fontWeight: 600,
                },
              }}
            />
          ))}
        </Tabs>
      </Box>
    );
  }

  if (variant === 'chips') {
    return (
      <Box className='domain-selector domain-selector-chips'>
        {showLabel && (
          <Typography variant='caption' color='text.secondary' sx={{ mr: 1 }}>
            Domain:
          </Typography>
        )}
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {availableDomains.map(d => (
            <Chip
              key={d.key}
              label={d.name}
              onClick={() => handleChipClick(d.key)}
              color={domain === d.key ? 'primary' : 'default'}
              variant={domain === d.key ? 'filled' : 'outlined'}
              sx={{
                cursor: 'pointer',
                fontWeight: domain === d.key ? 600 : 400,
              }}
            />
          ))}
        </Box>
      </Box>
    );
  }

  // Select variant (dropdown)
  return (
    <Box className='domain-selector'>
      {showLabel && (
        <Typography
          variant='caption'
          color='text.secondary'
          sx={{ mb: 0.5, display: 'block' }}
        >
          Domain
        </Typography>
      )}
      <select
        value={domain}
        onChange={e => handleSelectChange(e.target.value)}
        style={{
          padding: '8px 12px',
          borderRadius: '4px',
          border: '1px solid #ccc',
          fontSize: '0.875rem',
          minWidth: '150px',
        }}
      >
        {availableDomains.map(d => (
          <option key={d.key} value={d.key}>
            {d.name}
          </option>
        ))}
      </select>
    </Box>
  );
};

export default DomainSelector;
