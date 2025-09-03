import React, { createContext, useContext, useState, useCallback } from 'react';
import {
  Snackbar,
  Alert,
  AlertTitle,
  IconButton,
  Collapse
} from '@mui/material';
import {
  Close as CloseIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon
} from '@mui/icons-material';

const NotificationContext = createContext();

export const useNotifications = () => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
};

export const NotificationProvider = ({ children }) => {
  const [notifications, setNotifications] = useState([]);
  const [expanded, setExpanded] = useState({});

  const addNotification = useCallback((notification) => {
    const id = Date.now() + Math.random();
    const newNotification = {
      id,
      severity: 'info',
      title: null,
      message: '',
      duration: 6000,
      action: null,
      details: null,
      ...notification
    };

    setNotifications(prev => [...prev, newNotification]);

    // Auto-remove notification after duration
    if (newNotification.duration > 0) {
      setTimeout(() => {
        removeNotification(id);
      }, newNotification.duration);
    }

    return id;
  }, []);

  const removeNotification = useCallback((id) => {
    setNotifications(prev => prev.filter(notification => notification.id !== id));
    setExpanded(prev => {
      const newExpanded = { ...prev };
      delete newExpanded[id];
      return newExpanded;
    });
  }, []);

  const clearAllNotifications = useCallback(() => {
    setNotifications([]);
    setExpanded({});
  }, []);

  const toggleExpanded = useCallback((id) => {
    setExpanded(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  }, []);

  // Convenience methods
  const showSuccess = useCallback((message, options = {}) => {
    return addNotification({
      severity: 'success',
      message,
      ...options
    });
  }, [addNotification]);

  const showError = useCallback((message, options = {}) => {
    return addNotification({
      severity: 'error',
      message,
      duration: 0, // Don't auto-dismiss errors
      ...options
    });
  }, [addNotification]);

  const showWarning = useCallback((message, options = {}) => {
    return addNotification({
      severity: 'warning',
      message,
      ...options
    });
  }, [addNotification]);

  const showInfo = useCallback((message, options = {}) => {
    return addNotification({
      severity: 'info',
      message,
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
    showInfo
  };

  return (
    <NotificationContext.Provider value={value}>
      {children}
      <NotificationContainer 
        notifications={notifications}
        expanded={expanded}
        onRemove={removeNotification}
        onToggleExpanded={toggleExpanded}
      />
    </NotificationContext.Provider>
  );
};

const NotificationContainer = ({ 
  notifications, 
  expanded, 
  onRemove, 
  onToggleExpanded 
}) => {
  return (
    <Box
      sx={{
        position: 'fixed',
        top: 20,
        right: 20,
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        maxWidth: 400
      }}
    >
      {notifications.map((notification) => (
        <NotificationItem
          key={notification.id}
          notification={notification}
          expanded={expanded[notification.id] || false}
          onRemove={onRemove}
          onToggleExpanded={onToggleExpanded}
        />
      ))}
    </Box>
  );
};

const NotificationItem = ({ 
  notification, 
  expanded, 
  onRemove, 
  onToggleExpanded 
}) => {
  const {
    id,
    severity,
    title,
    message,
    action,
    details
  } = notification;

  const handleClose = () => {
    onRemove(id);
  };

  const handleToggleExpanded = () => {
    onToggleExpanded(id);
  };

  return (
    <Alert
      severity={severity}
      onClose={handleClose}
      sx={{
        minWidth: 300,
        '& .MuiAlert-message': {
          width: '100%'
        }
      }}
      action={
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          {details && (
            <IconButton
              size="small"
              onClick={handleToggleExpanded}
              sx={{ mr: 1 }}
            >
              {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            </IconButton>
          )}
          {action && (
            <Box sx={{ mr: 1 }}>
              {action}
            </Box>
          )}
          <IconButton
            size="small"
            onClick={handleClose}
          >
            <CloseIcon />
          </IconButton>
        </Box>
      }
    >
      {title && <AlertTitle>{title}</AlertTitle>}
      {message}
      
      {details && (
        <Collapse in={expanded}>
          <Box sx={{ mt: 1, p: 1, backgroundColor: 'rgba(0,0,0,0.1)', borderRadius: 1 }}>
            <pre style={{ 
              margin: 0, 
              fontSize: '0.75rem', 
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word'
            }}>
              {typeof details === 'string' ? details : JSON.stringify(details, null, 2)}
            </pre>
          </Box>
        </Collapse>
      )}
    </Alert>
  );
};

export default NotificationProvider;
