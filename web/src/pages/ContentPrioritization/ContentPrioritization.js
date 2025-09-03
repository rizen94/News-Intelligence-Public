import React, { useState, useEffect } from 'react';
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
  Divider
} from '@mui/material';
import {
  TrendingUp,
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
  Cancel
} from '@mui/icons-material';
import newsSystemService from '../../services/newsSystemService';

function TabPanel({ children, value, index, ...other }) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`prioritization-tabpanel-${index}`}
      aria-labelledby={`prioritization-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

const ContentPrioritization = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Priority Rules State
  const [priorityRules, setPriorityRules] = useState([]);
  const [newRule, setNewRule] = useState({
    name: '',
    condition: '',
    priority: 'high',
    enabled: true
  });
  
  // Content Priority State
  const [contentPriorities, setContentPriorities] = useState([]);
  const [priorityStats, setPriorityStats] = useState(null);
  
  // Story Threads State
  const [storyThreads, setStoryThreads] = useState([]);
  const [selectedThread, setSelectedThread] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      // Load priority rules, content priorities, and story threads
      // These would be real API calls in production
      setPriorityRules([
        {
          id: 1,
          name: 'Breaking News',
          condition: 'title contains "breaking" OR "urgent"',
          priority: 'critical',
          enabled: true,
          created_at: new Date().toISOString()
        },
        {
          id: 2,
          name: 'High-Impact Technology',
          condition: 'category = "technology" AND entities contains "AI"',
          priority: 'high',
          enabled: true,
          created_at: new Date().toISOString()
        }
      ]);
      
      setContentPriorities([
        {
          id: 1,
          article_id: 1,
          title: 'AI Regulation Breakthrough',
          priority_level: 'critical',
          priority_score: 0.95,
          assigned_by: 'system',
          assigned_at: new Date().toISOString()
        }
      ]);
      
      setPriorityStats({
        total_articles: 1250,
        critical_priority: 45,
        high_priority: 180,
        medium_priority: 650,
        low_priority: 375,
        avg_priority_score: 0.68
      });
      
      setStoryThreads([
        {
          id: 1,
          title: 'AI Regulation Developments',
          priority: 'high',
          article_count: 25,
          last_updated: new Date().toISOString()
        }
      ]);
      
    } catch (err) {
      setError('Failed to load prioritization data: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (event, newValue) => {
    setActiveTab(newValue);
  };

  const handleAddRule = () => {
    if (newRule.name && newRule.condition) {
      const rule = {
        id: Date.now(),
        ...newRule,
        created_at: new Date().toISOString()
      };
      setPriorityRules([...priorityRules, rule]);
      setNewRule({ name: '', condition: '', priority: 'high', enabled: true });
    }
  };

  const handleDeleteRule = (ruleId) => {
    setPriorityRules(priorityRules.filter(rule => rule.id !== ruleId));
  };

  const handleToggleRule = (ruleId) => {
    setPriorityRules(priorityRules.map(rule => 
      rule.id === ruleId ? { ...rule, enabled: !rule.enabled } : rule
    ));
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'critical': return 'error';
      case 'high': return 'warning';
      case 'medium': return 'info';
      case 'low': return 'default';
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
        Content Prioritization
      </Typography>
      <Typography variant="subtitle1" color="text.secondary" gutterBottom>
        Manage content priority rules and story thread prioritization
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={activeTab} onChange={handleTabChange}>
          <Tab label="Priority Rules" />
          <Tab label="Content Priorities" />
          <Tab label="Story Threads" />
          <Tab label="Statistics" />
        </Tabs>
      </Box>

      <TabPanel value={activeTab} index={0}>
        <Grid container spacing={3}>
          <Grid item xs={12} md={8}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Priority Rules
                </Typography>
                <List>
                  {priorityRules.map((rule) => (
                    <ListItem key={rule.id} divider>
                      <ListItemText
                        primary={rule.name}
                        secondary={
                          <Box>
                            <Typography variant="body2" color="text.secondary">
                              Condition: {rule.condition}
                            </Typography>
                            <Box sx={{ mt: 1 }}>
                              <Chip 
                                label={rule.priority} 
                                color={getPriorityColor(rule.priority)}
                                size="small"
                                sx={{ mr: 1 }}
                              />
                              <Chip 
                                label={rule.enabled ? 'Enabled' : 'Disabled'} 
                                color={rule.enabled ? 'success' : 'default'}
                                size="small"
                              />
                            </Box>
                          </Box>
                        }
                      />
                      <ListItemSecondaryAction>
                        <Tooltip title={rule.enabled ? 'Disable' : 'Enable'}>
                          <IconButton onClick={() => handleToggleRule(rule.id)}>
                            {rule.enabled ? <Visibility /> : <Visibility />}
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete">
                          <IconButton onClick={() => handleDeleteRule(rule.id)}>
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
                  Add New Rule
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <TextField
                    label="Rule Name"
                    value={newRule.name}
                    onChange={(e) => setNewRule({ ...newRule, name: e.target.value })}
                    fullWidth
                  />
                  <TextField
                    label="Condition"
                    value={newRule.condition}
                    onChange={(e) => setNewRule({ ...newRule, condition: e.target.value })}
                    fullWidth
                    multiline
                    rows={3}
                  />
                  <FormControl fullWidth>
                    <InputLabel>Priority</InputLabel>
                    <Select
                      value={newRule.priority}
                      onChange={(e) => setNewRule({ ...newRule, priority: e.target.value })}
                    >
                      <MenuItem value="critical">Critical</MenuItem>
                      <MenuItem value="high">High</MenuItem>
                      <MenuItem value="medium">Medium</MenuItem>
                      <MenuItem value="low">Low</MenuItem>
                    </Select>
                  </FormControl>
                  <Button
                    variant="contained"
                    onClick={handleAddRule}
                    startIcon={<Add />}
                    fullWidth
                  >
                    Add Rule
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
            <Typography variant="h6" gutterBottom>
              Content Priorities
            </Typography>
            <List>
              {contentPriorities.map((priority) => (
                <ListItem key={priority.id} divider>
                  <ListItemText
                    primary={priority.title}
                    secondary={
                      <Box>
                        <Typography variant="body2" color="text.secondary">
                          Priority Score: {priority.priority_score}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Assigned by: {priority.assigned_by} • {new Date(priority.assigned_at).toLocaleString()}
                        </Typography>
                      </Box>
                    }
                  />
                  <ListItemSecondaryAction>
                    <Chip 
                      label={priority.priority_level} 
                      color={getPriorityColor(priority.priority_level)}
                    />
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
            </List>
          </CardContent>
        </Card>
      </TabPanel>

      <TabPanel value={activeTab} index={2}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Story Threads
            </Typography>
            <List>
              {storyThreads.map((thread) => (
                <ListItem key={thread.id} divider>
                  <ListItemText
                    primary={thread.title}
                    secondary={
                      <Box>
                        <Typography variant="body2" color="text.secondary">
                          Articles: {thread.article_count} • Last updated: {new Date(thread.last_updated).toLocaleString()}
                        </Typography>
                      </Box>
                    }
                  />
                  <ListItemSecondaryAction>
                    <Chip 
                      label={thread.priority} 
                      color={getPriorityColor(thread.priority)}
                    />
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
            </List>
          </CardContent>
        </Card>
      </TabPanel>

      <TabPanel value={activeTab} index={3}>
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Priority Distribution
                </Typography>
                {priorityStats && (
                  <Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography>Critical</Typography>
                      <Typography>{priorityStats.critical_priority}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography>High</Typography>
                      <Typography>{priorityStats.high_priority}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography>Medium</Typography>
                      <Typography>{priorityStats.medium_priority}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography>Low</Typography>
                      <Typography>{priorityStats.low_priority}</Typography>
                    </Box>
                    <Divider sx={{ my: 2 }} />
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="subtitle2">Total Articles</Typography>
                      <Typography variant="subtitle2">{priorityStats.total_articles}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="subtitle2">Avg Priority Score</Typography>
                      <Typography variant="subtitle2">{priorityStats.avg_priority_score}</Typography>
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
                    startIcon={<Refresh />}
                    onClick={loadData}
                  >
                    Refresh Data
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<Download />}
                  >
                    Export Priorities
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<AutoAwesome />}
                  >
                    Auto-Prioritize
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>
    </Box>
  );
};

export default ContentPrioritization;
