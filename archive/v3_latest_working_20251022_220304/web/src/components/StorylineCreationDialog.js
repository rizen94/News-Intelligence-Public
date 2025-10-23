import { Add, Close as CloseIcon } from '@mui/icons-material';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Box,
  Typography,
  Alert,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Stack,
} from '@mui/material';
import React, { useState } from 'react';

import apiService from '../services/apiService';
import Logger from '../utils/logger';

const StorylineCreationDialog = ({
  open,
  onClose,
  onSuccess,
  articleId = null,
  articleTitle = null,
}) => {
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    priority: 'medium',
    tags: [],
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [newTag, setNewTag] = useState('');

  const priorityOptions = [
    { value: 'low', label: 'Low', color: 'success' },
    { value: 'medium', label: 'Medium', color: 'warning' },
    { value: 'high', label: 'High', color: 'error' },
  ];

  const handleInputChange = (field) => (event) => {
    setFormData(prev => ({
      ...prev,
      [field]: event.target.value,
    }));
    setError(null);
  };

  const handleAddTag = () => {
    if (newTag.trim() && !formData.tags.includes(newTag.trim())) {
      setFormData(prev => ({
        ...prev,
        tags: [...prev.tags, newTag.trim()],
      }));
      setNewTag('');
    }
  };

  const handleRemoveTag = (tagToRemove) => {
    setFormData(prev => ({
      ...prev,
      tags: prev.tags.filter(tag => tag !== tagToRemove),
    }));
  };

  const handleKeyPress = (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      handleAddTag();
    }
  };

  const handleSubmit = async() => {
    if (!formData.title.trim()) {
      setError('Please enter a storyline title');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const storylineData = {
        title: formData.title.trim(),
        description: formData.description.trim() || `Storyline created${articleTitle ? ` from article: ${articleTitle}` : ''}`,
        priority: formData.priority,
        tags: formData.tags,
        created_by: 'user',
      };

      const response = await apiService.post('/api/storylines', storylineData);

      if (response.success) {
        setSuccess(true);
        setTimeout(() => {
          handleClose();
          onSuccess?.(response.data.storyline);
        }, 1500);
      } else {
        throw new Error(response.message || 'Failed to create storyline');
      }
    } catch (err) {
      Logger.error('Error creating storyline:', err);
      setError(err.message || 'Failed to create storyline. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setFormData({
        title: '',
        description: '',
        priority: 'medium',
        tags: [],
      });
      setError(null);
      setSuccess(false);
      setNewTag('');
      onClose();
    }
  };

  const isFormValid = formData.title.trim().length > 0;

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      disableEscapeKeyDown={loading}
    >
      <DialogTitle>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">
            {articleId ? 'Create New Storyline' : 'Add New Storyline'}
          </Typography>
          <Button
            onClick={handleClose}
            disabled={loading}
            sx={{ minWidth: 'auto', p: 1 }}
          >
            <CloseIcon />
          </Button>
        </Box>
      </DialogTitle>

      <DialogContent>
        <Box sx={{ pt: 2 }}>
          {articleTitle && (
            <Alert severity="info" sx={{ mb: 2 }}>
              Creating storyline from article: <strong>{articleTitle}</strong>
            </Alert>
          )}

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          {success && (
            <Alert severity="success" sx={{ mb: 2 }}>
              Storyline created successfully! Redirecting...
            </Alert>
          )}

          <TextField
            fullWidth
            label="Storyline Title"
            value={formData.title}
            onChange={handleInputChange('title')}
            placeholder="Enter a descriptive title for your storyline"
            margin="normal"
            required
            disabled={loading}
            autoFocus
          />

          <TextField
            fullWidth
            label="Description"
            value={formData.description}
            onChange={handleInputChange('description')}
            placeholder="Describe what this storyline is about..."
            margin="normal"
            multiline
            rows={3}
            disabled={loading}
          />

          <FormControl fullWidth margin="normal">
            <InputLabel>Priority Level</InputLabel>
            <Select
              value={formData.priority}
              onChange={handleInputChange('priority')}
              label="Priority Level"
              disabled={loading}
            >
              {priorityOptions.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  <Box display="flex" alignItems="center" gap={1}>
                    <Chip
                      label={option.label}
                      size="small"
                      color={option.color}
                      variant="outlined"
                    />
                  </Box>
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Tags (Optional)
            </Typography>
            <Box display="flex" gap={1} mb={1}>
              <TextField
                size="small"
                placeholder="Add a tag..."
                value={newTag}
                onChange={(e) => setNewTag(e.target.value)}
                onKeyPress={handleKeyPress}
                disabled={loading}
                sx={{ flexGrow: 1 }}
              />
              <Button
                variant="outlined"
                onClick={handleAddTag}
                disabled={!newTag.trim() || loading}
                startIcon={<Add />}
              >
                Add
              </Button>
            </Box>
            {formData.tags.length > 0 && (
              <Stack direction="row" spacing={1} flexWrap="wrap" gap={1}>
                {formData.tags.map((tag) => (
                  <Chip
                    key={tag}
                    label={tag}
                    onDelete={() => handleRemoveTag(tag)}
                    disabled={loading}
                    size="small"
                  />
                ))}
              </Stack>
            )}
          </Box>
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
          onClick={handleSubmit}
          variant="contained"
          disabled={!isFormValid || loading}
          startIcon={loading ? <CircularProgress size={20} /> : <Add />}
        >
          {loading ? 'Creating...' : 'Create Storyline'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default StorylineCreationDialog;
