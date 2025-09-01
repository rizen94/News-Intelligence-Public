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
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Divider,
  Badge,
  Alert,
  CircularProgress,
  Tooltip,
  Accordion,
  AccordionSummary,
  AccordionDetails
} from '@mui/material';
import {
  Notifications as NotificationsIcon,
  NotificationsActive as NotificationsActiveIcon,
  Close as CloseIcon,
  ExpandMore as ExpandMoreIcon,
  Article as ArticleIcon,
  Timeline as TimelineIcon,
  CheckCircle as CheckCircleIcon,
  Info as InfoIcon
} from '@mui/icons-material';

const StorylineAlerts = () => {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [alertDialogOpen, setAlertDialogOpen] = useState(false);
  const [statistics, setStatistics] = useState({});

  useEffect(() => {
    fetchAlerts();
    fetchStatistics();
    
    // Set up polling for new alerts every 30 seconds
    const interval = setInterval(() => {
      fetchAlerts();
      fetchStatistics();
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  const fetchAlerts = async () => {
    try {
      const response = await fetch('/api/alerts/storyline/unread?limit=20');
      const data = await response.json();
      
      if (data.success) {
        setAlerts(data.alerts);
      } else {
        setError(data.error);
      }
    } catch (err) {
      setError('Failed to fetch alerts');
    } finally {
      setLoading(false);
    }
  };

  const fetchStatistics = async () => {
    try {
      const response = await fetch('/api/alerts/storyline/statistics');
      const data = await response.json();
      
      if (data.success) {
        setStatistics(data.statistics);
      }
    } catch (err) {
      console.error('Failed to fetch alert statistics:', err);
    }
  };

  const markAlertAsRead = async (alertId) => {
    try {
      const response = await fetch(`/api/alerts/storyline/${alertId}/read`, {
        method: 'POST'
      });
      
      if (response.ok) {
        // Remove the alert from the list
        setAlerts(prev => prev.filter(alert => alert.id !== alertId));
        setAlertDialogOpen(false);
        setSelectedAlert(null);
      }
    } catch (err) {
      setError('Failed to mark alert as read');
    }
  };

  const openAlertDialog = (alert) => {
    setSelectedAlert(alert);
    setAlertDialogOpen(true);
  };

  const getSignificanceColor = (score) => {
    if (score >= 0.8) return 'error';
    if (score >= 0.6) return 'warning';
    return 'info';
  };

  const getSignificanceLabel = (score) => {
    if (score >= 0.8) return 'Critical';
    if (score >= 0.6) return 'High';
    return 'Medium';
  };

  const formatTimeAgo = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffInMinutes = Math.floor((now - date) / (1000 * 60));
    
    if (diffInMinutes < 1) return 'Just now';
    if (diffInMinutes < 60) return `${diffInMinutes}m ago`;
    if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)}h ago`;
    return `${Math.floor(diffInMinutes / 1440)}d ago`;
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
      {/* Header with Statistics */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box display="flex" alignItems="center" justifyContent="space-between">
            <Box display="flex" alignItems="center" gap={2}>
              <Badge badgeContent={statistics.unread_alerts || 0} color="error">
                <NotificationsActiveIcon color="primary" />
              </Badge>
              <Typography variant="h6">Storyline Alerts</Typography>
            </Box>
            <Box display="flex" gap={1}>
              <Chip 
                label={`${statistics.unread_alerts || 0} Unread`} 
                color="error" 
                size="small" 
              />
              <Chip 
                label={`${statistics.recent_alerts || 0} Recent`} 
                color="info" 
                size="small" 
              />
            </Box>
          </Box>
        </CardContent>
      </Card>

      {/* Error Display */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Alerts List */}
      {alerts.length === 0 ? (
        <Card>
          <CardContent>
            <Box textAlign="center" py={4}>
              <NotificationsIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" color="text.secondary">
                No New Alerts
              </Typography>
              <Typography variant="body2" color="text.secondary">
                You're all caught up! New storyline updates will appear here.
              </Typography>
            </Box>
          </CardContent>
        </Card>
      ) : (
        <Box>
          {alerts.map((alert) => (
            <Card key={alert.id} sx={{ mb: 2 }}>
              <CardContent>
                <Box display="flex" alignItems="flex-start" justifyContent="space-between">
                  <Box flex={1}>
                    <Box display="flex" alignItems="center" gap={1} mb={1}>
                      <Typography variant="h6" component="div">
                        {alert.title}
                      </Typography>
                      <Chip 
                        label={getSignificanceLabel(alert.significance_score)}
                        color={getSignificanceColor(alert.significance_score)}
                        size="small"
                      />
                    </Box>
                    
                    <Typography variant="body2" color="text.secondary" mb={1}>
                      {alert.message}
                    </Typography>
                    
                    <Box display="flex" alignItems="center" gap={2} mb={1}>
                      <Chip 
                        icon={<ArticleIcon />}
                        label={`${alert.article_count} articles`}
                        size="small"
                        variant="outlined"
                      />
                      <Chip 
                        label={alert.category}
                        size="small"
                        variant="outlined"
                      />
                      <Typography variant="caption" color="text.secondary">
                        {formatTimeAgo(alert.created_at)}
                      </Typography>
                    </Box>
                    
                    <Typography variant="body2" sx={{ fontStyle: 'italic' }}>
                      {alert.context_summary}
                    </Typography>
                  </Box>
                  
                  <Box display="flex" flexDirection="column" gap={1}>
                    <Button
                      variant="outlined"
                      size="small"
                      onClick={() => openAlertDialog(alert)}
                    >
                      View Details
                    </Button>
                    <Button
                      variant="contained"
                      size="small"
                      startIcon={<CheckCircleIcon />}
                      onClick={() => markAlertAsRead(alert.id)}
                    >
                      Mark Read
                    </Button>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          ))}
        </Box>
      )}

      {/* Alert Details Dialog */}
      <Dialog 
        open={alertDialogOpen} 
        onClose={() => setAlertDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          <Box display="flex" alignItems="center" justifyContent="space-between">
            <Typography variant="h6">
              {selectedAlert?.title}
            </Typography>
            <IconButton onClick={() => setAlertDialogOpen(false)}>
              <CloseIcon />
            </IconButton>
          </Box>
        </DialogTitle>
        
        <DialogContent>
          {selectedAlert && (
            <Box>
              <Box display="flex" alignItems="center" gap={2} mb={2}>
                <Chip 
                  label={getSignificanceLabel(selectedAlert.significance_score)}
                  color={getSignificanceColor(selectedAlert.significance_score)}
                />
                <Chip 
                  icon={<ArticleIcon />}
                  label={`${selectedAlert.article_count} articles`}
                  variant="outlined"
                />
                <Typography variant="body2" color="text.secondary">
                  {formatTimeAgo(selectedAlert.created_at)}
                </Typography>
              </Box>
              
              <Typography variant="body1" paragraph>
                {selectedAlert.message}
              </Typography>
              
              <Typography variant="body2" sx={{ fontStyle: 'italic', mb: 2 }}>
                {selectedAlert.context_summary}
              </Typography>
              
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="subtitle1">
                    New Articles ({selectedAlert.new_articles?.length || 0})
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <List dense>
                    {selectedAlert.new_articles?.map((article, index) => (
                      <React.Fragment key={article.id}>
                        <ListItem>
                          <ListItemText
                            primary={article.title}
                            secondary={
                              <Box>
                                <Typography variant="caption" display="block">
                                  {article.source} • {article.category}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                  Quality: {article.quality_score?.toFixed(2)} • 
                                  Published: {new Date(article.published_date).toLocaleDateString()}
                                </Typography>
                              </Box>
                            }
                          />
                        </ListItem>
                        {index < selectedAlert.new_articles.length - 1 && <Divider />}
                      </React.Fragment>
                    ))}
                  </List>
                </AccordionDetails>
              </Accordion>
            </Box>
          )}
        </DialogContent>
        
        <DialogActions>
          <Button onClick={() => setAlertDialogOpen(false)}>
            Close
          </Button>
          <Button 
            variant="contained" 
            startIcon={<CheckCircleIcon />}
            onClick={() => markAlertAsRead(selectedAlert?.id)}
          >
            Mark as Read
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default StorylineAlerts;
