import React, { useState, useEffect } from 'react';
import {
  Box,
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
  Paper,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Tabs,
  Tab,
  Grid,
  Tooltip,
  Badge,
  SpeedDial,
  SpeedDialAction,
  SpeedDialIcon
} from '@mui/material';
import {
  Bookmark as BookmarkIcon,
  BookmarkBorder as BookmarkBorderIcon,
  Share as ShareIcon,
  Edit as EditIcon,
  Tag as TagIcon,
  PriorityHigh as PriorityIcon,
  Timeline as TimelineIcon,
  Build as BuildIcon,
  Close as CloseIcon,
  ArrowBack as ArrowBackIcon,
  ArrowForward as ArrowForwardIcon,
  OpenInNew as OpenInNewIcon,
  ContentCopy as CopyIcon,
  Print as PrintIcon,
  Download as DownloadIcon
} from '@mui/icons-material';

const ArticleViewer = ({ article, onClose, onNavigate, onUpdate }) => {
  const [activeTab, setActiveTab] = useState(0);
  const [priorityDialog, setPriorityDialog] = useState(false);
  const [tagDialog, setTagDialog] = useState(false);
  const [ragDialog, setRagDialog] = useState(false);
  const [createThreadDialog, setCreateThreadDialog] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [priorityLevels, setPriorityLevels] = useState([]);
  const [storyThreads, setStoryThreads] = useState([]);
  
  // Form states
  const [priorityForm, setPriorityForm] = useState({
    priority_level: 'medium',
    reasoning: '',
    thread_id: null
  });
  
  const [tagForm, setTagForm] = useState({
    tags: [],
    notes: '',
    category: ''
  });
  
  const [ragForm, setRagForm] = useState({
    context_type: 'historical',
    max_articles: 10
  });
  
  const [threadForm, setThreadForm] = useState({
    title: '',
    description: '',
    category: '',
    priority_level: 'medium',
    keywords: []
  });
  
  const [keywordsInput, setKeywordsInput] = useState('');

  useEffect(() => {
    if (article) {
      fetchPriorityLevels();
      fetchStoryThreads();
      loadArticleData();
    }
  }, [article]);

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

  const fetchStoryThreads = async () => {
    try {
      const response = await fetch('/api/prioritization/story-threads?status=active');
      const data = await response.json();
      if (data.success) {
        setStoryThreads(data.data);
      }
    } catch (err) {
      console.error('Failed to fetch story threads:', err);
    }
  };

  const loadArticleData = async () => {
    // Load existing article data like tags, notes, priority
    // This would fetch from the database
  };

  const handlePrioritySubmit = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const priorityLevel = priorityLevels.find(p => p.name === priorityForm.priority_level);
      if (!priorityLevel) {
        setError('Please select a valid priority level');
        return;
      }
      
      const response = await fetch(`/api/prioritization/articles/${article.id}/priority`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          priority_level_id: priorityLevel.id,
          thread_id: priorityForm.thread_id || null,
          reasoning: priorityForm.reasoning
        }),
      });
      
      const result = await response.json();
      
      if (response.ok && result.success) {
        setPriorityDialog(false);
        onUpdate && onUpdate();
        // Reset form
        setPriorityForm({
          priority_level: 'medium',
          reasoning: '',
          thread_id: null
        });
      } else {
        setError(result.error || 'Failed to update priority');
      }
    } catch (err) {
      console.error('Priority update error:', err);
      setError('Failed to update priority: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleTagSubmit = async () => {
    try {
      setLoading(true);
      // Save tags and notes to database
      // This would be a new API endpoint
      setTagDialog(false);
      onUpdate && onUpdate();
    } catch (err) {
      setError('Failed to save tags');
    } finally {
      setLoading(false);
    }
  };

  const handleRAGBuild = async () => {
    try {
      setLoading(true);
      setError(null);
      
      if (!ragForm.thread_id) {
        setError('Please select a story thread or create a new one first');
        return;
      }
      
      const response = await fetch(`/api/prioritization/rag-context/${ragForm.thread_id}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          context_type: ragForm.context_type,
          max_articles: ragForm.max_articles,
          article_id: article.id
        }),
      });
      
      const result = await response.json();
      
      if (response.ok && result.success) {
        setRagDialog(false);
        // Show RAG results - could display in a new dialog or section
        console.log('RAG context built successfully:', result.data);
      } else {
        setError(result.error || 'Failed to build RAG context');
      }
    } catch (err) {
      console.error('RAG build error:', err);
      setError('Failed to build RAG context: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateThread = async () => {
    try {
      setLoading(true);
      setError(null);
      
      if (!threadForm.title || !threadForm.description || !threadForm.category) {
        setError('Please fill in all required fields');
        return;
      }
      
      // Process keywords from input
      const keywords = keywordsInput.split(',').map(k => k.trim()).filter(k => k);
      const formDataWithKeywords = { ...threadForm, keywords };
      
      const response = await fetch('/api/prioritization/story-threads', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formDataWithKeywords),
      });
      
      const result = await response.json();
      
      if (response.ok && result.success) {
        setCreateThreadDialog(false);
        // Reset form
        setThreadForm({
          title: '',
          description: '',
          category: '',
          priority_level: 'medium',
          keywords: []
        });
        setKeywordsInput('');
        // Refresh story threads list
        fetchStoryThreads();
        // Auto-select the newly created thread
        setRagForm(prev => ({ ...prev, thread_id: result.data.id }));
        setError(null);
      } else {
        setError(result.error || 'Failed to create story thread');
      }
    } catch (err) {
      console.error('Create thread error:', err);
      setError('Failed to create story thread: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const getPriorityColor = (priority) => {
    const level = priorityLevels.find(p => p.name === priority);
    return level?.color_hex || '#666';
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown date';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    // Show success message
  };

  const printArticle = () => {
    const printWindow = window.open('', '_blank');
    printWindow.document.write(`
      <html>
        <head>
          <title>${article.title}</title>
          <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; margin: 20px; }
            h1 { color: #333; border-bottom: 2px solid #eee; padding-bottom: 10px; }
            .meta { color: #666; margin-bottom: 20px; }
            .content { line-height: 1.8; }
          </style>
        </head>
        <body>
          <h1>${article.title}</h1>
          <div class="meta">
            <strong>Source:</strong> ${article.source}<br>
            <strong>Published:</strong> ${formatDate(article.published_date)}<br>
            <strong>Category:</strong> ${article.category || 'Uncategorized'}
          </div>
          <div class="content">${article.content}</div>
        </body>
      </html>
    `);
    printWindow.document.close();
    printWindow.print();
  };

  if (!article) return null;

  return (
    <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Paper elevation={2} sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <IconButton onClick={onClose} size="large">
              <ArrowBackIcon />
            </IconButton>
            <Typography variant="h5" noWrap sx={{ maxWidth: '600px' }}>
              {article.title}
            </Typography>
          </Box>
          
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title="Bookmark">
              <IconButton>
                <BookmarkBorderIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="Share">
              <IconButton>
                <ShareIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="Print">
              <IconButton onClick={printArticle}>
                <PrintIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="Copy Link">
              <IconButton onClick={() => copyToClipboard(article.url)}>
                <CopyIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="Open Original">
              <IconButton onClick={() => window.open(article.url, '_blank')}>
                <OpenInNewIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>
        
        {/* Article Meta */}
        <Box sx={{ mt: 2, display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
          <Chip 
            label={article.source} 
            size="small" 
            variant="outlined" 
            color="primary"
          />
          <Chip 
            label={article.category || 'Uncategorized'} 
            size="small" 
            variant="outlined"
          />
          <Typography variant="caption" color="text.secondary">
            {formatDate(article.published_date)}
          </Typography>
          {article.deduplication_status && (
            <Chip 
              label={article.deduplication_status} 
              size="small" 
              color={article.deduplication_status === 'unique' ? 'success' : 'warning'}
            />
          )}
        </Box>
      </Paper>

      {/* Content Tabs */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <Tabs value={activeTab} onChange={(e, newValue) => setActiveTab(newValue)}>
          <Tab label="Article" />
          <Tab label="Analysis" />
          <Tab label="Tags & Notes" />
          <Tab label="RAG Context" />
        </Tabs>
        
        <Box sx={{ flex: 1, overflow: 'auto', p: 3 }}>
          {activeTab === 0 && (
            <Box>
              {/* Article Content */}
              <Paper elevation={1} sx={{ p: 3, mb: 3 }}>
                <Typography variant="body1" sx={{ lineHeight: 1.8, fontSize: '1.1rem' }}>
                  {article.content}
                </Typography>
              </Paper>
              
              {/* Quick Actions */}
              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                <Button
                  variant="outlined"
                  startIcon={<PriorityIcon />}
                  onClick={() => setPriorityDialog(true)}
                >
                  Set Priority
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<TagIcon />}
                  onClick={() => setTagDialog(true)}
                >
                  Add Tags
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<TimelineIcon />}
                  onClick={() => setRagDialog(true)}
                >
                  Build RAG Context
                </Button>
              </Box>
            </Box>
          )}
          
          {activeTab === 1 && (
            <Box>
              <Typography variant="h6" gutterBottom>
                Content Analysis
              </Typography>
              <Grid container spacing={3}>
                <Grid item xs={12} md={6}>
                  <Card>
                    <CardContent>
                      <Typography variant="subtitle1" gutterBottom>
                        Content Statistics
                      </Typography>
                      <List dense>
                        <ListItem>
                          <ListItemText
                            primary="Word Count"
                            secondary={article.content?.split(' ').length || 0}
                          />
                        </ListItem>
                        <ListItem>
                          <ListItemText
                            primary="Character Count"
                            secondary={article.content?.length || 0}
                          />
                        </ListItem>
                        <ListItem>
                          <ListItemText
                            primary="Reading Time"
                            secondary={`${Math.ceil((article.content?.split(' ').length || 0) / 200)} minutes`}
                          />
                        </ListItem>
                      </List>
                    </CardContent>
                  </Card>
                </Grid>
                
                <Grid item xs={12} md={6}>
                  <Card>
                    <CardContent>
                      <Typography variant="subtitle1" gutterBottom>
                        Priority Information
                      </Typography>
                      <List dense>
                        <ListItem>
                          <ListItemText
                            primary="Current Priority"
                            secondary={article.priority_level || 'Not set'}
                          />
                        </ListItem>
                        <ListItem>
                          <ListItemText
                            primary="Story Thread"
                            secondary={article.thread_id ? 'Assigned' : 'Not assigned'}
                          />
                        </ListItem>
                      </List>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
            </Box>
          )}
          
          {activeTab === 2 && (
            <Box>
              <Typography variant="h6" gutterBottom>
                Tags & Notes
              </Typography>
              <Card sx={{ mb: 3 }}>
                <CardContent>
                  <Typography variant="subtitle1" gutterBottom>
                    Current Tags
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                    {tagForm.tags.map((tag, index) => (
                      <Chip
                        key={index}
                        label={tag}
                        onDelete={() => {
                          const newTags = tagForm.tags.filter((_, i) => i !== index);
                          setTagForm(prev => ({ ...prev, tags: newTags }));
                        }}
                      />
                    ))}
                  </Box>
                  
                  <Button
                    variant="outlined"
                    startIcon={<TagIcon />}
                    onClick={() => setTagDialog(true)}
                  >
                    Edit Tags & Notes
                  </Button>
                </CardContent>
              </Card>
            </Box>
          )}
          
          {activeTab === 3 && (
            <Box>
              <Typography variant="h6" gutterBottom>
                RAG Context Builder
              </Typography>
              <Card>
                <CardContent>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Build contextual information around this article to enhance your understanding
                    and create connections with related content.
                  </Typography>
                  
                  <Button
                    variant="contained"
                    startIcon={<BuildIcon />}
                    onClick={() => setRagDialog(true)}
                  >
                    Build RAG Context
                  </Button>
                </CardContent>
              </Card>
            </Box>
          )}
        </Box>
      </Box>

      {/* Priority Dialog */}
      <Dialog open={priorityDialog} onClose={() => setPriorityDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Set Article Priority</DialogTitle>
        <DialogContent>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <FormControl fullWidth>
                <InputLabel>Priority Level</InputLabel>
                <Select
                  value={priorityForm.priority_level}
                  label="Priority Level"
                  onChange={(e) => setPriorityForm(prev => ({ ...prev, priority_level: e.target.value }))}
                >
                  {priorityLevels.map((level) => (
                    <MenuItem key={level.name} value={level.name}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Box
                          sx={{
                            width: 16,
                            height: 16,
                            borderRadius: '50%',
                            backgroundColor: level.color_hex
                          }}
                        />
                        {level.name.charAt(0).toUpperCase() + level.name.slice(1)}
                      </Box>
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12}>
              <FormControl fullWidth>
                <InputLabel>Story Thread</InputLabel>
                <Select
                  value={priorityForm.thread_id || ''}
                  label="Story Thread"
                  onChange={(e) => setPriorityForm(prev => ({ ...prev, thread_id: e.target.value }))}
                >
                  <MenuItem value="">No thread</MenuItem>
                  {storyThreads.map((thread) => (
                    <MenuItem key={thread.id} value={thread.id}>
                      {thread.title}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Reasoning"
                value={priorityForm.reasoning}
                onChange={(e) => setPriorityForm(prev => ({ ...prev, reasoning: e.target.value }))}
                multiline
                rows={3}
                helperText="Explain why you're setting this priority level"
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPriorityDialog(false)}>Cancel</Button>
          <Button onClick={handlePrioritySubmit} variant="contained" disabled={loading}>
            {loading ? <CircularProgress size={20} /> : 'Set Priority'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Tag Dialog */}
      <Dialog open={tagDialog} onClose={() => setTagDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add Tags & Notes</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Tags (comma-separated)"
                value={tagForm.tags.join(', ')}
                onChange={(e) => {
                  const tags = e.target.value.split(',').map(t => t.trim()).filter(t => t);
                  setTagForm(prev => ({ ...prev, tags }));
                }}
                helperText="Enter tags separated by commas"
              />
            </Grid>
            
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Notes"
                value={tagForm.notes}
                onChange={(e) => setTagForm(prev => ({ ...prev, notes: e.target.value }))}
                multiline
                rows={4}
                helperText="Add your personal notes about this article"
              />
            </Grid>
            
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Category Override"
                value={tagForm.category}
                onChange={(e) => setTagForm(prev => ({ ...prev, category: e.target.value }))}
                helperText="Override the default category if needed"
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setTagDialog(false)}>Cancel</Button>
          <Button onClick={handleTagSubmit} variant="contained" disabled={loading}>
            {loading ? <CircularProgress size={20} /> : 'Save Tags'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* RAG Dialog */}
      <Dialog open={ragDialog} onClose={() => setRagDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle>Build RAG Context</DialogTitle>
        <DialogContent>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Context Type</InputLabel>
                <Select
                  value={ragForm.context_type}
                  label="Context Type"
                  onChange={(e) => setRagForm(prev => ({ ...prev, context_type: e.target.value }))}
                >
                  <MenuItem value="historical">Historical Context</MenuItem>
                  <MenuItem value="related">Related Content</MenuItem>
                  <MenuItem value="background">Background Info</MenuItem>
                  <MenuItem value="timeline">Timeline</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Max Articles</InputLabel>
                <Select
                  value={ragForm.max_articles}
                  label="Max Articles"
                  onChange={(e) => setRagForm(prev => ({ ...prev, max_articles: e.target.value }))}
                >
                  <MenuItem value={5}>5 articles</MenuItem>
                  <MenuItem value={10}>10 articles</MenuItem>
                  <MenuItem value={20}>20 articles</MenuItem>
                  <MenuItem value={50}>50 articles</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12}>
              <FormControl fullWidth>
                <InputLabel>Story Thread</InputLabel>
                <Select
                  value={ragForm.thread_id || ''}
                  label="Story Thread"
                  onOpen={() => {
                    // Refresh story threads every time dropdown is opened
                    fetchStoryThreads();
                  }}
                  onChange={(e) => {
                    if (e.target.value === 'create_new') {
                      // Open story thread creation dialog
                      setCreateThreadDialog(true);
                    } else {
                      setRagForm(prev => ({ ...prev, thread_id: e.target.value }));
                    }
                  }}
                >
                  <MenuItem value="">Select existing thread</MenuItem>
                  <MenuItem value="create_new">Create new thread</MenuItem>
                  {storyThreads.map((thread) => (
                    <MenuItem key={thread.id} value={thread.id}>
                      {thread.title}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRagDialog(false)}>Cancel</Button>
          <Button onClick={handleRAGBuild} variant="contained" disabled={loading}>
            {loading ? <CircularProgress size={20} /> : 'Build Context'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Create Thread Dialog */}
      <Dialog open={createThreadDialog} onClose={() => setCreateThreadDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create New Story Thread</DialogTitle>
        <DialogContent>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Title"
                value={threadForm.title}
                onChange={(e) => setThreadForm(prev => ({ ...prev, title: e.target.value }))}
                required
              />
            </Grid>
            
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Description"
                value={threadForm.description}
                onChange={(e) => setThreadForm(prev => ({ ...prev, description: e.target.value }))}
                multiline
                rows={3}
                required
              />
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Category"
                value={threadForm.category}
                onChange={(e) => setThreadForm(prev => ({ ...prev, category: e.target.value }))}
                required
              />
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Priority Level</InputLabel>
                <Select
                  value={threadForm.priority_level}
                  label="Priority Level"
                  onChange={(e) => setThreadForm(prev => ({ ...prev, priority_level: e.target.value }))}
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
          <Button onClick={() => setCreateThreadDialog(false)}>Cancel</Button>
          <Button onClick={handleCreateThread} variant="contained" disabled={loading}>
            {loading ? <CircularProgress size={20} /> : 'Create Thread'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Error Alert */}
      {error && (
        <Alert 
          severity="error" 
          sx={{ position: 'fixed', bottom: 20, right: 20, zIndex: 1000 }}
          onClose={() => setError(null)}
        >
          {error}
        </Alert>
      )}
    </Box>
  );
};

export default ArticleViewer;

