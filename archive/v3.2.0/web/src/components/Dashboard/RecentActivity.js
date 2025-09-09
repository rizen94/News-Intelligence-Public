// News Intelligence System v3.1.0 - Recent Activity Component
// Shows recent system activity and events

import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Chip,
  Avatar,
  Divider,
  Button,
  CircularProgress
} from '@mui/material';
import {
  Article as ArticleIcon,
  RssFeed as RssIcon,
  Psychology as AIIcon,
  Error as ErrorIcon,
  CheckCircle as CheckIcon,
  Warning as WarningIcon,
  Timeline as TimelineIcon
} from '@mui/icons-material';

const RecentActivity = () => {
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchRecentActivity();
  }, []);

  const fetchRecentActivity = async () => {
    try {
      setLoading(true);
      // Mock recent activity data
      const mockActivities = [
        {
          id: 1,
          type: 'article',
          title: 'New article processed: "AI Breakthrough in Medical Diagnosis"',
          timestamp: new Date(Date.now() - 5 * 60 * 1000),
          status: 'success',
          icon: ArticleIcon,
          color: 'success'
        },
        {
          id: 2,
          type: 'rss',
          title: 'RSS feed updated: BBC News',
          timestamp: new Date(Date.now() - 15 * 60 * 1000),
          status: 'success',
          icon: RssIcon,
          color: 'success'
        },
        {
          id: 3,
          type: 'ai',
          title: 'AI analysis completed for 5 articles',
          timestamp: new Date(Date.now() - 30 * 60 * 1000),
          status: 'success',
          icon: AIIcon,
          color: 'info'
        },
        {
          id: 4,
          type: 'error',
          title: 'RSS feed error: TechCrunch connection failed',
          timestamp: new Date(Date.now() - 45 * 60 * 1000),
          status: 'error',
          icon: ErrorIcon,
          color: 'error'
        },
        {
          id: 5,
          type: 'system',
          title: 'System health check completed',
          timestamp: new Date(Date.now() - 60 * 60 * 1000),
          status: 'success',
          icon: CheckIcon,
          color: 'success'
        }
      ];
      setActivities(mockActivities);
    } catch (error) {
      console.error('Failed to fetch recent activity:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'success':
        return <CheckIcon sx={{ fontSize: 16, color: 'success.main' }} />;
      case 'error':
        return <ErrorIcon sx={{ fontSize: 16, color: 'error.main' }} />;
      case 'warning':
        return <WarningIcon sx={{ fontSize: 16, color: 'warning.main' }} />;
      default:
        return <TimelineIcon sx={{ fontSize: 16, color: 'text.secondary' }} />;
    }
  };

  const formatTimestamp = (timestamp) => {
    const now = new Date();
    const diff = now - timestamp;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    
    if (minutes < 60) {
      return `${minutes}m ago`;
    } else if (hours < 24) {
      return `${hours}h ago`;
    } else {
      return timestamp.toLocaleDateString();
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 200 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6" component="h2">
          Recent Activity
        </Typography>
        <Button size="small" onClick={fetchRecentActivity}>
          Refresh
        </Button>
      </Box>

      <List sx={{ maxHeight: 400, overflow: 'auto' }}>
        {activities.map((activity, index) => (
          <React.Fragment key={activity.id}>
            <ListItem sx={{ px: 0 }}>
              <ListItemIcon sx={{ minWidth: 40 }}>
                <Avatar sx={{ 
                  width: 32, 
                  height: 32, 
                  backgroundColor: `${activity.color}.main`,
                  color: 'white'
                }}>
                  <activity.icon sx={{ fontSize: 16 }} />
                </Avatar>
              </ListItemIcon>
              <ListItemText
                primary={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="body2" sx={{ flexGrow: 1 }}>
                      {activity.title}
                    </Typography>
                    {getStatusIcon(activity.status)}
                  </Box>
                }
                secondary={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                    <Typography variant="caption" color="textSecondary">
                      {formatTimestamp(activity.timestamp)}
                    </Typography>
                    <Chip 
                      label={activity.type} 
                      size="small" 
                      variant="outlined"
                      sx={{ height: 20, fontSize: '0.7rem' }}
                    />
                  </Box>
                }
              />
            </ListItem>
            {index < activities.length - 1 && <Divider />}
          </React.Fragment>
        ))}
      </List>
    </Box>
  );
};

export default RecentActivity;

