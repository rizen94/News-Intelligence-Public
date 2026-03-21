import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography,
  Alert,
  CircularProgress,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Divider,
  Card,
  CardContent,
  CardActions,
  Tooltip,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Close as CloseIcon,
  Search as SearchIcon,
} from '@mui/icons-material';
import apiService from '../services/apiService';

const StorylineManagementDialog = ({
  open,
  onClose,
  storyline = null,
  domain,
  onStorylineUpdated,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Form state
  const [formData, setFormData] = useState({
    title: '',
    description: '',
  });

  // Article management state
  const [articles, setArticles] = useState([]);
  const [availableArticles, setAvailableArticles] = useState([]);
  const [showAddArticles, setShowAddArticles] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedArticles, setSelectedArticles] = useState([]);

  useEffect(() => {
    if (open) {
      if (storyline) {
        // Editing existing storyline
        setFormData({
          title: storyline.title || '',
          description: storyline.description || '',
        });
        loadStorylineArticles();
      } else {
        // Creating new storyline
        setFormData({ title: '', description: '' });
        setArticles([]);
      }
      setError(null);
      setSuccess(null);
    }
  }, [open, storyline, domain]);

  const loadStorylineArticles = async () => {
    if (!storyline?.id) return;

    try {
      setLoading(true);
      const response = await apiService.getStoryline(storyline.id, domain);
      if (response?.error) return;
      // Handle both formats: wrapped { success, data: { articles } } and direct { id, articles }
      const articlesList = response?.data?.articles ?? response?.articles ?? [];
      setArticles(Array.isArray(articlesList) ? articlesList : []);
    } catch (err) {
      console.error('Error loading storyline articles:', err);
      setError('Failed to load storyline articles');
    } finally {
      setLoading(false);
    }
  };

  const loadAvailableArticles = async () => {
    if (!storyline?.id) return;

    try {
      setLoading(true);
      const response = await apiService.getAvailableArticles(
        storyline.id,
        {},
        domain
      );
      if (response?.error) return;
      const articlesList = response?.data?.articles ?? response?.articles ?? [];
      setAvailableArticles(Array.isArray(articlesList) ? articlesList : []);
    } catch (err) {
      console.error('Error loading available articles:', err);
      setError('Failed to load available articles');
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleCreateStoryline = async () => {
    if (!formData.title.trim()) {
      setError('Title is required');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      let response;
      if (storyline?.id) {
        // Update existing storyline
        response = await apiService.updateStoryline(storyline.id, formData, domain);
      } else {
        // Create new storyline
        response = await apiService.createStoryline(formData, domain);
      }

      if (response.success) {
        const action = storyline?.id ? 'updated' : 'created';
        setSuccess(`Storyline ${action} successfully!`);
        setTimeout(() => {
          onStorylineUpdated();
          onClose();
        }, 1500);
      } else {
        setError(
          response.message ||
            `Failed to ${storyline?.id ? 'update' : 'create'} storyline`
        );
      }
    } catch (err) {
      console.error(
        `Error ${storyline?.id ? 'updating' : 'creating'} storyline:`,
        err
      );
      setError(`Failed to ${storyline?.id ? 'update' : 'create'} storyline`);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteStoryline = async () => {
    if (!storyline?.id) return;

    if (
      !window.confirm(
        `Are you sure you want to delete "${storyline.title}"? This action cannot be undone.`
      )
    ) {
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await apiService.deleteStoryline(storyline.id, domain);
      if (response.success) {
        setSuccess('Storyline deleted successfully!');
        setTimeout(() => {
          onStorylineUpdated();
          onClose();
        }, 1500);
      } else {
        setError(
          response.message ||
            response.error ||
            'Failed to delete storyline'
        );
      }
    } catch (err) {
      console.error('Error deleting storyline:', err);
      setError('Failed to delete storyline');
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveArticle = async articleId => {
    if (!storyline?.id) return;

    try {
      setLoading(true);
      setError(null);

      const response = await apiService.removeArticleFromStoryline(
        storyline.id,
        articleId,
        domain
      );
      if (response.success) {
        setArticles(prev => prev.filter(article => article.id !== articleId));
        setSuccess('Article removed from storyline');
        setTimeout(() => setSuccess(null), 3000);
      } else {
        setError(response.message || 'Failed to remove article');
      }
    } catch (err) {
      console.error('Error removing article:', err);
      setError('Failed to remove article');
    } finally {
      setLoading(false);
    }
  };

  const handleAddSelectedArticles = async () => {
    if (!storyline?.id || selectedArticles.length === 0) return;

    try {
      setLoading(true);
      setError(null);

      const promises = selectedArticles.map(articleId =>
        apiService.addArticleToStoryline(storyline.id, articleId, domain)
      );

      await Promise.all(promises);

      setSuccess(`${selectedArticles.length} articles added to storyline`);
      setSelectedArticles([]);
      setShowAddArticles(false);

      // Reload articles
      await loadStorylineArticles();

      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      console.error('Error adding articles:', err);
      setError('Failed to add articles');
    } finally {
      setLoading(false);
    }
  };

  const filteredAvailableArticles = availableArticles.filter(
    article =>
      article.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      article.source_domain.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const isEditing = !!storyline;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth='md'
      fullWidth
      PaperProps={{
        sx: { minHeight: '600px' },
      }}
    >
      <DialogTitle>
        <Box display='flex' justifyContent='space-between' alignItems='center'>
          <Typography variant='h6'>
            {isEditing ? `Manage "${storyline.title}"` : 'Create New Storyline'}
          </Typography>
          <IconButton onClick={onClose} size='small'>
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent>
        {error && (
          <Alert severity='error' sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {success && (
          <Alert
            severity='success'
            sx={{ mb: 2 }}
            onClose={() => setSuccess(null)}
          >
            {success}
          </Alert>
        )}

        {/* Storyline Form */}
        <Box sx={{ mb: 3 }}>
          <TextField
            fullWidth
            label='Storyline Title'
            value={formData.title}
            onChange={e => handleInputChange('title', e.target.value)}
            disabled={loading}
            sx={{ mb: 2 }}
            required
          />

          <TextField
            fullWidth
            label='Description'
            value={formData.description}
            onChange={e => handleInputChange('description', e.target.value)}
            disabled={loading}
            multiline
            rows={3}
          />
        </Box>

        {/* Article Management */}
        {isEditing && (
          <Box>
            <Box
              display='flex'
              justifyContent='space-between'
              alignItems='center'
              sx={{ mb: 2 }}
            >
              <Typography variant='h6'>Articles ({articles.length})</Typography>
              <Button
                variant='outlined'
                startIcon={<AddIcon />}
                onClick={() => {
                  setShowAddArticles(true);
                  loadAvailableArticles();
                }}
                disabled={loading}
              >
                Add Articles
              </Button>
            </Box>

            {/* Current Articles */}
            <Card sx={{ mb: 2 }}>
              <CardContent>
                {articles.length === 0 ? (
                  <Typography color='text.secondary' textAlign='center' py={2}>
                    No articles in this storyline
                  </Typography>
                ) : (
                  <List dense>
                    {articles.map((article, index) => (
                      <React.Fragment key={article.id}>
                        <ListItem>
                          <ListItemText
                            primary={article.title}
                            secondary={`${article.source_domain} • ${new Date(
                              article.published_at
                            ).toLocaleDateString()}`}
                          />
                          <ListItemSecondaryAction>
                            <Tooltip title='Remove from storyline'>
                              <IconButton
                                edge='end'
                                onClick={() => handleRemoveArticle(article.id)}
                                disabled={loading}
                                color='error'
                                size='small'
                              >
                                <DeleteIcon />
                              </IconButton>
                            </Tooltip>
                          </ListItemSecondaryAction>
                        </ListItem>
                        {index < articles.length - 1 && <Divider />}
                      </React.Fragment>
                    ))}
                  </List>
                )}
              </CardContent>
            </Card>

            {/* Add Articles Section */}
            {showAddArticles && (
              <Card>
                <CardContent>
                  <Box
                    display='flex'
                    justifyContent='space-between'
                    alignItems='center'
                    sx={{ mb: 2 }}
                  >
                    <Typography variant='h6'>
                      Add Articles ({selectedArticles.length} selected)
                    </Typography>
                    <Button
                      variant='outlined'
                      onClick={() => setShowAddArticles(false)}
                      size='small'
                    >
                      Cancel
                    </Button>
                  </Box>

                  <TextField
                    fullWidth
                    placeholder='Search articles...'
                    value={searchTerm}
                    onChange={e => setSearchTerm(e.target.value)}
                    InputProps={{
                      startAdornment: (
                        <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />
                      ),
                    }}
                    sx={{ mb: 2 }}
                  />

                  <Box sx={{ maxHeight: '300px', overflow: 'auto' }}>
                    {filteredAvailableArticles.length === 0 ? (
                      <Typography
                        color='text.secondary'
                        textAlign='center'
                        py={2}
                      >
                        No available articles found
                      </Typography>
                    ) : (
                      <List dense>
                        {filteredAvailableArticles.map((article, index) => (
                          <React.Fragment key={article.id}>
                            <ListItem>
                              <ListItemText
                                primary={article.title}
                                secondary={`${
                                  article.source_domain
                                } • ${new Date(
                                  article.published_at
                                ).toLocaleDateString()}`}
                              />
                              <ListItemSecondaryAction>
                                <Button
                                  variant={
                                    selectedArticles.includes(article.id)
                                      ? 'contained'
                                      : 'outlined'
                                  }
                                  size='small'
                                  onClick={() => {
                                    setSelectedArticles(prev =>
                                      prev.includes(article.id)
                                        ? prev.filter(id => id !== article.id)
                                        : [...prev, article.id]
                                    );
                                  }}
                                >
                                  {selectedArticles.includes(article.id)
                                    ? 'Selected'
                                    : 'Select'}
                                </Button>
                              </ListItemSecondaryAction>
                            </ListItem>
                            {index < filteredAvailableArticles.length - 1 && (
                              <Divider />
                            )}
                          </React.Fragment>
                        ))}
                      </List>
                    )}
                  </Box>
                </CardContent>
                <CardActions>
                  <Button
                    variant='contained'
                    onClick={handleAddSelectedArticles}
                    disabled={loading || selectedArticles.length === 0}
                    startIcon={<AddIcon />}
                  >
                    Add {selectedArticles.length} Articles
                  </Button>
                </CardActions>
              </Card>
            )}
          </Box>
        )}
      </DialogContent>

      <DialogActions>
        {isEditing && (
          <Button
            color='error'
            onClick={handleDeleteStoryline}
            disabled={loading}
            startIcon={<DeleteIcon />}
          >
            Delete Storyline
          </Button>
        )}

        <Box sx={{ flexGrow: 1 }} />

        <Button onClick={onClose} disabled={loading}>
          Cancel
        </Button>

        <Button
          variant='contained'
          onClick={handleCreateStoryline}
          disabled={loading || !formData.title.trim()}
          startIcon={loading ? <CircularProgress size={20} /> : <AddIcon />}
        >
          {isEditing ? 'Update Storyline' : 'Create Storyline'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default StorylineManagementDialog;
