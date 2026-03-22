import { TrendingUp, Assessment } from '@mui/icons-material';
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
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
} from '@mui/material';
import React, { useState } from 'react';

import apiService from '../../services/apiService';
import './StorylineTracking.css';

interface BreakingTopic {
  title: string;
  source: string;
  published_date: string;
  quality_score: number;
  urgency: string;
}

interface TopicCloudData {
  top_topics: Record<string, number>;
  categories: Record<string, number>;
}

interface DossierData {
  story_id: string;
  article_count: number;
  time_span: string;
  generated_at: string;
  dossier: string;
}

const StorylineTracking: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [topicCloud, setTopicCloud] = useState<TopicCloudData | null>(null);
  const [breakingTopics, setBreakingTopics] = useState<BreakingTopic[]>([]);
  const [daysToAnalyze, setDaysToAnalyze] = useState(1);

  const [storyId, setStoryId] = useState('');
  const [dossier, setDossier] = useState<DossierData | null>(null);
  const [includeRag, setIncludeRag] = useState<boolean>(true);

  const generateTopicCloud = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await apiService.getTopicCloud(daysToAnalyze);
      if (response.success) {
        setTopicCloud(response.result.topic_cloud);
        setBreakingTopics(response.result.breaking_topics);
      } else {
        setError('Failed to generate topic cloud');
      }
    } catch {
      setError('Failed to generate topic cloud');
    } finally {
      setLoading(false);
    }
  };

  const generateStoryDossier = async () => {
    if (!storyId.trim()) {
      setError('Please enter a story ID or topic');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await apiService.getStoryDossier(storyId, includeRag);
      if (response.success) {
        setDossier(response.result);
      } else {
        setError('Failed to generate story dossier');
      }
    } catch {
      setError('Failed to generate story dossier');
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const renderTopicCloud = () => (
    <Box>
      <Typography variant='h6' gutterBottom>
        Topic Cloud & Breaking News
      </Typography>

      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <TextField
            fullWidth
            label='Days to Analyze'
            type='number'
            value={daysToAnalyze}
            onChange={e => setDaysToAnalyze(parseInt(e.target.value) || 1)}
            inputProps={{ min: 1, max: 30 }}
          />
        </Grid>
        <Grid item xs={12} md={6}>
          <Button
            variant='contained'
            onClick={generateTopicCloud}
            disabled={loading}
            startIcon={<TrendingUp />}
            fullWidth
          >
            Generate Topic Cloud
          </Button>
        </Grid>
      </Grid>

      {topicCloud && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant='h6' gutterBottom>
                  Top Topics
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {Object.entries(topicCloud.top_topics || {}).map(
                    ([topic, count]) => (
                      <Chip
                        key={topic}
                        label={`${topic} (${count})`}
                        color='primary'
                        variant='outlined'
                      />
                    ),
                  )}
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant='h6' gutterBottom>
                  Categories
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {Object.entries(topicCloud.categories || {}).map(
                    ([category, count]) => (
                      <Chip
                        key={category}
                        label={`${category} (${count})`}
                        color='secondary'
                        variant='outlined'
                      />
                    ),
                  )}
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {breakingTopics.length > 0 && (
        <Card sx={{ mt: 3 }}>
          <CardContent>
            <Typography variant='h6' gutterBottom>
              Breaking Topics ({breakingTopics.length})
            </Typography>
            <List>
              {breakingTopics.map((topic, index) => (
                <ListItem key={index} divider>
                  <ListItemText
                    primary={topic.title}
                    secondary={`${topic.source} • ${topic.published_date} • Quality: ${topic.quality_score}`}
                  />
                  <ListItemSecondaryAction>
                    <Chip
                      label={topic.urgency}
                      color={topic.urgency === 'high' ? 'error' : 'warning'}
                      size='small'
                    />
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
            </List>
          </CardContent>
        </Card>
      )}
    </Box>
  );

  const renderStoryDossier = () => (
    <Box>
      <Typography variant='h6' gutterBottom>
        Story Dossier Generation
      </Typography>

      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <TextField
            fullWidth
            label='Story ID or Topic'
            value={storyId}
            onChange={e => setStoryId(e.target.value)}
            placeholder='e.g., ai-regulation, climate-change'
          />
        </Grid>
        <Grid item xs={12} md={3}>
          <FormControl fullWidth>
            <InputLabel>Include RAG</InputLabel>
            <Select
              value={includeRag}
              onChange={e => setIncludeRag(e.target.value as boolean)}
              label='Include RAG'
            >
              <MenuItem value={true as any}>Yes</MenuItem>
              <MenuItem value={false as any}>No</MenuItem>
            </Select>
          </FormControl>
        </Grid>
        <Grid item xs={12} md={3}>
          <Button
            variant='contained'
            onClick={generateStoryDossier}
            disabled={loading || !storyId.trim()}
            startIcon={<Assessment />}
            fullWidth
          >
            Generate Dossier
          </Button>
        </Grid>
      </Grid>

      {dossier && (
        <Card>
          <CardContent>
            <Typography variant='h6' gutterBottom>
              Dossier: {dossier.story_id}
            </Typography>
            <Typography variant='body2' color='text.secondary' gutterBottom>
              {dossier.article_count} articles • {dossier.time_span} •
              Generated: {dossier.generated_at}
            </Typography>

            <Divider sx={{ my: 2 }} />

            <Box sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}>
              {dossier.dossier}
            </Box>
          </CardContent>
        </Card>
      )}
    </Box>
  );

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant='h4' gutterBottom>
        Storyline Tracking & Intelligence
      </Typography>
      <Typography variant='body1' color='text.secondary' sx={{ mb: 3 }}>
        Explore topic clouds and generate story dossiers
      </Typography>

      {error && (
        <Alert severity='error' sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs value={activeTab} onChange={handleTabChange}>
          <Tab label='Topic Cloud' icon={<TrendingUp />} />
          <Tab label='Story Dossiers' icon={<Assessment />} />
        </Tabs>
      </Box>

      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
          <CircularProgress />
        </Box>
      )}

      <Box sx={{ mt: 2 }}>
        {activeTab === 0 && renderTopicCloud()}
        {activeTab === 1 && renderStoryDossier()}
      </Box>
    </Box>
  );
};

export default StorylineTracking;
