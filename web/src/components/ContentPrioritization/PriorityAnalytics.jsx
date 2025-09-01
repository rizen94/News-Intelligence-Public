import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  CircularProgress,
  Alert,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  Timeline as TimelineIcon,
  Assessment as AssessmentIcon,
  PieChart as PieChartIcon
} from '@mui/icons-material';

const PriorityAnalytics = ({ statistics }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!statistics) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
        <CircularProgress />
      </Box>
    );
  }

  const priorityStats = statistics.priority_stats || {};
  const managerStats = statistics.manager_stats || {};

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Priority Analytics & Statistics
      </Typography>

      {/* System Overview */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                System Performance
              </Typography>
              <List dense>
                <ListItem>
                  <ListItemIcon>
                    <AssessmentIcon color="primary" />
                  </ListItemIcon>
                  <ListItemText
                    primary="Total Articles Processed"
                    secondary={managerStats.total_articles_processed || 0}
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <TrendingUpIcon color="success" />
                  </ListItemIcon>
                  <ListItemText
                    primary="Priority Assignments Made"
                    secondary={managerStats.priority_assignments_made || 0}
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <TimelineIcon color="info" />
                  </ListItemIcon>
                  <ListItemText
                    primary="Story Threads Created"
                    secondary={managerStats.story_threads_created || 0}
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <PieChartIcon color="secondary" />
                  </ListItemIcon>
                  <ListItemText
                    primary="RAG Contexts Built"
                    secondary={managerStats.rag_contexts_built || 0}
                  />
                </ListItem>
              </List>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Processing Statistics
              </Typography>
              <List dense>
                <ListItem>
                  <ListItemText
                    primary="Total Processing Time"
                    secondary={`${(managerStats.processing_time || 0).toFixed(2)}s`}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Average Time per Article"
                    secondary={
                      managerStats.total_articles_processed > 0
                        ? `${((managerStats.processing_time || 0) / managerStats.total_articles_processed).toFixed(3)}s`
                        : '0s'
                    }
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Last Run"
                    secondary={
                      managerStats.last_run
                        ? new Date(managerStats.last_run).toLocaleString()
                        : 'Never'
                    }
                  />
                </ListItem>
              </List>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Priority Level Distribution */}
      {priorityStats.priority_levels && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Priority Level Distribution
            </Typography>
            <Grid container spacing={2}>
              {priorityStats.priority_levels.map((level) => (
                <Grid item key={level.name}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Chip
                      label={level.name.toUpperCase()}
                      style={{ 
                        backgroundColor: level.color_hex, 
                        color: 'white',
                        marginBottom: 1
                      }}
                      size="medium"
                    />
                    <Typography variant="h4" color="primary">
                      {level.article_count}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Articles
                    </Typography>
                  </Box>
                </Grid>
              ))}
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* Story Thread Status */}
      {statistics.story_threads && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Story Thread Status
            </Typography>
            <Grid container spacing={2}>
              {Object.entries(statistics.story_threads).map(([status, count]) => (
                <Grid item key={status}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Chip
                      label={status.charAt(0).toUpperCase() + status.slice(1)}
                      color={status === 'active' ? 'success' : 'default'}
                      variant="outlined"
                      sx={{ marginBottom: 1 }}
                    />
                    <Typography variant="h4" color="primary">
                      {count}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Threads
                    </Typography>
                  </Box>
                </Grid>
              ))}
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* Recent Activity */}
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Recent Activity
          </Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Metric</TableCell>
                  <TableCell>Value</TableCell>
                  <TableCell>Description</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                <TableRow>
                  <TableCell>Recent Articles</TableCell>
                  <TableCell>{priorityStats.recent_articles || 0}</TableCell>
                  <TableCell>Articles processed in last 24 hours</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Total Priority Levels</TableCell>
                  <TableCell>{statistics.total_priority_levels || 0}</TableCell>
                  <TableCell>Available priority levels in system</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Total Story Threads</TableCell>
                  <TableCell>{statistics.total_story_threads || 0}</TableCell>
                  <TableCell>All story threads (active + archived)</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Total User Rules</TableCell>
                  <TableCell>{statistics.total_user_rules || 0}</TableCell>
                  <TableCell>User-defined interest rules</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Total Collection Rules</TableCell>
                  <TableCell>{statistics.total_collection_rules || 0}</TableCell>
                  <TableCell>System-level collection rules</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>
    </Box>
  );
};

export default PriorityAnalytics;
