import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  CircularProgress,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Divider,
  Badge
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Visibility as ViewIcon,
  Build as BuildIcon,
  AutoAwesome as AutoAwesomeIcon
} from '@mui/icons-material';
import RAGContextBuilder from './RAGContextBuilder';
import IntelligentTags from '../IntelligentTags/IntelligentTags';

const StoryThreadManager = ({ onRefresh }) => {
  const [threads, setThreads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [priorityLevels, setPriorityLevels] = useState([]);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingThread, setEditingThread] = useState(null);
  const [openRAGDialog, setOpenRAGDialog] = useState(false);
  const [selectedThread, setSelectedThread] = useState(null);
  const [openTagsDialog, setOpenTagsDialog] = useState(false);
  const [selectedThreadForTags, setSelectedThreadForTags] = useState(null);
  
  // Form state
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    category: '',
    priority_level: 'medium',
    keywords: []
  });
  
  const [keywordsInput, setKeywordsInput] = useState('');

  useEffect(() => {
    fetchThreads();
    fetchPriorityLevels();
  }, []);

  const fetchThreads = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/prioritization/story-threads');
      const data = await response.json();
      
      if (data.success) {
        setThreads(data.data);
      } else {
        setError(data.error);
      }
    } catch (err) {
      setError('Failed to fetch story threads');
    } finally {
      setLoading(false);
    }
  };

  const fetchPriorityLevels = async () => {
    try {
      const response = await fetch('/api/prioritization/priority-levels');
      const data = await response.json();
      
      if (data.success) {
        setPriorityLevels(data.data);
      }
    } catch (err) {
      console.error('Failed to fetch priority levels:', err);
    }
  };

  const handleOpenDialog = (thread = null) => {
    if (thread) {
      setEditingThread(thread);
      setFormData({
        title: thread.title,
        description: thread.description,
        category: thread.category,
        priority_level: thread.priority_level,
        keywords: thread.keywords || []
      });
      setKeywordsInput((thread.keywords || []).join(', '));
    } else {
      setEditingThread(null);
      setFormData({
        title: '',
        description: '',
        category: '',
        priority_level: 'medium',
        keywords: []
      });
      setKeywordsInput('');
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditingThread(null);
    setFormData({
      title: '',
      description: '',
      category: '',
      priority_level: 'medium',
      keywords: []
    });
    setKeywordsInput('');
  };

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleKeywordsChange = (value) => {
    const keywords = value.split(',').map(k => k.trim()).filter(k => k);
    setFormData(prev => ({
      ...prev,
      keywords
    }));
  };

  const handleSubmit = async () => {
    try {
      // Process keywords from input
      const keywords = keywordsInput.split(',').map(k => k.trim()).filter(k => k);
      const formDataWithKeywords = { ...formData, keywords };
      
      const url = editingThread 
        ? `/api/prioritization/story-threads/${editingThread.id}`
        : '/api/prioritization/story-threads';
      
      const method = editingThread ? 'PUT' : 'POST';
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formDataWithKeywords),
      });
      
      const data = await response.json();
      
      if (data.success) {
        handleCloseDialog();
        fetchThreads();
        onRefresh();
      } else {
        setError(data.error);
      }
    } catch (err) {
      setError('Failed to save story thread');
    }
  };

  const handleDeleteThread = async (threadId) => {
    if (window.confirm('Are you sure you want to delete this story thread? This action cannot be undone.')) {
      try {
        const response = await fetch(`/api/prioritization/story-threads/${threadId}`, {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
          },
        });
        
        const data = await response.json();
        
        if (data.success) {
          fetchThreads();
          onRefresh();
        } else {
          setError(data.error || 'Failed to delete story thread');
        }
      } catch (err) {
        setError('Failed to delete story thread');
      }
    }
  };

  const handleOpenRAGDialog = (thread) => {
    setSelectedThread(thread);
    setOpenRAGDialog(true);
  };

  const handleCloseRAGDialog = () => {
    setOpenRAGDialog(false);
    setSelectedThread(null);
  };

  const handleOpenTagsDialog = (thread) => {
    setSelectedThreadForTags(thread);
    setOpenTagsDialog(true);
  };

  const handleCloseTagsDialog = () => {
    setOpenTagsDialog(false);
    setSelectedThreadForTags(null);
  };

  const getPriorityColor = (priorityLevel) => {
    const level = priorityLevels.find(l => l.name === priorityLevel);
    return level?.color_hex || '#666';
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5">
          Story Threads ({threads.length})
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => handleOpenDialog()}
        >
          New Story Thread
        </Button>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Threads List */}
      <Grid container spacing={3}>
        {threads.map((thread) => (
          <Grid item xs={12} md={6} key={thread.id}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                  <Box sx={{ flex: 1 }}>
                    <Typography variant="h6" gutterBottom>
                      {thread.title}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      {thread.description}
                    </Typography>
                  </Box>
                  <Chip
                    label={thread.priority_level}
                    size="small"
                    style={{ backgroundColor: getPriorityColor(thread.priority_level), color: 'white' }}
                  />
                </Box>
                
                <Box sx={{ mb: 2 }}>
                  <Chip
                    label={thread.category}
                    size="small"
                    variant="outlined"
                    sx={{ mr: 1 }}
                  />
                  <Chip
                    label={thread.status}
                    size="small"
                    variant="outlined"
                    color={thread.status === 'active' ? 'success' : 'default'}
                  />
                </Box>
                
                {thread.keywords && thread.keywords.length > 0 && (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
                      Keywords:
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {thread.keywords.map((keyword, index) => (
                        <Chip
                          key={index}
                          label={keyword}
                          size="small"
                          variant="outlined"
                        />
                      ))}
                    </Box>
                  </Box>
                )}
                
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="caption" color="text.secondary">
                    Created: {new Date(thread.created_at).toLocaleDateString()}
                  </Typography>
                  
                  <Box>
                    <IconButton
                      size="small"
                      onClick={() => handleOpenRAGDialog(thread)}
                      title="Build RAG Context"
                    >
                      <BuildIcon />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => handleOpenTagsDialog(thread)}
                      title="Intelligent Tags"
                    >
                      <AutoAwesomeIcon />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => handleOpenDialog(thread)}
                      title="Edit Thread"
                    >
                      <EditIcon />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => handleDeleteThread(thread.id)}
                      title="Delete Thread"
                      color="error"
                    >
                      <DeleteIcon />
                    </IconButton>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Create/Edit Dialog */}
      <Dialog open={openDialog} onClose={handleCloseDialog} maxWidth="md" fullWidth>
        <DialogTitle>
          {editingThread ? 'Edit Story Thread' : 'Create New Story Thread'}
        </DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Title"
                value={formData.title}
                onChange={(e) => handleInputChange('title', e.target.value)}
                required
              />
            </Grid>
            
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Description"
                value={formData.description}
                onChange={(e) => handleInputChange('description', e.target.value)}
                multiline
                rows={3}
                required
              />
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Category"
                value={formData.category}
                onChange={(e) => handleInputChange('category', e.target.value)}
                required
              />
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Priority Level</InputLabel>
                <Select
                  value={formData.priority_level}
                  label="Priority Level"
                  onChange={(e) => handleInputChange('priority_level', e.target.value)}
                >
                  {priorityLevels.map((level) => (
                    <MenuItem key={level.name} value={level.name}>
                      {level.name.charAt(0).toUpperCase() + level.name.slice(1)}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Keywords (comma-separated)"
                value={keywordsInput}
                onChange={(e) => setKeywordsInput(e.target.value)}
                helperText="Enter keywords separated by commas to help identify related articles"
                placeholder="e.g., Ukraine, Russia, conflict, war, politics"
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button onClick={handleSubmit} variant="contained">
            {editingThread ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* RAG Context Dialog */}
      <Dialog open={openRAGDialog} onClose={handleCloseRAGDialog} maxWidth="lg" fullWidth>
        <DialogTitle>
          RAG Context Builder - {selectedThread?.title}
        </DialogTitle>
        <DialogContent>
          {selectedThread && (
            <RAGContextBuilder thread={selectedThread} onClose={handleCloseRAGDialog} />
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseRAGDialog}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Intelligent Tags Dialog */}
      {openTagsDialog && selectedThreadForTags && (
        <Dialog
          open={openTagsDialog}
          onClose={handleCloseTagsDialog}
          maxWidth="lg"
          fullWidth
        >
          <DialogTitle>
            <Box display="flex" alignItems="center" gap={1}>
              <AutoAwesomeIcon color="primary" />
              Intelligent Tags - {selectedThreadForTags.title}
            </Box>
          </DialogTitle>
          <DialogContent>
            <IntelligentTags 
              threadId={selectedThreadForTags.id}
              onTagsUpdated={() => {
                // Refresh threads when tags are updated
                fetchThreads();
              }}
            />
          </DialogContent>
          <DialogActions>
            <Button onClick={handleCloseTagsDialog}>Close</Button>
          </DialogActions>
        </Dialog>
      )}
    </Box>
  );
};

export default StoryThreadManager;
