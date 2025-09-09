import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  CardHeader,
  Button,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Switch,
  FormControlLabel,
  Alert,
  CircularProgress,
  Tabs,
  Tab,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Badge,
  LinearProgress
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Refresh as RefreshIcon,
  TrendingUp as TrendingUpIcon,
  Psychology as PsychologyIcon,
  Timeline as TimelineIcon,
  Assessment as AssessmentIcon,
  AutoAwesome as AutoAwesomeIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Info as InfoIcon
} from '@mui/icons-material';
import newsSystemService from '../../services/newsSystemService';
import { useNotifications } from '../../components/Notifications/NotificationSystem';

const StoryControlDashboard = () => {
  const { showSuccess, showError, showLoading, showInfo } = useNotifications();
  
  // State
  const [stories, setStories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState(0);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showUkraineDialog, setShowUkraineDialog] = useState(false);
  const [feedbackLoopStatus, setFeedbackLoopStatus] = useState(null);
  const [weeklyDigest, setWeeklyDigest] = useState(null);
  const [buttonLoading, setButtonLoading] = useState({});

  // Form state for creating stories
  const [storyForm, setStoryForm] = useState({
    name: '',
    description: '',
    priority_level: 5,
    keywords: [],
    entities: [],
    geographic_regions: [],
    quality_threshold: 0.7,
    max_articles_per_day: 100,
    auto_enhance: true
  });

  // Form state for keywords/entities
  const [newKeyword, setNewKeyword] = useState('');
  const [newEntity, setNewEntity] = useState('');
  const [newRegion, setNewRegion] = useState('');

  useEffect(() => {
    fetchStories();
    fetchFeedbackLoopStatus();
    fetchWeeklyDigest();
  }, []);

  const fetchStories = async () => {
    try {
      setLoading(true);
      const response = await newsSystemService.getActiveStories();
      setStories(response);
    } catch (err) {
      console.error('Error fetching stories:', err);
      setError(err.message);
      showError(`Failed to load stories: ${err.message}`, 'Load Error');
    } finally {
      setLoading(false);
    }
  };

  const fetchFeedbackLoopStatus = async () => {
    try {
      const response = await newsSystemService.getFeedbackLoopStatus();
      setFeedbackLoopStatus(response);
    } catch (err) {
      console.error('Error fetching feedback loop status:', err);
    }
  };

  const fetchWeeklyDigest = async () => {
    try {
      const response = await newsSystemService.getRecentDigests(1);
      if (response.length > 0) {
        setWeeklyDigest(response[0]);
      }
    } catch (err) {
      console.error('Error fetching weekly digest:', err);
    }
  };

  const handleCreateStory = async () => {
    try {
      setButtonLoading(prev => ({ ...prev, create: true }));
      
      showLoading('Creating story...', 'Story Creation');
      
      const response = await newsSystemService.createStoryExpectation(storyForm);
      
      showSuccess('Story created successfully!', 'Story Created');
      
      setShowCreateDialog(false);
      resetStoryForm();
      await fetchStories();
    } catch (err) {
      console.error('Error creating story:', err);
      showError(`Failed to create story: ${err.message}`, 'Creation Error');
    } finally {
      setButtonLoading(prev => ({ ...prev, create: false }));
    }
  };

  const handleCreateUkraineStory = async () => {
    try {
      setButtonLoading(prev => ({ ...prev, ukraine: true }));
      
      showLoading('Creating Ukraine-Russia conflict story...', 'Story Creation');
      
      const response = await newsSystemService.createUkraineRussiaConflictStory();
      
      showSuccess('Ukraine-Russia conflict story created successfully!', 'Story Created');
      
      setShowUkraineDialog(false);
      await fetchStories();
    } catch (err) {
      console.error('Error creating Ukraine story:', err);
      showError(`Failed to create Ukraine story: ${err.message}`, 'Creation Error');
    } finally {
      setButtonLoading(prev => ({ ...prev, ukraine: false }));
    }
  };

  const handleStartFeedbackLoop = async () => {
    try {
      setButtonLoading(prev => ({ ...prev, start: true }));
      
      showLoading('Starting feedback loop...', 'Feedback Loop');
      
      await newsSystemService.startFeedbackLoop();
      
      showSuccess('Feedback loop started successfully!', 'Feedback Loop Started');
      
      await fetchFeedbackLoopStatus();
    } catch (err) {
      console.error('Error starting feedback loop:', err);
      showError(`Failed to start feedback loop: ${err.message}`, 'Start Error');
    } finally {
      setButtonLoading(prev => ({ ...prev, start: false }));
    }
  };

  const handleStopFeedbackLoop = async () => {
    try {
      setButtonLoading(prev => ({ ...prev, stop: true }));
      
      showLoading('Stopping feedback loop...', 'Feedback Loop');
      
      await newsSystemService.stopFeedbackLoop();
      
      showSuccess('Feedback loop stopped successfully!', 'Feedback Loop Stopped');
      
      await fetchFeedbackLoopStatus();
    } catch (err) {
      console.error('Error stopping feedback loop:', err);
      showError(`Failed to stop feedback loop: ${err.message}`, 'Stop Error');
    } finally {
      setButtonLoading(prev => ({ ...prev, stop: false }));
    }
  };

  const handleGenerateDigest = async () => {
    try {
      setButtonLoading(prev => ({ ...prev, digest: true }));
      
      showLoading('Generating weekly digest...', 'Weekly Digest');
      
      await newsSystemService.generateWeeklyDigest();
      
      showSuccess('Weekly digest generated successfully!', 'Digest Generated');
      
      await fetchWeeklyDigest();
    } catch (err) {
      console.error('Error generating digest:', err);
      showError(`Failed to generate digest: ${err.message}`, 'Generation Error');
    } finally {
      setButtonLoading(prev => ({ ...prev, digest: false }));
    }
  };

  const resetStoryForm = () => {
    setStoryForm({
      name: '',
      description: '',
      priority_level: 5,
      keywords: [],
      entities: [],
      geographic_regions: [],
      quality_threshold: 0.7,
      max_articles_per_day: 100,
      auto_enhance: true
    });
  };

  const addKeyword = () => {
    if (newKeyword.trim()) {
      setStoryForm(prev => ({
        ...prev,
        keywords: [...prev.keywords, newKeyword.trim()]
      }));
      setNewKeyword('');
    }
  };

  const addEntity = () => {
    if (newEntity.trim()) {
      setStoryForm(prev => ({
        ...prev,
        entities: [...prev.entities, newEntity.trim()]
      }));
      setNewEntity('');
    }
  };

  const addRegion = () => {
    if (newRegion.trim()) {
      setStoryForm(prev => ({
        ...prev,
        geographic_regions: [...prev.geographic_regions, newRegion.trim()]
      }));
      setNewRegion('');
    }
  };

  const removeKeyword = (index) => {
    setStoryForm(prev => ({
      ...prev,
      keywords: prev.keywords.filter((_, i) => i !== index)
    }));
  };

  const removeEntity = (index) => {
    setStoryForm(prev => ({
      ...prev,
      entities: prev.entities.filter((_, i) => i !== index)
    }));
  };

  const removeRegion = (index) => {
    setStoryForm(prev => ({
      ...prev,
      geographic_regions: prev.geographic_regions.filter((_, i) => i !== index)
    }));
  };

  const getPriorityColor = (priority) => {
    if (priority >= 8) return 'error';
    if (priority >= 6) return 'warning';
    if (priority >= 4) return 'info';
    return 'success';
  };

  const getPriorityLabel = (priority) => {
    if (priority >= 8) return 'Critical';
    if (priority >= 6) return 'High';
    if (priority >= 4) return 'Medium';
    return 'Low';
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" action={
        <Button color="inherit" size="small" onClick={fetchStories}>
          Retry
        </Button>
      }>
        Error loading story control dashboard: {error}
      </Alert>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Story Control Dashboard
        </Typography>
        <Box display="flex" gap={2}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={fetchStories}
            disabled={loading}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setShowCreateDialog(true)}
          >
            Create Story
          </Button>
          <Button
            variant="contained"
            color="secondary"
            startIcon={<AutoAwesomeIcon />}
            onClick={() => setShowUkraineDialog(true)}
          >
            Ukraine-Russia Conflict
          </Button>
        </Box>
      </Box>

      {/* Feedback Loop Status */}
      {feedbackLoopStatus && (
        <Card sx={{ mb: 3 }}>
          <CardHeader
            title="Feedback Loop Status"
            action={
              <Box display="flex" gap={1}>
                {feedbackLoopStatus.is_running ? (
                  <Button
                    variant="outlined"
                    color="error"
                    startIcon={<StopIcon />}
                    onClick={handleStopFeedbackLoop}
                    disabled={buttonLoading.stop}
                  >
                    Stop Loop
                  </Button>
                ) : (
                  <Button
                    variant="outlined"
                    color="success"
                    startIcon={<PlayIcon />}
                    onClick={handleStartFeedbackLoop}
                    disabled={buttonLoading.start}
                  >
                    Start Loop
                  </Button>
                )}
              </Box>
            }
          />
          <CardContent>
            <Grid container spacing={2}>
              <Grid item xs={12} md={3}>
                <Box textAlign="center">
                  <Typography variant="h6" color={feedbackLoopStatus.is_running ? 'success.main' : 'error.main'}>
                    {feedbackLoopStatus.is_running ? 'Running' : 'Stopped'}
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    Status
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={12} md={3}>
                <Box textAlign="center">
                  <Typography variant="h6">
                    {feedbackLoopStatus.stories_being_tracked}
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    Stories Tracked
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={12} md={3}>
                <Box textAlign="center">
                  <Typography variant="h6">
                    {feedbackLoopStatus.articles_processed_today}
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    Articles Today
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={12} md={3}>
                <Box textAlign="center">
                  <Typography variant="h6">
                    {feedbackLoopStatus.rag_enhancements_triggered}
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    RAG Enhancements
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* Weekly Digest */}
      {weeklyDigest && (
        <Card sx={{ mb: 3 }}>
          <CardHeader
            title="Weekly Digest"
            action={
              <Button
                variant="outlined"
                startIcon={<AssessmentIcon />}
                onClick={handleGenerateDigest}
                disabled={buttonLoading.digest}
              >
                Generate New
              </Button>
            }
          />
          <CardContent>
            <Grid container spacing={2}>
              <Grid item xs={12} md={4}>
                <Typography variant="h6">
                  {weeklyDigest.total_articles_analyzed}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  Articles Analyzed
                </Typography>
              </Grid>
              <Grid item xs={12} md={4}>
                <Typography variant="h6">
                  {weeklyDigest.new_stories_suggested}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  New Stories Suggested
                </Typography>
              </Grid>
              <Grid item xs={12} md={4}>
                <Typography variant="h6">
                  {weeklyDigest.story_suggestions.length}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  Story Suggestions
                </Typography>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* Stories List */}
      <Card>
        <CardHeader title="Active Stories" />
        <CardContent>
          {stories.length === 0 ? (
            <Box textAlign="center" py={4}>
              <Typography variant="h6" color="textSecondary">
                No stories configured yet
              </Typography>
              <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
                Create your first story to start tracking
              </Typography>
            </Box>
          ) : (
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Name</TableCell>
                    <TableCell>Priority</TableCell>
                    <TableCell>Keywords</TableCell>
                    <TableCell>Entities</TableCell>
                    <TableCell>Auto Enhance</TableCell>
                    <TableCell>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {stories.map((story) => (
                    <TableRow key={story.story_id}>
                      <TableCell>
                        <Box>
                          <Typography variant="subtitle1">
                            {story.name}
                          </Typography>
                          <Typography variant="body2" color="textSecondary">
                            {story.description}
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={getPriorityLabel(story.priority_level)}
                          color={getPriorityColor(story.priority_level)}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Box display="flex" flexWrap="wrap" gap={0.5}>
                          {story.keywords.slice(0, 3).map((keyword, index) => (
                            <Chip
                              key={index}
                              label={keyword}
                              size="small"
                              variant="outlined"
                            />
                          ))}
                          {story.keywords.length > 3 && (
                            <Chip
                              label={`+${story.keywords.length - 3}`}
                              size="small"
                              variant="outlined"
                            />
                          )}
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Box display="flex" flexWrap="wrap" gap={0.5}>
                          {story.entities.slice(0, 2).map((entity, index) => (
                            <Chip
                              key={index}
                              label={entity}
                              size="small"
                              variant="outlined"
                            />
                          ))}
                          {story.entities.length > 2 && (
                            <Chip
                              label={`+${story.entities.length - 2}`}
                              size="small"
                              variant="outlined"
                            />
                          )}
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Chip
                          icon={story.auto_enhance ? <CheckCircleIcon /> : <ErrorIcon />}
                          label={story.auto_enhance ? 'Enabled' : 'Disabled'}
                          color={story.auto_enhance ? 'success' : 'error'}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Box display="flex" gap={1}>
                          <Tooltip title="Edit Story">
                            <IconButton size="small">
                              <EditIcon />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Delete Story">
                            <IconButton size="small" color="error">
                              <DeleteIcon />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

      {/* Create Story Dialog */}
      <Dialog
        open={showCreateDialog}
        onClose={() => setShowCreateDialog(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Create New Story</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <Grid container spacing={2}>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Story Name"
                  value={storyForm.name}
                  onChange={(e) => setStoryForm(prev => ({ ...prev, name: e.target.value }))}
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Description"
                  multiline
                  rows={3}
                  value={storyForm.description}
                  onChange={(e) => setStoryForm(prev => ({ ...prev, description: e.target.value }))}
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <FormControl fullWidth>
                  <InputLabel>Priority Level</InputLabel>
                  <Select
                    value={storyForm.priority_level}
                    onChange={(e) => setStoryForm(prev => ({ ...prev, priority_level: e.target.value }))}
                  >
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(level => (
                      <MenuItem key={level} value={level}>
                        {level} - {getPriorityLabel(level)}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Quality Threshold"
                  type="number"
                  inputProps={{ min: 0, max: 1, step: 0.1 }}
                  value={storyForm.quality_threshold}
                  onChange={(e) => setStoryForm(prev => ({ ...prev, quality_threshold: parseFloat(e.target.value) }))}
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Max Articles Per Day"
                  type="number"
                  value={storyForm.max_articles_per_day}
                  onChange={(e) => setStoryForm(prev => ({ ...prev, max_articles_per_day: parseInt(e.target.value) }))}
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={storyForm.auto_enhance}
                      onChange={(e) => setStoryForm(prev => ({ ...prev, auto_enhance: e.target.checked }))}
                    />
                  }
                  label="Auto Enhance with RAG"
                />
              </Grid>
              
              {/* Keywords */}
              <Grid item xs={12}>
                <Typography variant="h6" gutterBottom>
                  Keywords
                </Typography>
                <Box display="flex" gap={1} mb={2}>
                  <TextField
                    size="small"
                    label="Add Keyword"
                    value={newKeyword}
                    onChange={(e) => setNewKeyword(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && addKeyword()}
                  />
                  <Button onClick={addKeyword} disabled={!newKeyword.trim()}>
                    Add
                  </Button>
                </Box>
                <Box display="flex" flexWrap="wrap" gap={1}>
                  {storyForm.keywords.map((keyword, index) => (
                    <Chip
                      key={index}
                      label={keyword}
                      onDelete={() => removeKeyword(index)}
                      color="primary"
                      variant="outlined"
                    />
                  ))}
                </Box>
              </Grid>

              {/* Entities */}
              <Grid item xs={12}>
                <Typography variant="h6" gutterBottom>
                  Entities
                </Typography>
                <Box display="flex" gap={1} mb={2}>
                  <TextField
                    size="small"
                    label="Add Entity"
                    value={newEntity}
                    onChange={(e) => setNewEntity(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && addEntity()}
                  />
                  <Button onClick={addEntity} disabled={!newEntity.trim()}>
                    Add
                  </Button>
                </Box>
                <Box display="flex" flexWrap="wrap" gap={1}>
                  {storyForm.entities.map((entity, index) => (
                    <Chip
                      key={index}
                      label={entity}
                      onDelete={() => removeEntity(index)}
                      color="secondary"
                      variant="outlined"
                    />
                  ))}
                </Box>
              </Grid>

              {/* Geographic Regions */}
              <Grid item xs={12}>
                <Typography variant="h6" gutterBottom>
                  Geographic Regions
                </Typography>
                <Box display="flex" gap={1} mb={2}>
                  <TextField
                    size="small"
                    label="Add Region"
                    value={newRegion}
                    onChange={(e) => setNewRegion(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && addRegion()}
                  />
                  <Button onClick={addRegion} disabled={!newRegion.trim()}>
                    Add
                  </Button>
                </Box>
                <Box display="flex" flexWrap="wrap" gap={1}>
                  {storyForm.geographic_regions.map((region, index) => (
                    <Chip
                      key={index}
                      label={region}
                      onDelete={() => removeRegion(index)}
                      color="info"
                      variant="outlined"
                    />
                  ))}
                </Box>
              </Grid>
            </Grid>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowCreateDialog(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleCreateStory}
            variant="contained"
            disabled={buttonLoading.create || !storyForm.name.trim()}
          >
            {buttonLoading.create ? <CircularProgress size={20} /> : 'Create Story'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Ukraine-Russia Conflict Dialog */}
      <Dialog
        open={showUkraineDialog}
        onClose={() => setShowUkraineDialog(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Create Ukraine-Russia Conflict Story</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <Alert severity="info" sx={{ mb: 2 }}>
              This will create a pre-configured story for tracking the Ukraine-Russia conflict with:
            </Alert>
            <List>
              <ListItem>
                <ListItemText
                  primary="High Priority (10/10)"
                  secondary="Critical international conflict"
                />
              </ListItem>
              <ListItem>
                <ListItemText
                  primary="Comprehensive Keywords"
                  secondary="Ukraine, Russia, conflict, war, invasion, military, defense, etc."
                />
              </ListItem>
              <ListItem>
                <ListItemText
                  primary="Key Entities"
                  secondary="Volodymyr Zelensky, Vladimir Putin, NATO, EU, etc."
                />
              </ListItem>
              <ListItem>
                <ListItemText
                  primary="Quality Filters"
                  secondary="Trusted sources, high-quality content only"
                />
              </ListItem>
              <ListItem>
                <ListItemText
                  primary="Auto-Enhancement"
                  secondary="RAG system will continuously enhance context"
                />
              </ListItem>
            </List>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowUkraineDialog(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleCreateUkraineStory}
            variant="contained"
            color="secondary"
            disabled={buttonLoading.ukraine}
          >
            {buttonLoading.ukraine ? <CircularProgress size={20} /> : 'Create Story'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default StoryControlDashboard;
