/**
 * Standardized Notification Hook
 * Provides consistent toast notifications across all pages
 */

import { useState, useCallback } from 'react';
import { Snackbar, Alert } from '@mui/material';

export interface NotificationState {
  open: boolean;
  message: string;
  severity: 'success' | 'error' | 'warning' | 'info';
}

export const useNotification = () => {
  const [notification, setNotification] = useState<NotificationState>({
    open: false,
    message: '',
    severity: 'info',
  });

  const showSuccess = useCallback((message: string) => {
    setNotification({
      open: true,
      message,
      severity: 'success',
    });
  }, []);

  const showError = useCallback((message: string) => {
    setNotification({
      open: true,
      message,
      severity: 'error',
    });
  }, []);

  const showWarning = useCallback((message: string) => {
    setNotification({
      open: true,
      message,
      severity: 'warning',
    });
  }, []);

  const showInfo = useCallback((message: string) => {
    setNotification({
      open: true,
      message,
      severity: 'info',
    });
  }, []);

  const closeNotification = useCallback(() => {
    setNotification(prev => ({ ...prev, open: false }));
  }, []);

  const NotificationComponent = () => (
    <Snackbar
      open={notification.open}
      autoHideDuration={6000}
      onClose={closeNotification}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
    >
      <Alert
        onClose={closeNotification}
        severity={notification.severity}
        sx={{ width: '100%' }}
      >
        {notification.message}
      </Alert>
    </Snackbar>
  );

  return {
    showSuccess,
    showError,
    showWarning,
    showInfo,
    closeNotification,
    NotificationComponent,
  };
};
