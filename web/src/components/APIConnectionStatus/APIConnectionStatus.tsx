/**
 * API Connection Status Component
 * Displays API connection status and allows manual reconnection
 */

import React, { useState } from 'react';
import { Box, Chip, IconButton, Tooltip, Alert } from '@mui/material';
import { CheckCircle, Error, Refresh } from '@mui/icons-material';
import { useShellStatusOptional } from '../../contexts/ShellStatusContext';
import { getAPIConnectionManager } from '../../services/apiConnectionManager';

interface APIConnectionStatusProps {
  showDetails?: boolean;
}

const APIConnectionStatus: React.FC<APIConnectionStatusProps> = ({
  showDetails = false,
}) => {
  const shell = useShellStatusOptional();
  const [isChecking, setIsChecking] = useState(false);
  const [manualConnected, setManualConnected] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isConnected =
    manualConnected !== null ? manualConnected : (shell?.apiConnected ?? false);

  const checkConnection = async () => {
    setIsChecking(true);
    setError(null);
    try {
      if (shell) {
        await shell.refresh();
        setManualConnected(shell.apiConnected);
        if (!shell.apiConnected) {
          setError(
            'API not reachable at /api on this host (504/timeout usually means the backend is overloaded, not a wrong API URL). Ensure the API service is running on Widow.'
          );
        }
        return;
      }
      const connectionManager = getAPIConnectionManager();
      const connected = await connectionManager.testConnection();
      setManualConnected(connected);
      if (!connected) {
        setError(
          'API not reachable at /api on this host (504/timeout usually means the backend is overloaded, not a wrong API URL). Ensure the API service is running on Widow.'
        );
      }
    } catch (err: unknown) {
      setManualConnected(false);
      setError(
        (err as Error)?.message ||
          'Connection check failed. Is the API running on port 8000?'
      );
    } finally {
      setIsChecking(false);
    }
  };

  const getStatusIcon = () => {
    if (isChecking) {
      return <Refresh sx={{ animation: 'spin 1s linear infinite' }} />;
    }
    if (isConnected) {
      return <CheckCircle color='success' />;
    }
    return <Error color='error' />;
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
    <Box display='flex' alignItems='center' gap={1}>
      <Tooltip title='Refresh API connection status'>
        <IconButton size='small' onClick={checkConnection} disabled={isChecking}>
          {getStatusIcon()}
        </IconButton>
      </Tooltip>
      {showDetails && (
        <Chip
          size='small'
          label={getStatusText()}
          color={getStatusColor()}
          variant='outlined'
        />
      )}
      {showDetails && error && (
        <Alert severity='error' sx={{ py: 0, px: 1 }}>
          {error}
        </Alert>
      )}
    </Box>
  );
};

export default APIConnectionStatus;
