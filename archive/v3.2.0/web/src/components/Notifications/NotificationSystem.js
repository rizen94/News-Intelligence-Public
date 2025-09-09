import React, { createContext, useContext, useState, useCallback } from 'react';
import {
  Snackbar,
  Alert,
  AlertTitle,
  IconButton,
  Collapse,
  Box,
  Typography
} from '@mui/material';
import {
  Close as CloseIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';

// Notification context
const NotificationContext = createContext();

// Custom hook to use notifications
export const useNotifications = () => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
};

// Notification provider component
export const NotificationProvider = ({ children }) => {
  const [notifications, setNotifications] = useState([]);

  const addNotification = useCallback((notification) => {
    const id = Date.now() + Math.random();
    const newNotification = {
      id,
      timestamp: new Date(),
      ...notification
    };
    
    setNotifications(prev => [...prev, newNotification]);
    
    // Auto-remove after duration (default 5 seconds)
    const duration = notification.duration || 5000;
    setTimeout(() => {
      removeNotification(id);
    }, duration);
    
    return id;
  }, []);

  const removeNotification = useCallback((id) => {
    setNotifications(prev => prev.filter(notification => notification.id !== id));
  }, []);

  const clearAllNotifications = useCallback(() => {
    setNotifications([]);
  }, []);

  // Convenience methods for different notification types
  const showSuccess = useCallback((message, title = 'Success', options = {}) => {
    return addNotification({
      type: 'success',
      title,
      message,
      icon: <CheckCircleIcon />,
      ...options
    });
  }, [addNotification]);

  const showError = useCallback((message, title = 'Error', options = {}) => {
    return addNotification({
      type: 'error',
      title,
      message,
      icon: <ErrorIcon />,
      duration: 8000, // Errors stay longer
      ...options
    });
  }, [addNotification]);

  const showWarning = useCallback((message, title = 'Warning', options = {}) => {
    return addNotification({
      type: 'warning',
      title,
      message,
      icon: <WarningIcon />,
      duration: 6000,
      ...options
    });
  }, [addNotification]);

  const showInfo = useCallback((message, title = 'Info', options = {}) => {
    return addNotification({
      type: 'info',
      title,
      message,
      icon: <InfoIcon />,
      ...options
    });
  }, [addNotification]);

  const showLoading = useCallback((message, title = 'Loading', options = {}) => {
    return addNotification({
      type: 'info',
      title,
      message,
      icon: <RefreshIcon className="animate-spin" />,
      duration: 0, // Loading notifications don't auto-remove
      ...options
    });
  }, [addNotification]);

  const value = {
    notifications,
    addNotification,
    removeNotification,
    clearAllNotifications,
    showSuccess,
    showError,
    showWarning,
    showInfo,
    showLoading
  };

  return (
    <NotificationContext.Provider value={value}>
      {children}
      <NotificationContainer notifications={notifications} onRemove={removeNotification} />
    </NotificationContext.Provider>
  );
};

// Notification container component
const NotificationContainer = ({ notifications, onRemove }) => {
  const [expanded, setExpanded] = useState({});

  const handleExpand = (id) => {
    setExpanded(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const getSeverity = (type) => {
    switch (type) {
      case 'success': return 'success';
      case 'error': return 'error';
      case 'warning': return 'warning';
      case 'info': return 'info';
      default: return 'info';
    }
  };

  return (
    <Box
      sx={{
        position: 'fixed',
        top: 20,
        right: 20,
        zIndex: 9999,
        maxWidth: 400,
        width: '100%'
      }}
    >
      {notifications.map((notification) => (
        <Snackbar
          key={notification.id}
          open={true}
          anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
          sx={{ mb: 1 }}
        >
          <Alert
            severity={getSeverity(notification.type)}
            icon={notification.icon}
            action={
              <Box display="flex" alignItems="center" gap={1}>
                {notification.details && (
                  <IconButton
                    size="small"
                    onClick={() => handleExpand(notification.id)}
                    sx={{ color: 'inherit' }}
                  >
                    <Typography variant="caption">
                      {expanded[notification.id] ? 'Less' : 'More'}
                    </Typography>
                  </IconButton>
                )}
                <IconButton
                  size="small"
                  onClick={() => onRemove(notification.id)}
                  sx={{ color: 'inherit' }}
                >
                  <CloseIcon fontSize="small" />
                </IconButton>
              </Box>
            }
            sx={{
              width: '100%',
              '& .MuiAlert-message': {
                width: '100%'
              }
            }}
          >
            <AlertTitle>{notification.title}</AlertTitle>
            {notification.message}
            {notification.details && (
              <Collapse in={expanded[notification.id]}>
                <Box sx={{ mt: 1, pt: 1, borderTop: 1, borderColor: 'divider' }}>
                  <Typography variant="body2" color="text.secondary">
                    {notification.details}
                  </Typography>
                </Box>
              </Collapse>
            )}
          </Alert>
        </Snackbar>
      ))}
    </Box>
  );
};

// CSS for spin animation
const spinStyle = `
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
  .animate-spin {
    animation: spin 1s linear infinite;
  }
`;

// Inject CSS
if (typeof document !== 'undefined') {
  const style = document.createElement('style');
  style.textContent = spinStyle;
  document.head.appendChild(style);
}

export default NotificationProvider;