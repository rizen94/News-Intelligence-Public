import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
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
  Divider,
  Badge,
  Tooltip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Paper,

} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Build as BuildIcon,
  AutoAwesome as AutoAwesomeIcon,
  Timeline as TimelineIcon,
  Notifications as NotificationsIcon,
  TrendingUp as TrendingUpIcon,
  Psychology as PsychologyIcon,
  ExpandMore as ExpandMoreIcon,
  Visibility as ViewIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import StoryThreadManager from '../../components/ContentPrioritization/StoryThreadManager';
import RAGContextBuilder from '../../components/ContentPrioritization/RAGContextBuilder';
import IntelligentTags from '../../components/IntelligentTags/IntelligentTags';
import StorylineAlerts from '../../components/StorylineAlerts/StorylineAlerts';

const StoryDossiers = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [storyThreads, setStoryThreads] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedThread, setSelectedThread] = useState(null);
  const [ragDialogOpen, setRagDialogOpen] = useState(false);
  const [tagsDialogOpen, setTagsDialogOpen] = useState(false);
  const [contextData, setContextData] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      
      // Fetch story threads
      const threadsResponse = await fetch('/api/prioritization/story-threads?status=active');
      const threadsData = await threadsResponse.json();
      setStoryThreads(threadsData.data || []);
      
      // Fetch alerts
      const alertsResponse = await fetch('/api/alerts/storyline/unread');
      const alertsData = await alertsResponse.json();
      setAlerts(alertsData.data || []);
      
    } catch (err) {
      setError('Failed to fetch data');
      console.error('Fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleBuildRAG = async (thread) => {
    try {
      setSelectedThread(thread);
      const response = await fetch(`/api/prioritization/rag-context/${thread.id}`);
      const data = await response.json();
      
      if (data.success) {
        setContextData(data.data);
        setRagDialogOpen(true);
      } else {
        setError(data.error || 'Failed to build RAG context');
      }
    } catch (err) {
      setError('Failed to build RAG context');
    }
  };

  const handleIntelligentTags = (thread) => {
    setSelectedThread(thread);
    setTagsDialogOpen(true);
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'high': return 'error';
      case 'medium': return 'warning';
      case 'low': return 'success';
      default: return 'default';
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          Story Dossiers
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={fetchData}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setActiveTab(1)} // Switch to management tab
          >
            New Story Thread
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Box sx={{ display: 'flex' }}>
            <Button
              variant={activeTab === 0 ? 'contained' : 'text'}
              onClick={() => setActiveTab(0)}
              startIcon={<TimelineIcon />}
              sx={{ mr: 1 }}
            >
              <Badge badgeContent={storyThreads.length} color="primary">
                Active Stories
              </Badge>
            </Button>
            <Button
              variant={activeTab === 1 ? 'contained' : 'text'}
              onClick={() => setActiveTab(1)}
              startIcon={<EditIcon />}
              sx={{ mr: 1 }}
            >
              Manage Threads
            </Button>
            <Button
              variant={activeTab === 2 ? 'contained' : 'text'}
              onClick={() => setActiveTab(2)}
              startIcon={<NotificationsIcon />}
            >
              <Badge badgeContent={alerts.length} color="warning">
                Alerts
              </Badge>
            </Button>
          </Box>
        </Box>
      </Paper>

      {/* Tab Content */}
      {activeTab === 0 && (
        <Grid container spacing={3}>
          {storyThreads.map((thread) => (
            <Grid item xs={12} key={thread.id}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                    <Box>
                      <Typography variant="h5" gutterBottom>
                        {thread.title}
                      </Typography>
                      <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                        <Chip 
                          label={thread.priority_level} 
                          color={getPriorityColor(thread.priority_level)} 
                          size="small" 
                        />
                        <Chip 
                          label={thread.category || 'Uncategorized'} 
                          color="default" 
                          size="small" 
                        />
                        <Chip 
                          label={`${thread.keyword_count} keywords`} 
                          color="info" 
                          size="small" 
                        />
                      </Box>
                    </Box>
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      <Tooltip title="Build RAG Context">
                        <IconButton 
                          color="primary"
                          onClick={() => handleBuildRAG(thread)}
                        >
                          <BuildIcon />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Intelligent Tags">
                        <IconButton 
                          color="secondary"
                          onClick={() => handleIntelligentTags(thread)}
                        >
                          <AutoAwesomeIcon />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="View Details">
                        <IconButton color="info">
                          <ViewIcon />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </Box>
                  
                  {thread.description && (
                    <Typography variant="body1" sx={{ mb: 2 }}>
                      {thread.description}
                    </Typography>
                  )}

                  {/* Keywords */}
                  {thread.keywords && thread.keywords.length > 0 && (
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="subtitle2" gutterBottom>
                        Keywords:
                      </Typography>
                      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                        {thread.keywords.map((keyword, index) => (
                          <Chip key={index} label={keyword} size="small" variant="outlined" />
                        ))}
                      </Box>
                    </Box>
                  )}

                  {/* Timeline */}
                  <Accordion>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="subtitle1">
                        Story Timeline & Context
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <List>
                        <ListItem>
                          <ListItemIcon>
                            <AddIcon color="primary" />
                          </ListItemIcon>
                          <ListItemText
                            primary="Story Created"
                            secondary={formatDate(thread.created_at)}
                          />
                        </ListItem>
                        <ListItem>
                          <ListItemIcon>
                            <EditIcon color="secondary" />
                          </ListItemIcon>
                          <ListItemText
                            primary="Last Updated"
                            secondary={formatDate(thread.updated_at)}
                          />
                        </ListItem>
                        <ListItem>
                          <ListItemIcon>
                            <TrendingUpIcon color="success" />
                          </ListItemIcon>
                          <ListItemText
                            primary="Activity Status"
                            secondary={thread.last_activity ? 'Active' : 'Inactive'}
                          />
                        </ListItem>
                      </List>
                    </AccordionDetails>
                  </Accordion>
                </CardContent>
              </Card>
            </Grid>
          ))}
          {storyThreads.length === 0 && (
            <Grid item xs={12}>
              <Paper sx={{ p: 4, textAlign: 'center' }}>
                <Typography variant="h6" color="text.secondary">
                  No active story threads
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Create your first story thread to start tracking news developments
                </Typography>
                <Button
                  variant="contained"
                  startIcon={<AddIcon />}
                  onClick={() => setActiveTab(1)}
                >
                  Create Story Thread
                </Button>
              </Paper>
            </Grid>
          )}
        </Grid>
      )}

      {activeTab === 1 && (
        <StoryThreadManager onRefresh={fetchData} />
      )}

      {activeTab === 2 && (
        <StorylineAlerts />
      )}

      {/* RAG Context Dialog */}
      <Dialog
        open={ragDialogOpen}
        onClose={() => setRagDialogOpen(false)}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle>
          RAG Context - {selectedThread?.title}
        </DialogTitle>
        <DialogContent>
          {contextData && (
            <RAGContextBuilder 
              contextData={contextData}
              threadId={selectedThread?.id}
            />
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRagDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Intelligent Tags Dialog */}
      <Dialog
        open={tagsDialogOpen}
        onClose={() => setTagsDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <AutoAwesomeIcon color="primary" />
            Intelligent Tags - {selectedThread?.title}
          </Box>
        </DialogTitle>
        <DialogContent>
          {selectedThread && (
            <IntelligentTags 
              threadId={selectedThread.id}
              onTagsUpdated={() => {
                fetchData();
                setTagsDialogOpen(false);
              }}
            />
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setTagsDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default StoryDossiers;
