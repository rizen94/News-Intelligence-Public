import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Avatar,
  Button,
  Alert,
  CircularProgress,
} from '@mui/material';
import MLProcessingStatus from '../../components/MLProcessingStatus/MLProcessingStatus';
import {
  Article as ArticleIcon,
  GroupWork as ClusterIcon,
  Person as PersonIcon,
  RssFeed as SourceIcon,
  TrendingUp as TrendingUpIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Refresh as RefreshIcon,
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
} from '@mui/icons-material';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell } from 'recharts';
import { useNewsSystem } from '../../contexts/NewsSystemContext';
import Breadcrumb from '../../components/Breadcrumb/Breadcrumb';
import './Dashboard.css';

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

export default function Dashboard() {
  const { state, actions } = useNewsSystem();
  const { dashboard, pipeline, systemStatus } = state;
  const [isRefreshing, setIsRefreshing] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    // Dashboard data is loaded in context initialization
  }, []);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      // Refresh dashboard data
      const dashboardData = await actions.fetchArticles();
      // Add a small delay to show loading state
      setTimeout(() => setIsRefreshing(false), 1000);
    } catch (error) {
      setIsRefreshing(false);
    }
  };

  const handleRunPipeline = async () => {
    try {
      await actions.runPipeline();
    } catch (error) {
      console.error('Failed to run pipeline:', error);
    }
  };

  // Mock data for charts
  const articleTrendData = [
    { date: 'Mon', articles: 45, clusters: 3, entities: 67 },
    { date: 'Tue', articles: 52, clusters: 4, entities: 78 },
    { date: 'Wed', articles: 38, clusters: 2, entities: 54 },
    { date: 'Thu', articles: 61, clusters: 5, entities: 89 },
    { date: 'Fri', articles: 48, clusters: 3, entities: 72 },
    { date: 'Sat', articles: 35, clusters: 2, entities: 51 },
    { date: 'Sun', articles: 42, clusters: 3, entities: 63 },
  ];

  const sourceHealthData = [
    { name: 'BBC News', health: 99.8, articles: 156 },
    { name: 'Reuters', health: 99.5, articles: 134 },
    { name: 'AP', health: 95.2, articles: 98 },
    { name: 'TechCrunch', health: 98.9, articles: 87 },
    { name: 'The Verge', health: 99.1, articles: 76 },
  ];

  const entityTypeData = [
    { name: 'People', value: 45, color: '#0088FE' },
    { name: 'Organizations', value: 32, color: '#00C49F' },
    { name: 'Locations', value: 28, color: '#FFBB28' },
    { name: 'Events', value: 18, color: '#FF8042' },
    { name: 'Concepts', value: 12, color: '#8884D8' },
  ];

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy': return 'success';
      case 'warning': return 'warning';
      case 'error': return 'error';
      default: return 'default';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy': return <CheckCircleIcon color="success" />;
      case 'warning': return <WarningIcon color="warning" />;
      case 'error': return <ErrorIcon color="error" />;
      default: return <ErrorIcon color="disabled" />;
    }
  };

  const StatCard = ({ title, value, icon, color = 'primary', subtitle, trend }) => (
    <Card sx={{ 
      height: '100%', 
      minHeight: { xs: 120, sm: 140, md: 160 },
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between',
      width: '100%'
    }}>
      <CardContent sx={{ 
        p: { xs: 2, sm: 3 },
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between'
      }}>
        <Box sx={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between', 
          mb: { xs: 1, sm: 2 },
          flexWrap: 'wrap',
          gap: 1
        }}>
          <Typography 
            variant="h4" 
            component="div" 
            color={color} 
            sx={{ 
              fontWeight: 'bold',
              fontSize: { xs: '1.5rem', sm: '2rem', md: '2.125rem', lg: '2.5rem' }
            }}
          >
            {value}
          </Typography>
          <Avatar sx={{ 
            bgcolor: `${color}.light`, 
            color: `${color}.dark`,
            width: { xs: 32, sm: 40, md: 48 },
            height: { xs: 32, sm: 40, md: 48 }
          }}>
            {icon}
          </Avatar>
        </Box>
        <Typography 
          variant="h6" 
          component="div" 
          gutterBottom
          sx={{ 
            fontSize: { xs: '0.875rem', sm: '1rem', md: '1.25rem' },
            fontWeight: 500
          }}
        >
          {title}
        </Typography>
        {subtitle && (
          <Typography 
            variant="body2" 
            color="text.secondary"
            sx={{ fontSize: { xs: '0.75rem', sm: '0.875rem' } }}
          >
            {subtitle}
          </Typography>
        )}
        {trend && (
          <Box sx={{ display: 'flex', alignItems: 'center', mt: 1 }}>
            <TrendingUpIcon color="success" sx={{ fontSize: { xs: 14, sm: 16 }, mr: 0.5 }} />
            <Typography 
              variant="caption" 
              color="success.main"
              sx={{ fontSize: { xs: '0.7rem', sm: '0.75rem' } }}
            >
              {trend}
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );

  const PipelineStatusCard = () => (
    <Card className="dashboard-card" sx={{ height: '100%' }}>
      <CardContent className="dashboard-card-content">
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="h6" component="div">
            Pipeline Status
          </Typography>
          <Chip
            label={pipeline.status}
            color={pipeline.status === 'running' ? 'warning' : pipeline.status === 'completed' ? 'success' : 'default'}
            size="small"
          />
        </Box>
        
        {pipeline.status === 'running' && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              {pipeline.currentStep}
            </Typography>
            <LinearProgress variant="determinate" value={pipeline.progress} sx={{ height: 8, borderRadius: 4 }} />
            <Typography variant="caption" color="text.secondary">
              {pipeline.progress}% Complete
            </Typography>
          </Box>
        )}
        
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Last Run: {pipeline.lastRun ? new Date(pipeline.lastRun).toLocaleString() : 'Never'}
          </Typography>
        </Box>
        
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <Chip
            label={`${pipeline.statistics.articlesProcessed} Articles`}
            size="small"
            variant="outlined"
          />
          <Chip
            label={`${pipeline.statistics.duplicatesRemoved} Duplicates`}
            size="small"
            variant="outlined"
          />
          <Chip
            label={`${pipeline.statistics.entitiesExtracted} Entities`}
            size="small"
            variant="outlined"
          />
        </Box>
        
        <Box sx={{ mt: 2 }}>
          <Button
            variant="contained"
            startIcon={pipeline.status === 'running' ? <PauseIcon /> : <PlayIcon />}
            onClick={handleRunPipeline}
            disabled={pipeline.status === 'running'}
            fullWidth
          >
            {pipeline.status === 'running' ? 'Stop Pipeline' : 'Run Pipeline'}
          </Button>
        </Box>
      </CardContent>
    </Card>
  );

  const SystemHealthCard = () => (
    <Card className="dashboard-card" sx={{ height: '100%' }}>
      <CardContent className="dashboard-card-content">
        <Typography variant="h6" component="div" gutterBottom>
          System Health
        </Typography>
        
        <Box sx={{ mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
            <Typography variant="body2">CPU Usage</Typography>
            <Typography variant="body2">{systemStatus.cpuUsage}</Typography>
          </Box>
          <LinearProgress 
            variant="determinate" 
            value={parseInt(systemStatus.cpuUsage)} 
            color={parseInt(systemStatus.cpuUsage) > 80 ? 'error' : parseInt(systemStatus.cpuUsage) > 60 ? 'warning' : 'success'}
            sx={{ height: 6, borderRadius: 3 }}
          />
        </Box>
        
        <Box sx={{ mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
            <Typography variant="body2">Memory Usage</Typography>
            <Typography variant="body2">{systemStatus.memoryUsage}</Typography>
          </Box>
          <LinearProgress 
            variant="determinate" 
            value={parseInt(systemStatus.memoryUsage)} 
            color={parseInt(systemStatus.memoryUsage) > 80 ? 'error' : parseInt(systemStatus.memoryUsage) > 60 ? 'warning' : 'success'}
            sx={{ height: 6, borderRadius: 3 }}
          />
        </Box>
        
        <Box sx={{ mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
            <Typography variant="body2">Disk Usage</Typography>
            <Typography variant="body2">{systemStatus.diskUsage}</Typography>
          </Box>
          <LinearProgress 
            variant="determinate" 
            value={parseInt(systemStatus.diskUsage)} 
            color={parseInt(systemStatus.diskUsage) > 80 ? 'error' : parseInt(systemStatus.diskUsage) > 60 ? 'warning' : 'success'}
            sx={{ height: 6, borderRadius: 3 }}
          />
        </Box>
        
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="body2">Uptime:</Typography>
          <Chip label={systemStatus.uptime} size="small" variant="outlined" />
        </Box>
      </CardContent>
    </Card>
  );

  const RecentArticlesCard = () => (
    <Card className="dashboard-card" sx={{ height: '100%' }}>
      <CardContent className="dashboard-card-content">
        <Typography variant="h6" component="div" gutterBottom>
          Recent Articles
        </Typography>
        
        <List dense>
          {dashboard.recentArticles.map((article, index) => (
            <ListItem key={article.id} sx={{ px: 0 }}>
              <ListItemIcon>
                <Avatar sx={{ width: 32, height: 32, bgcolor: 'primary.light' }}>
                  <ArticleIcon fontSize="small" />
                </Avatar>
              </ListItemIcon>
              <ListItemText
                primary={
                  <Typography variant="body2" sx={{ fontWeight: 500 }}>
                    {article.title}
                  </Typography>
                }
                secondary={
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      {article.source} • {article.category} • {new Date(article.publishedDate).toLocaleDateString()}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                      {article.summary}
                    </Typography>
                  </Box>
                }
              />
            </ListItem>
          ))}
        </List>
        
        <Box sx={{ mt: 2 }}>
          <Button 
            variant="outlined" 
            size="small" 
            fullWidth
            onClick={() => navigate('/articles')}
          >
            View All Articles
          </Button>
        </Box>
      </CardContent>
    </Card>
  );

  const FeedHealthCard = () => (
    <Card className="dashboard-card" sx={{ height: '100%' }}>
      <CardContent className="dashboard-card-content">
        <Typography variant="h6" component="div" gutterBottom>
          Feed Health
        </Typography>
        
        <List dense>
          {dashboard.feedHealth.map((feed, index) => (
            <ListItem key={index} sx={{ px: 0 }}>
              <ListItemIcon>
                {getStatusIcon(feed.status)}
              </ListItemIcon>
              <ListItemText
                primary={feed.source}
                secondary={
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Success Rate: {feed.successRate}% • Last Fetch: {new Date(feed.lastFetch).toLocaleTimeString()}
                    </Typography>
                  </Box>
                }
              />
              <Chip
                label={feed.status}
                color={getStatusColor(feed.status)}
                size="small"
              />
            </ListItem>
          ))}
        </List>
      </CardContent>
    </Card>
  );

  if (isRefreshing) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box 
      className="dashboard-container"
      sx={{
        width: '100%',
        minHeight: '100vh',
        overflow: 'auto',
        p: { xs: 1, sm: 2, md: 3, lg: 4 },
        backgroundColor: 'background.default',
        display: 'flex',
        flexDirection: 'column',
        gap: { xs: 2, sm: 3, md: 4, lg: 5 },
      }}
    >
      {/* Breadcrumb Navigation */}
      <Breadcrumb />
      
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1" sx={{ fontWeight: 'bold' }}>
          Dashboard
        </Typography>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={handleRefresh}
          disabled={isRefreshing}
        >
          Refresh
        </Button>
      </Box>

      {/* ML Processing Status */}
      <MLProcessingStatus />

      {/* System Status Alert */}
      {systemStatus.status !== 'healthy' && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          System status: {systemStatus.status}. Please check system health and monitoring.
        </Alert>
      )}

      {/* Statistics Cards */}
      <Grid 
        container 
        spacing={{ xs: 1, sm: 2, md: 3, lg: 4 }} 
        sx={{ 
          mb: { xs: 2, sm: 3, md: 4, lg: 5 },
          justifyContent: 'center',
          width: '100%'
        }} 
        className="dashboard-grid"
      >
        <Grid item xs={12} sm={6} md={4} lg={3} xl={2}>
          <StatCard
            title="Total Articles"
            value={dashboard.articleCount.toLocaleString()}
            icon={<ArticleIcon />}
            color="primary"
            subtitle="Processed articles"
            trend="+12% this week"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4} lg={3} xl={2}>
          <StatCard
            title="Clusters"
            value={dashboard.clusterCount}
            icon={<ClusterIcon />}
            color="secondary"
            subtitle="Topic clusters"
            trend="+5 new today"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4} lg={3} xl={2}>
          <StatCard
            title="Entities"
            value={dashboard.entityCount.toLocaleString()}
            icon={<PersonIcon />}
            color="success"
            subtitle="Extracted entities"
            trend="+23% this week"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4} lg={3} xl={2}>
          <StatCard
            title="Sources"
            value={dashboard.sourceCount}
            icon={<SourceIcon />}
            color="info"
            subtitle="Active feeds"
            trend="All healthy"
          />
        </Grid>
      </Grid>

      {/* Charts and Status */}
      <Grid 
        container 
        spacing={{ xs: 1, sm: 2, md: 3, lg: 4 }} 
        sx={{ 
          mb: { xs: 2, sm: 3, md: 4, lg: 5 },
          justifyContent: 'center',
          width: '100%'
        }} 
        className="dashboard-grid"
      >
        {/* Article Trends Chart */}
        <Grid item xs={12} lg={8} xl={9}>
          <Card className="dashboard-card">
            <CardContent className="dashboard-card-content">
              <Typography variant="h6" component="div" gutterBottom>
                Weekly Trends
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={articleTrendData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip />
                  <Line type="monotone" dataKey="articles" stroke="#8884d8" strokeWidth={2} />
                  <Line type="monotone" dataKey="clusters" stroke="#82ca9d" strokeWidth={2} />
                  <Line type="monotone" dataKey="entities" stroke="#ffc658" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* Pipeline Status */}
        <Grid item xs={12} lg={4} xl={3}>
          <PipelineStatusCard />
        </Grid>
      </Grid>

      {/* Source Health and System Health */}
      <Grid 
        container 
        spacing={{ xs: 1, sm: 2, md: 3, lg: 4 }} 
        sx={{ 
          mb: { xs: 2, sm: 3, md: 4, lg: 5 },
          justifyContent: 'center',
          width: '100%'
        }} 
        className="dashboard-grid"
      >
        <Grid item xs={12} lg={6} xl={7}>
          <Card className="dashboard-card">
            <CardContent className="dashboard-card-content">
              <Typography variant="h6" component="div" gutterBottom>
                Source Health Overview
              </Typography>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={sourceHealthData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="health" fill="#8884d8" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} lg={6} xl={5}>
          <SystemHealthCard />
        </Grid>
      </Grid>

      {/* Entity Distribution and Recent Articles */}
      <Grid 
        container 
        spacing={{ xs: 1, sm: 2, md: 3, lg: 4 }}
        sx={{ 
          justifyContent: 'center',
          width: '100%'
        }}
        className="dashboard-grid"
      >
        <Grid item xs={12} md={6} lg={4} xl={3}>
          <Card className="dashboard-card">
            <CardContent className="dashboard-card-content">
              <Typography variant="h6" component="div" gutterBottom>
                Entity Distribution
              </Typography>
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={entityTypeData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {entityTypeData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6} lg={4} xl={4}>
          <RecentArticlesCard />
        </Grid>

        <Grid item xs={12} md={6} lg={4} xl={5}>
          <FeedHealthCard />
        </Grid>
      </Grid>
    </Box>
  );
}
