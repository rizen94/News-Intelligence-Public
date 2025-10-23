import { Close as CloseIcon } from '@mui/icons-material';
import { Snackbar, Alert, IconButton } from '@mui/material';
import React, { createContext, useContext, useReducer } from 'react';

// Notification types
const NOTIFICATION_TYPES = {
  SUCCESS: 'success',
  ERROR: 'error',
  WARNING: 'warning',
  INFO: 'info',
};

// Initial state
const initialState = {
  notifications: [],
};

// Action types
const ActionTypes = {
  ADD_NOTIFICATION: 'ADD_NOTIFICATION',
  REMOVE_NOTIFICATION: 'REMOVE_NOTIFICATION',
  CLEAR_ALL: 'CLEAR_ALL',
};

// Reducer
function notificationReducer(state, action) {
  switch (action.type) {
  case ActionTypes.ADD_NOTIFICATION:
    return {
      ...state,
      notifications: [...state.notifications, action.payload],
    };
  case ActionTypes.REMOVE_NOTIFICATION:
    return {
      ...state,
      notifications: state.notifications.filter(n => n.id !== action.payload),
    };
  case ActionTypes.CLEAR_ALL:
    return {
      ...state,
      notifications: [],
    };
  default:
    return state;
  }
}

// Context
const NotificationContext = createContext();

// Provider component
export const NotificationProvider = ({ children }) => {
  const [state, dispatch] = useReducer(notificationReducer, initialState);

  const addNotification = (message, type = NOTIFICATION_TYPES.INFO, duration = 6000) => {
    const id = Date.now() + Math.random();
    const notification = {
      id,
      message,
      type,
      duration,
    };
    dispatch({ type: ActionTypes.ADD_NOTIFICATION, payload: notification });

    // Auto-remove after duration
    if (duration > 0) {
      setTimeout(() => {
        dispatch({ type: ActionTypes.REMOVE_NOTIFICATION, payload: id });
      }, duration);
    }
  };

  const removeNotification = (id) => {
    dispatch({ type: ActionTypes.REMOVE_NOTIFICATION, payload: id });
  };

  const clearAll = () => {
    dispatch({ type: ActionTypes.CLEAR_ALL });
  };

  const showSuccess = (message, duration) => addNotification(message, NOTIFICATION_TYPES.SUCCESS, duration);
  const showError = (message, duration) => addNotification(message, NOTIFICATION_TYPES.ERROR, duration);
  const showWarning = (message, duration) => addNotification(message, NOTIFICATION_TYPES.WARNING, duration);
  const showInfo = (message, duration) => addNotification(message, NOTIFICATION_TYPES.INFO, duration);

  const value = {
    notifications: state.notifications,
    addNotification,
    removeNotification,
    clearAll,
    showSuccess,
    showError,
    showWarning,
    showInfo,
  };

  return (
    <NotificationContext.Provider value={value}>
      {children}
      <NotificationContainer />
    </NotificationContext.Provider>
  );
};

// Notification container component
const NotificationContainer = () => {
  const { notifications, removeNotification } = useContext(NotificationContext);

  return (
    <>
      {notifications.map((notification) => (
        <Snackbar
          key={notification.id}
          open={true}
          autoHideDuration={notification.duration}
          onClose={() => removeNotification(notification.id)}
          anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
        >
          <Alert
            severity={notification.type}
            action={
              <IconButton
                size="small"
                aria-label="close"
                color="inherit"
                onClick={() => removeNotification(notification.id)}
              >
                <CloseIcon fontSize="small" />
              </IconButton>
            }
          >
            {notification.message}
          </Alert>
        </Snackbar>
      ))}
    </>
  );
};

// Hook to use the context
export function useNotifications() {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
}

export default NotificationContext;
