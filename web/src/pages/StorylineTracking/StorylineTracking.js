import {
  TrendingUp,
  Assessment,
  Timeline,
  AutoAwesome,
  Refresh,
  Download,
  Visibility,
  Delete,
} from '@mui/icons-material';
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
  IconButton,
  Tooltip,
} from '@mui/material';
import React, { useState, useEffect } from 'react';

import newsSystemService from '../../services/newsSystemService';
import './StorylineTracking.css';

const StorylineTracking = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Topic Cloud State
  const [topicCloud, setTopicCloud] = useState(null);
  const [breakingTopics, setBreakingTopics] = useState([]);
  const [daysToAnalyze, setDaysToAnalyze] = useState(1);

  // Story Dossier State
  const [storyId, setStoryId] = useState('');
  const [dossier, setDossier] = useState(null);
  const [includeRag, setIncludeRag] = useState(true);

  // Deduplication State
  const [duplicateGroups, setDuplicateGroups] = useState([]);
  const [dedupStats, setDedupStats] = useState(null);
  const [similarityThreshold, setSimilarityThreshold] = useState(0.85);

  // Daily Briefing State
  const [dailyBriefing, setDailyBriefing] = useState(null);
  const [weeklyBriefing, setWeeklyBriefing] = useState(null);
  const [briefingDate, setBriefingDate] = useState(
    new Date().toISOString().split('T')[0],
  );

  useEffect(() => {
    // Load initial data
    loadDeduplicationStats();
  }, []);

  const loadDeduplicationStats = async() => {
    try {
      setLoading(true);
      const response = await newsSystemService.getDeduplicationStats();
      if (response.success) {
        setDedupStats(response.result);
      }
    } catch (error) {
      setError('Failed to load deduplication statistics');
    } finally {
      setLoading(false);
    }
  };

  const generateTopicCloud = async() => {
    try {
      setLoading(true);
      setError(null);

      const response = await newsSystemService.getTopicCloud(daysToAnalyze);
      if (response.success) {
        setTopicCloud(response.result.topic_cloud);
        setBreakingTopics(response.result.breaking_topics);
      } else {
        setError('Failed to generate topic cloud');
      }
    } catch (error) {
      setError('Failed to generate topic cloud');
    } finally {
      setLoading(false);
    }
  };

  const generateStoryDossier = async() => {
    if (!storyId.trim()) {
      setError('Please enter a story ID or topic');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await newsSystemService.getStoryDossier(
        storyId,
        includeRag,
      );
      if (response.success) {
        setDossier(response.result);
      } else {
        setError('Failed to generate story dossier');
      }
    } catch (error) {
      setError('Failed to generate story dossier');
    } finally {
      setLoading(false);
    }
  };

  const detectDuplicates = async() => {
    try {
      setLoading(true);
      setError(null);

      const response = await newsSystemService.detectDuplicates(
        similarityThreshold,
      );
      if (response.success) {
        setDuplicateGroups(response.result.duplicate_groups);
      } else {
        setError('Failed to detect duplicates');
      }
    } catch (error) {
      setError('Failed to detect duplicates');
    } finally {
      setLoading(false);
    }
  };

  const removeDuplicates = async() => {
    try {
      setLoading(true);
      setError(null);

      const response = await newsSystemService.removeDuplicates(
        true,
        similarityThreshold,
      );
      if (response.success) {
        setError(null);
        // Refresh stats and duplicate groups
        await loadDeduplicationStats();
        await detectDuplicates();
      } else {
        setError('Failed to remove duplicates');
      }
    } catch (error) {
      setError('Failed to remove duplicates');
    } finally {
      setLoading(false);
    }
  };

  const generateDailyBriefing = async() => {
    try {
      setLoading(true);
      setError(null);

      const response = await newsSystemService.generateDailyBriefing(
        briefingDate,
      );
      if (response.success) {
        setDailyBriefing(response.result);
      } else {
        setError('Failed to generate daily briefing');
      }
    } catch (error) {
      setError('Failed to generate daily briefing');
    } finally {
      setLoading(false);
    }
  };

  const generateWeeklyBriefing = async() => {
    try {
      setLoading(true);
      setError(null);

      const response = await newsSystemService.generateWeeklyBriefing();
      if (response.success) {
        setWeeklyBriefing(response.result);
      } else {
        setError('Failed to generate weekly briefing');
      }
    } catch (error) {
      setError('Failed to generate weekly briefing');
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (event, newValue) => {
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
              onChange={e => setIncludeRag(e.target.value)}
              label='Include RAG'
            >
              <MenuItem value={true}>Yes</MenuItem>
              <MenuItem value={false}>No</MenuItem>
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

  const renderDeduplication = () => (
    <Box>
      <Typography variant='h6' gutterBottom>
        Content Deduplication
      </Typography>

      {dedupStats && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Typography variant='h4' color='primary'>
                  {dedupStats.total_articles}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  Total Articles
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Typography variant='h4' color='error'>
                  {dedupStats.duplicate_count}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  Duplicates Removed
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Typography variant='h4' color='warning'>
                  {dedupStats.deduplication_rate}%
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  Deduplication Rate
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Typography variant='h4' color='success'>
                  {dedupStats.recent_duplicates}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  Recent (7 days)
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <TextField
            fullWidth
            label='Similarity Threshold'
            type='number'
            value={similarityThreshold}
            onChange={e =>
              setSimilarityThreshold(parseFloat(e.target.value) || 0.85)
            }
            inputProps={{ min: 0.1, max: 1.0, step: 0.05 }}
            helperText='Higher values = more strict duplicate detection'
          />
        </Grid>
        <Grid item xs={12} md={3}>
          <Button
            variant='outlined'
            onClick={detectDuplicates}
            disabled={loading}
            startIcon={<Visibility />}
            fullWidth
          >
            Detect Duplicates
          </Button>
        </Grid>
        <Grid item xs={12} md={3}>
          <Button
            variant='contained'
            color='error'
            onClick={removeDuplicates}
            disabled={loading || duplicateGroups.length === 0}
            startIcon={<Delete />}
            fullWidth
          >
            Remove Duplicates
          </Button>
        </Grid>
      </Grid>

      {duplicateGroups.length > 0 && (
        <Card>
          <CardContent>
            <Typography variant='h6' gutterBottom>
              Duplicate Groups ({duplicateGroups.length})
            </Typography>
            <List>
              {duplicateGroups.map((group, index) => (
                <ListItem key={index} divider>
                  <ListItemText
                    primary={group.primary_title}
                    secondary={`Primary: ${group.primary_source} • ${group.primary_date} • Similarity: ${group.similarity_score}`}
                  />
                  <ListItemSecondaryAction>
                    <Chip
                      label={`${group.group_size} articles`}
                      color='warning'
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

  const renderDailyBriefing = () => (
    <Box>
      <Typography variant='h6' gutterBottom>
        Daily Intelligence Briefing
      </Typography>

      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <TextField
            fullWidth
            label='Briefing Date'
            type='date'
            value={briefingDate}
            onChange={e => setBriefingDate(e.target.value)}
            InputLabelProps={{ shrink: true }}
          />
        </Grid>
        <Grid item xs={12} md={6}>
          <Button
            variant='contained'
            onClick={generateDailyBriefing}
            disabled={loading}
            startIcon={<AutoAwesome />}
            fullWidth
          >
            Generate Daily Briefing
          </Button>
        </Grid>
      </Grid>

      {dailyBriefing && (
        <Card>
          <CardContent>
            <Typography variant='h6' gutterBottom>
              Daily Briefing: {dailyBriefing.briefing_date}
            </Typography>

            <Grid container spacing={2} sx={{ mb: 2 }}>
              <Grid item xs={12} md={3}>
                <Typography variant='h4' color='primary'>
                  {dailyBriefing.statistics?.total_articles || 0}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  Total Articles
                </Typography>
              </Grid>
              <Grid item xs={12} md={3}>
                <Typography variant='h4' color='success'>
                  {dailyBriefing.statistics?.today_articles || 0}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  Today's Articles
                </Typography>
              </Grid>
              <Grid item xs={12} md={3}>
                <Typography variant='h4' color='warning'>
                  {dailyBriefing.statistics?.breaking_stories || 0}
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  Breaking Stories
                </Typography>
              </Grid>
              <Grid item xs={12} md={3}>
                <Typography variant='h4' color='info'>
                  {dailyBriefing.statistics?.success_rate || 0}%
                </Typography>
                <Typography variant='body2' color='text.secondary'>
                  Success Rate
                </Typography>
              </Grid>
            </Grid>

            <Divider sx={{ my: 2 }} />

            <Typography variant='h6' gutterBottom>
              Recommendations
            </Typography>
            {dailyBriefing.sections?.recommendations?.priority_actions?.map(
              (rec, index) => (
                <Alert key={index} severity='info' sx={{ mb: 1 }}>
                  {rec}
                </Alert>
              ),
            )}
          </CardContent>
        </Card>
      )}

      <Box sx={{ mt: 3 }}>
        <Button
          variant='outlined'
          onClick={generateWeeklyBriefing}
          disabled={loading}
          startIcon={<Timeline />}
        >
          Generate Weekly Briefing
        </Button>
      </Box>

      {weeklyBriefing && (
        <Card sx={{ mt: 2 }}>
          <CardContent>
            <Typography variant='h6' gutterBottom>
              Weekly Briefing: {weeklyBriefing.week_start} to{' '}
              {weeklyBriefing.week_end}
            </Typography>
            <Typography variant='body2' color='text.secondary' gutterBottom>
              {weeklyBriefing.weekly_summary?.total_articles || 0} articles •{' '}
              {weeklyBriefing.weekly_summary?.total_breaking_stories || 0}{' '}
              breaking stories
            </Typography>
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
        Manage storylines, detect duplicates, and generate automated
        intelligence briefings
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
          <Tab label='Deduplication' icon={<Delete />} />
          <Tab label='Daily Briefings' icon={<AutoAwesome />} />
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
        {activeTab === 2 && renderDeduplication()}
        {activeTab === 3 && renderDailyBriefing()}
      </Box>
    </Box>
  );
};

export default StorylineTracking;
