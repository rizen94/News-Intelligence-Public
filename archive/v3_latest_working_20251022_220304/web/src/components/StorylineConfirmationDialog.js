import {
  Delete,
  Add,
  Edit,
  Warning as WarningIcon,
} from '@mui/icons-material';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Alert,
  CircularProgress,
} from '@mui/material';
import React from 'react';

const StorylineConfirmationDialog = ({
  open,
  onClose,
  onConfirm,
  action,
  storyline,
  loading = false,
  error = null,
}) => {
  const getActionDetails = () => {
    switch (action) {
    case 'create':
      return {
        title: 'Create New Storyline',
        message: 'Are you sure you want to create this new storyline?',
        icon: <Add color="primary" />,
        confirmText: 'Create',
        confirmColor: 'primary',
      };
    case 'delete':
      return {
        title: 'Delete Storyline',
        message: `Are you sure you want to delete "${storyline?.title}"? This action cannot be undone.`,
        icon: <Delete color="error" />,
        confirmText: 'Delete',
        confirmColor: 'error',
      };
    case 'edit':
      return {
        title: 'Edit Storyline',
        message: 'Are you sure you want to save these changes?',
        icon: <Edit color="primary" />,
        confirmText: 'Save',
        confirmColor: 'primary',
      };
    case 'add_article':
      return {
        title: 'Add Article to Storyline',
        message: `Add this article to "${storyline?.title}"?`,
        icon: <Add color="primary" />,
        confirmText: 'Add',
        confirmColor: 'primary',
      };
    default:
      return {
        title: 'Confirm Action',
        message: 'Are you sure you want to proceed?',
        icon: <WarningIcon color="warning" />,
        confirmText: 'Confirm',
        confirmColor: 'primary',
      };
    }
  };

  const actionDetails = getActionDetails();

  const handleConfirm = () => {
    onConfirm();
  };

  const handleClose = () => {
    if (!loading) {
      onClose();
    }
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      disableEscapeKeyDown={loading}
    >
      <DialogTitle>
        <Box display="flex" alignItems="center" gap={2}>
          {actionDetails.icon}
          <Typography variant="h6">
            {actionDetails.title}
          </Typography>
        </Box>
      </DialogTitle>

      <DialogContent>
        <Box sx={{ pt: 1 }}>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          <Typography variant="body1" color="text.primary">
            {actionDetails.message}
          </Typography>

          {storyline && action === 'delete' && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              <Typography variant="body2">
                <strong>Warning:</strong> This will permanently delete the storyline and all associated data.
              </Typography>
            </Alert>
          )}

          {storyline && action === 'add_article' && (
            <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
              <Typography variant="subtitle2" color="text.secondary">
                Storyline Details:
              </Typography>
              <Typography variant="body2" sx={{ mt: 1 }}>
                <strong>Title:</strong> {storyline.title}
              </Typography>
              {storyline.description && (
                <Typography variant="body2">
                  <strong>Description:</strong> {storyline.description}
                </Typography>
              )}
              <Typography variant="body2">
                <strong>Articles:</strong> {storyline.article_count || 0}
              </Typography>
            </Box>
          )}
        </Box>
      </DialogContent>

      <DialogActions sx={{ p: 2 }}>
        <Button
          onClick={handleClose}
          disabled={loading}
          color="inherit"
        >
          Cancel
        </Button>
        <Button
          onClick={handleConfirm}
          variant="contained"
          color={actionDetails.confirmColor}
          disabled={loading}
          startIcon={loading ? <CircularProgress size={20} /> : actionDetails.icon}
        >
          {loading ? 'Processing...' : actionDetails.confirmText}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default StorylineConfirmationDialog;
