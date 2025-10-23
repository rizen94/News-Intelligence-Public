import {
  Schedule,
  Assessment,
  Timeline,
  AutoAwesome,
  Refresh,
  Download,
  Visibility,
  Delete,
  Add,
  Edit,
  Save,
  Cancel,
  Send,
  Bookmark,
} from '@mui/icons-material';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  Alert,
  CircularProgress,
  Tabs,
  Tab,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Tooltip,
  Paper,
  Divider,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import React, { useState, useEffect } from 'react';

import newsSystemService from '../../services/newsSystemService';

const TabPanel = ({ children, value, index, ...other }) => {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`briefings-tabpanel-${index}`}
      aria-labelledby={`briefings-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
};

const DailyBriefings = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Briefing Templates State
  const [templates, setTemplates] = useState([]);
  const [newTemplate, setNewTemplate] = useState({
    name: '',
    description: '',
    sections: [],
    schedule: 'daily',
    enabled: true,
  });

  // Generated Briefings State
  const [briefings, setBriefings] = useState([]);
  const [selectedBriefing, setSelectedBriefing] = useState(null);
  const [showBriefingDialog, setShowBriefingDialog] = useState(false);

  // Briefing Statistics
  const [briefingStats, setBriefingStats] = useState(null);

  const showError = (message) => {
    console.error(message);
    // You can add a toast notification here
  };

  const showSuccess = (message) => {
    console.log(message);
    // You can add a toast notification here
  };

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async() => {
    setLoading(true);
    setError(null);

    try {
      // Load briefing templates and generated briefings from API
      const [templatesResponse, briefingsResponse, statsResponse] = await Promise.all([
        newsSystemService.getBriefingTemplates(),
        newsSystemService.getGeneratedBriefings(),
        newsSystemService.getBriefingStats(),
      ]);

      // Check for critical failures
      const failures = [];

      if (!templatesResponse.success) {
        failures.push('Briefing templates');
        console.error('Failed to load briefing templates:', templatesResponse.error);
      } else {
        setTemplates(templatesResponse.data || []);
      }

      if (!briefingsResponse.success) {
        failures.push('Generated briefings');
        console.error('Failed to load generated briefings:', briefingsResponse.error);
      } else {
        setBriefings(briefingsResponse.data || []);
      }

      if (!statsResponse.success) {
        failures.push('Briefing statistics');
        console.error('Failed to load briefing stats:', statsResponse.error);
      } else {
        setBriefingStats(statsResponse.data || {
          total_briefings: 0,
          briefings_this_week: 0,
          avg_articles_per_briefing: 0,
          avg_word_count: 0,
          most_popular_template: 'None',
        });
      }

      // If any critical data failed to load, show error
      if (failures.length > 0) {
        const errorMessage = `Failed to load: ${failures.join(', ')}. Please check your connection and try again.`;
        setError(errorMessage);
        showError(errorMessage);
      } else {
        showSuccess('Briefing data loaded successfully');
      }

    } catch (err) {
      const errorMessage = 'Failed to load briefing data: ' + err.message;
      setError(errorMessage);
      showError(errorMessage);
      console.error('Error fetching briefing data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (event, newValue) => {
    setActiveTab(newValue);
  };

  const handleAddTemplate = () => {
    if (newTemplate.name && newTemplate.description) {
      const template = {
        id: Date.now(),
        ...newTemplate,
        created_at: new Date().toISOString(),
      };
      setTemplates([...templates, template]);
      setNewTemplate({ name: '', description: '', sections: [], schedule: 'daily', enabled: true });
    }
  };

  const handleDeleteTemplate = (templateId) => {
    setTemplates(templates.filter(template => template.id !== templateId));
  };

  const handleToggleTemplate = (templateId) => {
    setTemplates(templates.map(template =>
      template.id === templateId ? { ...template, enabled: !template.enabled } : template,
    ));
  };

  const handleGenerateBriefing = async(templateId) => {
    try {
      setLoading(true);
      // This would call the real API to generate a briefing
      const response = await newsSystemService.generateDailyDigest();

      if (response.success) {
        // Add the new briefing to the list
        const newBriefing = {
          id: Date.now(),
          template_id: templateId,
          title: `Generated Briefing - ${new Date().toLocaleDateString()}`,
          content: response.content || 'Briefing content...',
          generated_at: new Date().toISOString(),
          status: 'generated',
          article_count: response.article_count || 0,
          word_count: response.content?.length || 0,
        };
        setBriefings([newBriefing, ...briefings]);
      }
    } catch (err) {
      setError('Failed to generate briefing: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleViewBriefing = (briefing) => {
    setSelectedBriefing(briefing);
    setShowBriefingDialog(true);
  };

  const handleCloseBriefingDialog = () => {
    setShowBriefingDialog(false);
    setSelectedBriefing(null);
  };

  const getStatusColor = (status) => {
    switch (status) {
    case 'generated': return 'success';
    case 'pending': return 'warning';
    case 'failed': return 'error';
    default: return 'default';
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Daily Briefings
      </Typography>
      <Typography variant="subtitle1" color="text.secondary" gutterBottom>
        Create and manage automated daily briefings
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={activeTab} onChange={handleTabChange}>
          <Tab label="Templates" />
          <Tab label="Generated Briefings" />
          <Tab label="Statistics" />
        </Tabs>
      </Box>

      <TabPanel value={activeTab} index={0}>
        <Grid container spacing={3}>
          <Grid item xs={12} md={8}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Briefing Templates
                </Typography>
                <List>
                  {templates.map((template) => (
                    <ListItem key={template.id} divider>
                      <ListItemText
                        primary={template.name}
                        secondary={
                          <Box>
                            <Typography variant="body2" color="text.secondary">
                              {template.description}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              Sections: {template.sections.join(', ')}
                            </Typography>
                            <Box sx={{ mt: 1 }}>
                              <Chip
                                label={template.schedule}
                                color="primary"
                                size="small"
                                sx={{ mr: 1 }}
                              />
                              <Chip
                                label={template.enabled ? 'Enabled' : 'Disabled'}
                                color={template.enabled ? 'success' : 'default'}
                                size="small"
                              />
                            </Box>
                          </Box>
                        }
                      />
                      <ListItemSecondaryAction>
                        <Tooltip title="Generate Briefing">
                          <IconButton onClick={() => handleGenerateBriefing(template.id)}>
                            <AutoAwesome />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title={template.enabled ? 'Disable' : 'Enable'}>
                          <IconButton onClick={() => handleToggleTemplate(template.id)}>
                            <Visibility />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete">
                          <IconButton onClick={() => handleDeleteTemplate(template.id)}>
                            <Delete />
                          </IconButton>
                        </Tooltip>
                      </ListItemSecondaryAction>
                    </ListItem>
                  ))}
                </List>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Add New Template
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <TextField
                    label="Template Name"
                    value={newTemplate.name}
                    onChange={(e) => setNewTemplate({ ...newTemplate, name: e.target.value })}
                    fullWidth
                  />
                  <TextField
                    label="Description"
                    value={newTemplate.description}
                    onChange={(e) => setNewTemplate({ ...newTemplate, description: e.target.value })}
                    fullWidth
                    multiline
                    rows={3}
                  />
                  <TextField
                    label="Sections (comma-separated)"
                    value={newTemplate.sections.join(', ')}
                    onChange={(e) => setNewTemplate({
                      ...newTemplate,
                      sections: e.target.value.split(',').map(s => s.trim()).filter(s => s),
                    })}
                    fullWidth
                  />
                  <FormControl fullWidth>
                    <InputLabel>Schedule</InputLabel>
                    <Select
                      value={newTemplate.schedule}
                      onChange={(e) => setNewTemplate({ ...newTemplate, schedule: e.target.value })}
                    >
                      <MenuItem value="daily">Daily</MenuItem>
                      <MenuItem value="weekly">Weekly</MenuItem>
                      <MenuItem value="monthly">Monthly</MenuItem>
                    </Select>
                  </FormControl>
                  <Button
                    variant="contained"
                    onClick={handleAddTemplate}
                    startIcon={<Add />}
                    fullWidth
                  >
                    Add Template
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>

      <TabPanel value={activeTab} index={1}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">
                Generated Briefings
              </Typography>
              <Button
                variant="outlined"
                startIcon={<Refresh />}
                onClick={loadData}
              >
                Refresh
              </Button>
            </Box>
            <List>
              {briefings.map((briefing) => (
                <ListItem key={briefing.id} divider>
                  <ListItemText
                    primary={briefing.title}
                    secondary={
                      <Box>
                        <Typography variant="body2" color="text.secondary">
                          Articles: {briefing.article_count} • Words: {briefing.word_count}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Generated: {new Date(briefing.generated_at).toLocaleString()}
                        </Typography>
                      </Box>
                    }
                  />
                  <ListItemSecondaryAction>
                    <Chip
                      label={briefing.status}
                      color={getStatusColor(briefing.status)}
                      sx={{ mr: 1 }}
                    />
                    <Tooltip title="View Briefing">
                      <IconButton onClick={() => handleViewBriefing(briefing)}>
                        <Visibility />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Download">
                      <IconButton>
                        <Download />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Send">
                      <IconButton>
                        <Send />
                      </IconButton>
                    </Tooltip>
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
            </List>
          </CardContent>
        </Card>
      </TabPanel>

      <TabPanel value={activeTab} index={2}>
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Briefing Statistics
                </Typography>
                {briefingStats && (
                  <Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography>Total Briefings</Typography>
                      <Typography>{briefingStats.total_briefings}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography>This Week</Typography>
                      <Typography>{briefingStats.briefings_this_week}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography>Avg Articles/Briefing</Typography>
                      <Typography>{briefingStats.avg_articles_per_briefing}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography>Avg Word Count</Typography>
                      <Typography>{briefingStats.avg_word_count}</Typography>
                    </Box>
                    <Divider sx={{ my: 2 }} />
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="subtitle2">Most Popular Template</Typography>
                      <Typography variant="subtitle2">{briefingStats.most_popular_template}</Typography>
                    </Box>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Quick Actions
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <Button
                    variant="outlined"
                    startIcon={<AutoAwesome />}
                    onClick={() => handleGenerateBriefing(1)}
                  >
                    Generate Executive Summary
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<Schedule />}
                  >
                    Schedule Briefings
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<Download />}
                  >
                    Export All Briefings
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>

      {/* Briefing View Dialog */}
      <Dialog
        open={showBriefingDialog}
        onClose={handleCloseBriefingDialog}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          {selectedBriefing?.title}
        </DialogTitle>
        <DialogContent>
          {selectedBriefing && (
            <Box>
              <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
                {selectedBriefing.content}
              </Typography>
              <Divider sx={{ my: 2 }} />
              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                <Chip label={`${selectedBriefing.article_count} Articles`} />
                <Chip label={`${selectedBriefing.word_count} Words`} />
                <Chip label={selectedBriefing.status} color={getStatusColor(selectedBriefing.status)} />
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseBriefingDialog}>Close</Button>
          <Button variant="contained" startIcon={<Download />}>
            Download
          </Button>
          <Button variant="contained" startIcon={<Send />}>
            Send
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default DailyBriefings;
