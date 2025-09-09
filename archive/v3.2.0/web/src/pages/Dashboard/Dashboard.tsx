import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  Paper,
  LinearProgress,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
  Alert
} from '@mui/material';
import {
  Article as ArticleIcon,
  RssFeed as RssFeedIcon,
  TrendingUp as TrendingUpIcon,
  HealthAndSafety as HealthIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon
} from '@mui/icons-material';
import { apiService } from '../../services/apiService';

interface DashboardProps {
  systemData: {
    systemHealth: any;
    articleStats: any;
    rssStats: any;
    loading: boolean;
    error: string | null;
  };
}

interface DashboardState {
  recentArticles: any[];
  loading: boolean;
  error: string | null;
}

const Dashboard: React.FC<DashboardProps> = ({ systemData }) => {
  const [state, setState] = useState<DashboardState>({
    recentArticles: [],
    loading: true,
    error: null
  });

  useEffect(() => {
    loadRecentArticles();
  }, []);

  const loadRecentArticles = async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));

      const response = await apiService.getArticles({ limit: 10 });
      setState(prev => ({
        ...prev,
        recentArticles: response.data.items,
        loading: false
      }));
    } catch (error) {
      console.error('Error loading recent articles:', error);
      setState(prev => ({
        ...prev,
        loading: false,
        error: 'Failed to load recent articles'
      }));
    }
  };

  const getHealthIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircleIcon color="success" />;
      case 'degraded':
        return <WarningIcon color="warning" />;
      case 'unhealthy':
        return <ErrorIcon color="error" />;
      default:
        return <HealthIcon color="default" />;
    }
  };

  const getHealthColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'success';
      case 'degraded':
        return 'warning';
      case 'unhealthy':
        return 'error';
      default:
        return 'default';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" component="h1" sx={{ mb: 3 }}>
        Dashboard
      </Typography>

      {/* System Status Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <HealthIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">System Health</Typography>
              </Box>
              {systemData.systemHealth ? (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  {getHealthIcon(systemData.systemHealth.status)}
                  <Chip
                    label={systemData.systemHealth.status}
                    color={getHealthColor(systemData.systemHealth.status)}
                    size="small"
                  />
                </Box>
              ) : (
                <CircularProgress size={20} />
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <ArticleIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">Total Articles</Typography>
              </Box>
              <Typography variant="h4" color="primary">
                {systemData.articleStats?.total_articles || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <RssFeedIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">RSS Feeds</Typography>
              </Card>
              <Typography variant="h4" color="primary">
                {systemData.rssStats?.total_feeds || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <TrendingUpIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6">Success Rate</Typography>
              </Card>
              <Typography variant="h4" color="primary">
                {systemData.articleStats?.processing_success_rate 
                  ? `${(systemData.articleStats.processing_success_rate * 100).toFixed(1)}%`
                  : '0%'
                }
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Articles by Source */}
      {systemData.articleStats?.articles_by_source && (
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2 }}>
                  Articles by Source
                </Typography>
                {Object.entries(systemData.articleStats.articles_by_source).map(([source, count]) => (
                  <Box key={source} sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="body2">{source}</Typography>
                    <Chip label={count as number} size="small" />
                  </Box>
                ))}
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2 }}>
                  Articles by Category
                </Typography>
                {systemData.articleStats.articles_by_category && 
                  Object.entries(systemData.articleStats.articles_by_category).map(([category, count]) => (
                    <Box key={category} sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="body2">{category}</Typography>
                      <Chip label={count as number} size="small" color="primary" />
                    </Box>
                  ))
                }
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Recent Articles */}
      <Card>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Recent Articles
          </Typography>
          
          {state.loading && <LinearProgress />}
          
          {state.error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {state.error}
            </Alert>
          )}

          {!state.loading && !state.error && (
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Title</TableCell>
                    <TableCell>Source</TableCell>
                    <TableCell>Published</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {state.recentArticles.map((article) => (
                    <TableRow key={article.id} hover>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                          {article.title}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip label={article.source || 'Unknown'} size="small" />
                      </TableCell>
                      <TableCell>
                        {article.published_at && formatDate(article.published_at)}
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={article.processing_status}
                          size="small"
                          color={article.processing_status === 'completed' ? 'success' : 'warning'}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}

          {!state.loading && state.recentArticles.length === 0 && (
            <Box sx={{ textAlign: 'center', p: 2 }}>
              <Typography variant="body2" color="text.secondary">
                No recent articles found
              </Typography>
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  );
};

export default Dashboard;
