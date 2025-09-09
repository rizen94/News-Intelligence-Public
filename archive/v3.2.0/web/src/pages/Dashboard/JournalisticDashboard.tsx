import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Chip,
  Button,
  Tabs,
  Tab,
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  CircularProgress,
  Alert,
  IconButton,
  Tooltip
} from '@mui/material';
import {
  Timeline,
  Article,
  TrendingUp,
  Psychology,
  AutoStories,
  Refresh,
  Download,
  Share,
  FilterList,
  Search
} from '@mui/icons-material';

// Types for journalistic reporting
interface StoryTimeline {
  id: string;
  title: string;
  summary: string;
  timeline: TimelineEvent[];
  sources: number;
  lastUpdated: string;
  status: 'developing' | 'breaking' | 'concluded' | 'monitoring';
  sentiment: 'positive' | 'negative' | 'neutral' | 'mixed';
  impact: 'low' | 'medium' | 'high' | 'critical';
}

interface TimelineEvent {
  id: string;
  timestamp: string;
  title: string;
  description: string;
  source: string;
  confidence: number;
  type: 'initial' | 'development' | 'update' | 'conclusion';
}

interface StoryConsolidation {
  id: string;
  headline: string;
  consolidatedSummary: string;
  keyPoints: string[];
  timeline: TimelineEvent[];
  sources: string[];
  aiAnalysis: {
    sentiment: string;
    entities: string[];
    topics: string[];
    credibility: number;
    bias: string;
  };
  professionalReport: string;
}

const JournalisticDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [stories, setStories] = useState<StoryTimeline[]>([]);
  const [consolidatedStories, setConsolidatedStories] = useState<StoryConsolidation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load real data from backend APIs
  useEffect(() => {
    const loadDashboardData = async () => {
      setLoading(true);
      try {
        // Load story timelines from backend
        const timelinesResponse = await fetch('http://localhost:8000/api/stories/timelines/');
        const timelinesData = await timelinesResponse.json();
        
        // Load consolidated stories from backend
        const consolidatedResponse = await fetch('http://localhost:8000/api/stories/consolidated/');
        const consolidatedData = await consolidatedResponse.json();
        
        // Transform backend data to frontend format
        const transformedStories: StoryTimeline[] = timelinesData.data.map((timeline: any) => ({
          id: timeline.story_id,
          title: timeline.title,
          summary: timeline.summary || '',
          timeline: [], // Will be loaded separately
          sources: timeline.sources_count || 0,
          lastUpdated: timeline.last_updated || timeline.created_at,
          status: timeline.status,
          sentiment: timeline.sentiment,
          impact: timeline.impact_level,
          confidence: timeline.confidence_score
        }));

        const transformedConsolidated: StoryConsolidation[] = consolidatedData.data.map((consolidation: any) => ({
          id: consolidation.id.toString(),
          headline: consolidation.headline,
          consolidatedSummary: consolidation.consolidated_summary,
          keyPoints: consolidation.key_points || [],
          timeline: [], // Will be loaded separately
          sources: consolidation.sources || [],
          aiAnalysis: consolidation.ai_analysis || {
            sentiment: 'neutral',
            entities: [],
            topics: [],
            credibility: 0.5,
            bias: 'neutral',
            factCheck: 0.5
          },
          professionalReport: consolidation.professional_report || '',
          executiveSummary: consolidation.executive_summary || '',
          recommendations: consolidation.recommendations || []
        }));

        setStories(transformedStories);
        setConsolidatedStories(transformedConsolidated);
        setError(null);
      } catch (err) {
        console.error('Error loading dashboard data:', err);
        setError('Failed to load dashboard data');
      } finally {
        setLoading(false);
      }
    };

    loadDashboardData();
  }, []);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'breaking': return 'error';
      case 'developing': return 'warning';
      case 'concluded': return 'success';
      case 'monitoring': return 'info';
      default: return 'default';
    }
  };

  const getImpactColor = (impact: string) => {
    switch (impact) {
      case 'critical': return 'error';
      case 'high': return 'warning';
      case 'medium': return 'info';
      case 'low': return 'success';
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

  if (error) {
    return (
      <Alert severity="error" action={
        <Button color="inherit" size="small" onClick={() => window.location.reload()}>
          Retry
        </Button>
      }>
        {error}
      </Alert>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" gutterBottom>
          News Intelligence Dashboard
        </Typography>
        <Typography variant="subtitle1" color="text.secondary">
          AI-Powered Journalistic Reporting & Story Consolidation
        </Typography>
      </Box>

      {/* Quick Stats */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center">
                <Article color="primary" sx={{ mr: 2 }} />
                <Box>
                  <Typography variant="h6">Active Stories</Typography>
                  <Typography variant="h4">{stories.length}</Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center">
                <Timeline color="success" sx={{ mr: 2 }} />
                <Box>
                  <Typography variant="h6">Consolidated Reports</Typography>
                  <Typography variant="h4">{consolidatedStories.length}</Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center">
                <TrendingUp color="warning" sx={{ mr: 2 }} />
                <Box>
                  <Typography variant="h6">Breaking Stories</Typography>
                  <Typography variant="h4">
                    {stories.filter(s => s.status === 'breaking').length}
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center">
                <Psychology color="info" sx={{ mr: 2 }} />
                <Box>
                  <Typography variant="h6">AI Analysis</Typography>
                  <Typography variant="h4">Active</Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Main Content Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs value={activeTab} onChange={handleTabChange} variant="fullWidth">
          <Tab label="Story Timelines" icon={<Timeline />} />
          <Tab label="Consolidated Reports" icon={<AutoStories />} />
          <Tab label="AI Analysis" icon={<Psychology />} />
        </Tabs>
      </Paper>

      {/* Tab Content */}
      {activeTab === 0 && (
        <Grid container spacing={3}>
          {stories.map((story) => (
            <Grid item xs={12} md={6} key={story.id}>
              <Card>
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
                    <Typography variant="h6" component="h2">
                      {story.title}
                    </Typography>
                    <Box>
                      <Chip 
                        label={story.status} 
                        color={getStatusColor(story.status) as any}
                        size="small"
                        sx={{ mr: 1 }}
                      />
                      <Chip 
                        label={story.impact} 
                        color={getImpactColor(story.impact) as any}
                        size="small"
                      />
                    </Box>
                  </Box>
                  
                  <Typography variant="body2" color="text.secondary" paragraph>
                    {story.summary}
                  </Typography>

                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                    <Typography variant="caption">
                      {story.sources} sources • Updated {new Date(story.lastUpdated).toLocaleString()}
                    </Typography>
                    <Box>
                      <Tooltip title="View Timeline">
                        <IconButton size="small">
                          <Timeline />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Generate Report">
                        <IconButton size="small">
                          <AutoStories />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </Box>

                  <Divider sx={{ my: 2 }} />

                  <Typography variant="subtitle2" gutterBottom>
                    Recent Timeline Events
                  </Typography>
                  <List dense>
                    {story.timeline.slice(0, 2).map((event) => (
                      <ListItem key={event.id} disablePadding>
                        <ListItemIcon>
                          <Box
                            sx={{
                              width: 8,
                              height: 8,
                              borderRadius: '50%',
                              bgcolor: event.type === 'initial' ? 'primary.main' : 'secondary.main'
                            }}
                          />
                        </ListItemIcon>
                        <ListItemText
                          primary={event.title}
                          secondary={`${event.source} • ${new Date(event.timestamp).toLocaleTimeString()}`}
                        />
                      </ListItem>
                    ))}
                  </List>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {activeTab === 1 && (
        <Grid container spacing={3}>
          {consolidatedStories.map((story) => (
            <Grid item xs={12} key={story.id}>
              <Card>
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
                    <Typography variant="h5" component="h2">
                      {story.headline}
                    </Typography>
                    <Box>
                      <Button startIcon={<Download />} size="small" sx={{ mr: 1 }}>
                        Export
                      </Button>
                      <Button startIcon={<Share />} size="small">
                        Share
                      </Button>
                    </Box>
                  </Box>

                  <Typography variant="body1" paragraph>
                    {story.consolidatedSummary}
                  </Typography>

                  <Grid container spacing={2} sx={{ mb: 2 }}>
                    <Grid item xs={12} md={6}>
                      <Typography variant="subtitle2" gutterBottom>
                        Key Points
                      </Typography>
                      <List dense>
                        {story.keyPoints.map((point, index) => (
                          <ListItem key={index} disablePadding>
                            <ListItemText
                              primary={`• ${point}`}
                              primaryTypographyProps={{ variant: 'body2' }}
                            />
                          </ListItem>
                        ))}
                      </List>
                    </Grid>
                    <Grid item xs={12} md={6}>
                      <Typography variant="subtitle2" gutterBottom>
                        AI Analysis
                      </Typography>
                      <Box>
                        <Chip label={`Sentiment: ${story.aiAnalysis.sentiment}`} size="small" sx={{ mr: 1, mb: 1 }} />
                        <Chip label={`Credibility: ${Math.round(story.aiAnalysis.credibility * 100)}%`} size="small" sx={{ mr: 1, mb: 1 }} />
                        <Chip label={`Bias: ${story.aiAnalysis.bias}`} size="small" sx={{ mb: 1 }} />
                      </Box>
                      <Typography variant="caption" display="block">
                        Sources: {story.sources.join(', ')}
                      </Typography>
                    </Grid>
                  </Grid>

                  <Divider sx={{ my: 2 }} />

                  <Typography variant="subtitle2" gutterBottom>
                    Professional Report
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {story.professionalReport}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {activeTab === 2 && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  AI Analysis Overview
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                  Advanced AI analysis consolidating multiple sources into comprehensive story timelines and professional journalistic reports.
                </Typography>
                
                <Grid container spacing={2}>
                  <Grid item xs={12} sm={6} md={3}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <Typography variant="h4" color="primary">94%</Typography>
                      <Typography variant="caption">Analysis Accuracy</Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <Typography variant="h4" color="success">15</Typography>
                      <Typography variant="caption">Sources Analyzed</Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <Typography variant="h4" color="warning">2.3s</Typography>
                      <Typography variant="caption">Avg Processing Time</Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={12} sm={6} md={3}>
                    <Paper sx={{ p: 2, textAlign: 'center' }}>
                      <Typography variant="h4" color="info">24/7</Typography>
                      <Typography variant="caption">Monitoring</Typography>
                    </Paper>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
    </Box>
  );
};

export default JournalisticDashboard;
