import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Tabs,
  Tab,
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  IconButton,
  Tooltip,
  LinearProgress,
  Alert,
  Badge,
  Avatar,
  Stack,
  CardActions,
  CardHeader,
  Button,
  Chip,
  useTheme,
  useMediaQuery
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
  Search,
  Schedule,
  Public,
  TrendingDown,
  TrendingFlat
} from '@mui/icons-material';

// Import responsive components
import ResponsiveCard from '../../components/Layout/ResponsiveCard';
import ResponsiveGrid, { CardGrid, StatsGrid } from '../../components/Layout/ResponsiveGrid';
import ResponsiveLoading from '../../components/Layout/ResponsiveLoading';

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
  confidence?: number;
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
    factCheck?: number;
  };
  professionalReport?: string;
  executiveSummary?: string;
  recommendations?: string[];
}

const ResponsiveJournalisticDashboard: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const isTablet = useMediaQuery(theme.breakpoints.down('md'));

  const [stories, setStories] = useState<StoryTimeline[]>([]);
  const [consolidatedStories, setConsolidatedStories] = useState<StoryConsolidation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState(0);

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

  const getSentimentIcon = (sentiment: string) => {
    switch (sentiment) {
      case 'positive': return <TrendingUp color="success" />;
      case 'negative': return <TrendingDown color="error" />;
      case 'neutral': return <TrendingFlat color="info" />;
      case 'mixed': return <Psychology color="warning" />;
      default: return <TrendingFlat color="info" />;
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
    return <ResponsiveLoading type="skeleton" count={6} height={200} />;
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant={isMobile ? "h5" : "h4"} component="h1" gutterBottom>
          Journalistic Intelligence Dashboard
        </Typography>
        <Typography variant="body1" color="text.secondary">
          AI-powered story consolidation and professional reporting
        </Typography>
      </Box>

      {/* Stats Overview */}
      <StatsGrid sx={{ mb: 3 }}>
        <ResponsiveCard
          title="Active Stories"
          subtitle="Currently tracking"
          compact
          status="info"
        >
          <Typography variant="h4" color="primary" sx={{ fontWeight: 'bold' }}>
            {stories.length}
          </Typography>
        </ResponsiveCard>

        <ResponsiveCard
          title="Consolidated Reports"
          subtitle="Professional reports generated"
          compact
          status="success"
        >
          <Typography variant="h4" color="success.main" sx={{ fontWeight: 'bold' }}>
            {consolidatedStories.length}
          </Typography>
        </ResponsiveCard>

        <ResponsiveCard
          title="Total Sources"
          subtitle="Across all stories"
          compact
          status="info"
        >
          <Typography variant="h4" color="info.main" sx={{ fontWeight: 'bold' }}>
            {stories.reduce((sum, story) => sum + story.sources, 0)}
          </Typography>
        </ResponsiveCard>

        <ResponsiveCard
          title="Breaking Stories"
          subtitle="High priority stories"
          compact
          status="error"
        >
          <Typography variant="h4" color="error.main" sx={{ fontWeight: 'bold' }}>
            {stories.filter(story => story.status === 'breaking').length}
          </Typography>
        </ResponsiveCard>
      </StatsGrid>

      {/* Main Content Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs
          value={activeTab}
          onChange={handleTabChange}
          variant={isMobile ? "scrollable" : "standard"}
          scrollButtons="auto"
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab label="Story Timelines" icon={<Timeline />} iconPosition="start" />
          <Tab label="Consolidated Reports" icon={<AutoStories />} iconPosition="start" />
          <Tab label="AI Analysis" icon={<Psychology />} iconPosition="start" />
        </Tabs>

        {/* Story Timelines Tab */}
        {activeTab === 0 && (
          <Box sx={{ p: 3 }}>
            <CardGrid>
              {stories.map((story) => (
                <ResponsiveCard
                  key={story.id}
                  title={story.title}
                  subtitle={story.summary}
                  tags={[story.status, story.sentiment, story.impact]}
                  status={getStatusColor(story.status)}
                  action={
                    <Button size="small" startIcon={<Article />}>
                      View Details
                    </Button>
                  }
                >
                  <Stack spacing={2}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      {getSentimentIcon(story.sentiment)}
                      <Typography variant="body2" color="text.secondary">
                        {story.sentiment} sentiment
                      </Typography>
                    </Box>

                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Public fontSize="small" />
                      <Typography variant="body2" color="text.secondary">
                        {story.sources} sources
                      </Typography>
                    </Box>

                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Schedule fontSize="small" />
                      <Typography variant="body2" color="text.secondary">
                        Updated {new Date(story.lastUpdated).toLocaleDateString()}
                      </Typography>
                    </Box>

                    {story.confidence && (
                      <Box>
                        <Typography variant="body2" color="text.secondary" gutterBottom>
                          Confidence: {Math.round(story.confidence * 100)}%
                        </Typography>
                        <LinearProgress
                          variant="determinate"
                          value={story.confidence * 100}
                          color={story.confidence > 0.7 ? 'success' : story.confidence > 0.4 ? 'warning' : 'error'}
                        />
                      </Box>
                    )}
                  </Stack>
                </ResponsiveCard>
              ))}
            </CardGrid>
          </Box>
        )}

        {/* Consolidated Reports Tab */}
        {activeTab === 1 && (
          <Box sx={{ p: 3 }}>
            <CardGrid>
              {consolidatedStories.map((report) => (
                <ResponsiveCard
                  key={report.id}
                  title={report.headline}
                  subtitle={report.consolidatedSummary}
                  tags={report.aiAnalysis.topics.slice(0, 3)}
                  status="success"
                  action={
                    <Stack direction="row" spacing={1}>
                      <Button size="small" startIcon={<Download />}>
                        Export
                      </Button>
                      <Button size="small" startIcon={<Share />}>
                        Share
                      </Button>
                    </Stack>
                  }
                >
                  <Stack spacing={2}>
                    <Box>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Key Points:
                      </Typography>
                      <List dense>
                        {report.keyPoints.slice(0, 3).map((point, index) => (
                          <ListItem key={index} sx={{ py: 0 }}>
                            <ListItemIcon>
                              <Typography variant="body2" color="primary">
                                •
                              </Typography>
                            </ListItemIcon>
                            <ListItemText
                              primary={point}
                              primaryTypographyProps={{ variant: 'body2' }}
                            />
                          </ListItem>
                        ))}
                      </List>
                    </Box>

                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      {getSentimentIcon(report.aiAnalysis.sentiment)}
                      <Typography variant="body2" color="text.secondary">
                        {report.aiAnalysis.sentiment} sentiment
                      </Typography>
                    </Box>

                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Public fontSize="small" />
                      <Typography variant="body2" color="text.secondary">
                        {report.sources.length} sources
                      </Typography>
                    </Box>

                    <Box>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Credibility: {Math.round(report.aiAnalysis.credibility * 100)}%
                      </Typography>
                      <LinearProgress
                        variant="determinate"
                        value={report.aiAnalysis.credibility * 100}
                        color={report.aiAnalysis.credibility > 0.7 ? 'success' : report.aiAnalysis.credibility > 0.4 ? 'warning' : 'error'}
                      />
                    </Box>
                  </Stack>
                </ResponsiveCard>
              ))}
            </CardGrid>
          </Box>
        )}

        {/* AI Analysis Tab */}
        {activeTab === 2 && (
          <Box sx={{ p: 3 }}>
            <Alert severity="info" sx={{ mb: 3 }}>
              AI Analysis features are available when Ollama is running. 
              Currently showing graceful fallback mode.
            </Alert>
            
            <CardGrid>
              {stories.map((story) => (
                <ResponsiveCard
                  key={story.id}
                  title={`AI Analysis: ${story.title}`}
                  subtitle="Click to analyze with AI"
                  status="warning"
                  action={
                    <Button size="small" startIcon={<Psychology />}>
                      Analyze
                    </Button>
                  }
                >
                  <Typography variant="body2" color="text.secondary">
                    AI analysis will provide sentiment analysis, entity extraction, 
                    and professional report generation for this story.
                  </Typography>
                </ResponsiveCard>
              ))}
            </CardGrid>
          </Box>
        )}
      </Paper>
    </Box>
  );
};

export default ResponsiveJournalisticDashboard;

