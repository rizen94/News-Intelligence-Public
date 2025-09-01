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
  Tabs,
  Tab
} from '@mui/material';
import {
  Add as AddIcon,
  Settings as SettingsIcon,
  Timeline as TimelineIcon,
  TrendingUp as TrendingUpIcon,
  FilterList as FilterIcon
} from '@mui/icons-material';
import StoryThreadManager from './StoryThreadManager';
import UserRulesManager from './UserRulesManager';
import PriorityAnalytics from './PriorityAnalytics';
import CollectionRulesManager from './CollectionRulesManager';

const PrioritizationDashboard = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [statistics, setStatistics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  useEffect(() => {
    fetchStatistics();
  }, [refreshTrigger]);

  const fetchStatistics = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/prioritization/statistics');
      const data = await response.json();
      
      if (data.success) {
        setStatistics(data.data);
      } else {
        setError(data.error);
      }
    } catch (err) {
      setError('Failed to fetch statistics');
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = () => {
    setRefreshTrigger(prev => prev + 1);
  };

  const handleTabChange = (event, newValue) => {
    setActiveTab(newValue);
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
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" gutterBottom>
          Content Prioritization Dashboard
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Manage story threads, user interests, and content priorities
        </Typography>
      </Box>

      {/* Statistics Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                Story Threads
              </Typography>
              <Typography variant="h4">
                {statistics?.total_story_threads || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Active threads
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                Priority Levels
              </Typography>
              <Typography variant="h4">
                {statistics?.total_priority_levels || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Available levels
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                User Rules
              </Typography>
              <Typography variant="h4">
                {statistics?.total_user_rules || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Active rules
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                Collection Rules
              </Typography>
              <Typography variant="h4">
                {statistics?.total_collection_rules || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                System rules
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Priority Level Distribution */}
      {statistics?.priority_stats?.priority_levels && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Priority Level Distribution
            </Typography>
            <Grid container spacing={2}>
              {statistics.priority_stats.priority_levels.map((level) => (
                <Grid item key={level.name}>
                  <Chip
                    label={`${level.name}: ${level.article_count}`}
                    style={{ backgroundColor: level.color_hex, color: 'white' }}
                    size="medium"
                  />
                </Grid>
              ))}
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* Main Content Tabs */}
      <Card>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={activeTab} onChange={handleTabChange}>
            <Tab label="Story Threads" icon={<TimelineIcon />} />
            <Tab label="User Rules" icon={<SettingsIcon />} />
            <Tab label="Analytics" icon={<TrendingUpIcon />} />
            <Tab label="Collection Rules" icon={<FilterIcon />} />
          </Tabs>
        </Box>
        
        <Box sx={{ p: 3 }}>
          {activeTab === 0 && (
            <StoryThreadManager onRefresh={handleRefresh} />
          )}
          {activeTab === 1 && (
            <UserRulesManager onRefresh={handleRefresh} />
          )}
          {activeTab === 2 && (
            <PriorityAnalytics statistics={statistics} />
          )}
          {activeTab === 3 && (
            <CollectionRulesManager onRefresh={handleRefresh} />
          )}
        </Box>
      </Card>
    </Box>
  );
};

export default PrioritizationDashboard;
