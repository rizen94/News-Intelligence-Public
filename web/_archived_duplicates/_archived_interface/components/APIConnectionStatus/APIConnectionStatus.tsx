/**
 * API Connection Status Component
 * Displays API connection status and allows manual reconnection
 */

import React, { useState, useEffect } from 'react';
import { Box, Chip, IconButton, Tooltip, Alert } from '@mui/material';
import {
  CheckCircle,
  Error,
  Refresh,
} from '@mui/icons-material';
import { getAPIConnectionManager } from '../../services/apiConnectionManager';

interface APIConnectionStatusProps {
  showDetails?: boolean;
}

const APIConnectionStatus: React.FC<APIConnectionStatusProps> = ({ showDetails = false }) => {
  const [isConnected, setIsConnected] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const connectionManager = getAPIConnectionManager();

  const checkConnection = async() => {
    setIsChecking(true);
    setError(null);
    try {
      const connected = await connectionManager.testConnection();
      setIsConnected(connected);
      if (!connected) {
        setError('Unable to connect to API server');
      }
    } catch (err: any) {
      setIsConnected(false);
      setError(err.message || 'Connection check failed');
    } finally {
      setIsChecking(false);
    }
  };

  useEffect(() => {
    // Initial check
    checkConnection();

    // Optional: Check periodically (but not too frequently)
    // User can also manually refresh
    const interval = setInterval(() => {
      checkConnection();
    }, 30000); // Check every 30 seconds (much less frequent)

    return () => clearInterval(interval);
  }, []);

  const getStatusIcon = () => {
    if (isChecking) {
      return <Refresh sx={{ animation: 'spin 1s linear infinite' }} />;
    }
    if (isConnected) {
      return <CheckCircle color="success" />;
    }
    return <Error color="error" />;
  };

  const getStatusColor = () => {
    if (isChecking) return 'default';
    return isConnected ? 'success' : 'error';
  };

  const getStatusText = () => {
    if (isChecking) return 'Checking...';
    return isConnected ? 'Connected' : 'Disconnected';
  };

  return (
    <Box display="flex" alignItems="center" gap={1}>
      <Tooltip title={error || (isConnected ? 'API connection is active' : 'API connection failed - click to retry')}>
        <Chip
          icon={getStatusIcon()}
          label={getStatusText()}
          color={getStatusColor()}
          size="small"
          onClick={checkConnection}
          sx={{ cursor: 'pointer' }}
        />
      </Tooltip>
      <Tooltip title="Refresh connection">
        <span>
          <IconButton size="small" onClick={checkConnection} disabled={isChecking}>
            <Refresh />
          </IconButton>
        </span>
      </Tooltip>
      {showDetails && error && (
        <Alert severity="error" sx={{ ml: 1 }}>
          {error}
        </Alert>
      )}
    </Box>
  );
};

export default APIConnectionStatus;

