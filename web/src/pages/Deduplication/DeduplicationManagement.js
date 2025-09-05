import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  CardHeader,
  Paper,
  Button,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Alert,
  CircularProgress,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
  Divider,
  Switch,
  FormControlLabel,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Stack,
  Badge,
  Avatar,
  Tabs,
  Tab,
  Slider,
  Checkbox,
  FormGroup,
  FormControlLabel as FormControlLabelCheckbox
} from '@mui/material';
import {
  ContentCopy as DeduplicationIcon,
  Search as SearchIcon,
  FilterList as FilterIcon,
  Delete as DeleteIcon,
  Refresh as RefreshIcon,
  Settings as SettingsIcon,
  Assessment as AssessmentIcon,
  Timeline as TimelineIcon,
  Article as ArticleIcon,
  Compare as CompareIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  Visibility as VisibilityIcon,
  AutoAwesome as AutoAwesomeIcon,
  Speed as SpeedIcon,
  Memory as MemoryIcon,
  Analytics as AnalyticsIcon,
  BarChart as BarChartIcon,
  PieChart as PieChartIcon,
  ShowChart as ShowChartIcon,
  ExpandMore as ExpandMoreIcon,
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Pause as PauseIcon,
  Download as DownloadIcon,
  Upload as UploadIcon,
  History as HistoryIcon,
  Schedule as ScheduleIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  TrendingFlat as TrendingFlatIcon,
  Security as SecurityIcon,
  Public as PublicIcon,
  Business as BusinessIcon,
  Person as PersonIcon,
  LocationOn as LocationIcon,
  Category as CategoryIcon,
  Language as LanguageIcon,
  Source as SourceIcon,
  Link as LinkIcon,
  ContentCopy as ContentCopyIcon,
  CompareArrows as CompareArrowsIcon,
  Merge as MergeIcon,
  Split as SplitIcon,
  Flag as FlagIcon,
  Star as StarIcon,
  Bookmark as BookmarkIcon,
  BookmarkBorder as BookmarkBorderIcon,
  ThumbUp as ThumbUpIcon,
  ThumbDown as ThumbDownIcon,
  ThumbUpOutlined as ThumbUpOutlinedIcon,
  ThumbDownOutlined as ThumbDownOutlinedIcon
} from '@mui/icons-material';
import newsSystemService from '../../services/newsSystemService';

const DeduplicationManagement = () => {
  const [duplicates, setDuplicates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterSimilarity, setFilterSimilarity] = useState('');
  const [sortBy, setSortBy] = useState('similarity_score');
  const [sortOrder, setSortOrder] = useState('desc');
  const [activeTab, setActiveTab] = useState(0);
  const [selectedDuplicate, setSelectedDuplicate] = useState(null);
  const [showSettingsDialog, setShowSettingsDialog] = useState(false);
  const [showStatsDialog, setShowStatsDialog] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [stats, setStats] = useState(null);
  const [settings, setSettings] = useState({
    similarity_threshold: 0.85,
    auto_remove: false,
    min_article_length: 100,
    max_articles_to_process: 1000,
    enabled_algorithms: ['content_similarity', 'title_similarity', 'url_similarity'],
    exclude_sources: [],
    include_sources: [],
    time_window_hours: 24
  });

  useEffect(() => {
    fetchDuplicates();
    fetchStats();
    fetchSettings();
    const interval = setInterval(() => {
      fetchDuplicates();
      fetchStats();
    }, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchDuplicates = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await newsSystemService.getDuplicates();
      setDuplicates(response.duplicates || []);
    } catch (err) {
      console.error('Error fetching duplicates:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await newsSystemService.getDeduplicationStats();
      setStats(response);
    } catch (err) {
      console.error('Error fetching deduplication stats:', err);
    }
  };

  const fetchSettings = async () => {
    try {
      const response = await newsSystemService.getDeduplicationSettings();
      setSettings(response.settings || settings);
    } catch (err) {
      console.error('Error fetching deduplication settings:', err);
    }
  };

  const handleDetectDuplicates = async () => {
    try {
      setProcessing(true);
      await newsSystemService.detectDuplicates(settings);
      fetchDuplicates();
      fetchStats();
    } catch (err) {
      console.error('Error detecting duplicates:', err);
      setError(err.message);
    } finally {
      setProcessing(false);
    }
  };

  const handleRemoveDuplicates = async (duplicateIds, autoRemove = false) => {
    try {
      setProcessing(true);
      await newsSystemService.removeDuplicates(duplicateIds, autoRemove);
      fetchDuplicates();
      fetchStats();
    } catch (err) {
      console.error('Error removing duplicates:', err);
      setError(err.message);
    } finally {
      setProcessing(false);
    }
  };

  const handleMarkAsNotDuplicate = async (duplicateId) => {
    try {
      setProcessing(true);
      await newsSystemService.markAsNotDuplicate(duplicateId);
      fetchDuplicates();
      fetchStats();
    } catch (err) {
      console.error('Error marking as not duplicate:', err);
      setError(err.message);
    } finally {
      setProcessing(false);
    }
  };

  const handleUpdateSettings = async () => {
    try {
      setProcessing(true);
      await newsSystemService.updateDeduplicationSettings(settings);
      setShowSettingsDialog(false);
      fetchDuplicates();
      fetchStats();
    } catch (err) {
      console.error('Error updating settings:', err);
      setError(err.message);
    } finally {
      setProcessing(false);
    }
  };

  const getSimilarityColor = (score) => {
    if (score >= 0.9) return 'error';
    if (score >= 0.8) return 'warning';
    if (score >= 0.7) return 'info';
    return 'success';
  };

  const getSimilarityLabel = (score) => {
    if (score >= 0.9) return 'Very High';
    if (score >= 0.8) return 'High';
    if (score >= 0.7) return 'Medium';
    return 'Low';
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  const formatSimilarity = (score) => {
    return `${(score * 100).toFixed(1)}%`;
  };

  const filteredDuplicates = duplicates.filter(duplicate => {
    const matchesSearch = !searchQuery || 
      duplicate.article1.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      duplicate.article2.title.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = !filterStatus || duplicate.status === filterStatus;
    const matchesSimilarity = !filterSimilarity || 
      (filterSimilarity === 'high' && duplicate.similarity_score >= 0.8) ||
      (filterSimilarity === 'medium' && duplicate.similarity_score >= 0.6 && duplicate.similarity_score < 0.8) ||
      (filterSimilarity === 'low' && duplicate.similarity_score < 0.6);
    return matchesSearch && matchesStatus && matchesSimilarity;
  }).sort((a, b) => {
    const aValue = a[sortBy];
    const bValue = b[sortBy];
    if (sortOrder === 'asc') {
      return aValue > bValue ? 1 : -1;
    } else {
      return aValue < bValue ? 1 : -1;
    }
  });

  if (loading && duplicates.length === 0) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
        <Typography variant="h6" ml={2}>
          Loading duplicates...
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            Deduplication Management
          </Typography>
          <Typography variant="subtitle1" color="textSecondary">
            Detect, analyze, and manage duplicate articles across your news sources
          </Typography>
        </Box>
        <Box display="flex" gap={2}>
          <Tooltip title="Settings">
            <IconButton onClick={() => setShowSettingsDialog(true)}>
              <SettingsIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="Refresh">
            <IconButton onClick={fetchDuplicates} disabled={processing}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Button
            variant="contained"
            startIcon={<AutoAwesomeIcon />}
            onClick={handleDetectDuplicates}
            disabled={processing}
          >
            {processing ? <CircularProgress size={20} /> : 'Detect Duplicates'}
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Stats Overview */}
      {stats && (
        <Grid container spacing={3} mb={3}>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" justifyContent="space-between">
                  <Box>
                    <Typography color="textSecondary" gutterBottom>
                      Total Duplicates
                    </Typography>
                    <Typography variant="h4">
                      {stats.total_duplicates}
                    </Typography>
                    <Typography color="textSecondary" variant="body2">
                      {stats.pending_review} pending review
                    </Typography>
                  </Box>
                  <DeduplicationIcon sx={{ fontSize: 40, color: 'primary.main' }} />
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" justifyContent="space-between">
                  <Box>
                    <Typography color="textSecondary" gutterBottom>
                      High Similarity
                    </Typography>
                    <Typography variant="h4" color="error.main">
                      {stats.high_similarity}
                    </Typography>
                    <Typography color="textSecondary" variant="body2">
                      {stats.very_high_similarity} very high
                    </Typography>
                  </Box>
                  <WarningIcon sx={{ fontSize: 40, color: 'error.main' }} />
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" justifyContent="space-between">
                  <Box>
                    <Typography color="textSecondary" gutterBottom>
                      Removed Today
                    </Typography>
                    <Typography variant="h4" color="success.main">
                      {stats.removed_today}
                    </Typography>
                    <Typography color="textSecondary" variant="body2">
                      {stats.removed_this_week} this week
                    </Typography>
                  </Box>
                  <DeleteIcon sx={{ fontSize: 40, color: 'success.main' }} />
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" justifyContent="space-between">
                  <Box>
                    <Typography color="textSecondary" gutterBottom>
                      Accuracy Rate
                    </Typography>
                    <Typography variant="h4" color="info.main">
                      {stats.accuracy_rate}%
                    </Typography>
                    <Typography color="textSecondary" variant="body2">
                      Last 30 days
                    </Typography>
                  </Box>
                  <AssessmentIcon sx={{ fontSize: 40, color: 'info.main' }} />
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs value={activeTab} onChange={(e, newValue) => setActiveTab(newValue)}>
          <Tab label="Duplicate Pairs" icon={<CompareIcon />} />
          <Tab label="Statistics" icon={<BarChartIcon />} />
          <Tab label="Settings" icon={<SettingsIcon />} />
          <Tab label="History" icon={<HistoryIcon />} />
        </Tabs>
      </Box>

      {/* Duplicate Pairs Tab */}
      {activeTab === 0 && (
        <Box>
          {/* Filters */}
          <Paper sx={{ p: 2, mb: 3 }}>
            <Grid container spacing={2} alignItems="center">
              <Grid item xs={12} md={4}>
                <TextField
                  fullWidth
                  label="Search duplicates"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  InputProps={{
                    startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />
                  }}
                />
              </Grid>
              <Grid item xs={12} md={2}>
                <FormControl fullWidth>
                  <InputLabel>Status</InputLabel>
                  <Select
                    value={filterStatus}
                    label="Status"
                    onChange={(e) => setFilterStatus(e.target.value)}
                  >
                    <MenuItem value="">All</MenuItem>
                    <MenuItem value="pending">Pending</MenuItem>
                    <MenuItem value="confirmed">Confirmed</MenuItem>
                    <MenuItem value="rejected">Rejected</MenuItem>
                    <MenuItem value="removed">Removed</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={2}>
                <FormControl fullWidth>
                  <InputLabel>Similarity</InputLabel>
                  <Select
                    value={filterSimilarity}
                    label="Similarity"
                    onChange={(e) => setFilterSimilarity(e.target.value)}
                  >
                    <MenuItem value="">All</MenuItem>
                    <MenuItem value="high">High (80%+)</MenuItem>
                    <MenuItem value="medium">Medium (60-80%)</MenuItem>
                    <MenuItem value="low">Low (&lt;60%)</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={2}>
                <FormControl fullWidth>
                  <InputLabel>Sort By</InputLabel>
                  <Select
                    value={sortBy}
                    label="Sort By"
                    onChange={(e) => setSortBy(e.target.value)}
                  >
                    <MenuItem value="similarity_score">Similarity</MenuItem>
                    <MenuItem value="detected_at">Date Detected</MenuItem>
                    <MenuItem value="article1.title">Title</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={2}>
                <Button
                  fullWidth
                  variant="contained"
                  startIcon={<FilterIcon />}
                  onClick={fetchDuplicates}
                >
                  Filter
                </Button>
              </Grid>
            </Grid>
          </Paper>

          {/* Duplicates Table */}
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Articles</TableCell>
                  <TableCell>Similarity</TableCell>
                  <TableCell>Algorithm</TableCell>
                  <TableCell>Sources</TableCell>
                  <TableCell>Detected</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredDuplicates.map((duplicate) => (
                  <TableRow key={duplicate.id}>
                    <TableCell>
                      <Box>
                        <Typography variant="subtitle2" fontWeight="medium">
                          {duplicate.article1.title}
                        </Typography>
                        <Typography variant="caption" color="textSecondary">
                          vs {duplicate.article2.title}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Box display="flex" alignItems="center" gap={1}>
                        <LinearProgress
                          variant="determinate"
                          value={duplicate.similarity_score * 100}
                          color={getSimilarityColor(duplicate.similarity_score)}
                          sx={{ width: 60 }}
                        />
                        <Typography variant="body2">
                          {formatSimilarity(duplicate.similarity_score)}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={duplicate.algorithm}
                        size="small"
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>
                      <Box display="flex" gap={1}>
                        <Chip label={duplicate.article1.source} size="small" />
                        <Chip label={duplicate.article2.source} size="small" />
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {formatDate(duplicate.detected_at)}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={duplicate.status}
                        color={duplicate.status === 'confirmed' ? 'error' : duplicate.status === 'rejected' ? 'success' : 'default'}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>
                      <Box display="flex" gap={1}>
                        <Tooltip title="View Details">
                          <IconButton size="small" onClick={() => setSelectedDuplicate(duplicate)}>
                            <VisibilityIcon />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Mark as Not Duplicate">
                          <IconButton size="small" onClick={() => handleMarkAsNotDuplicate(duplicate.id)}>
                            <CheckCircleIcon />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Remove Duplicate">
                          <IconButton size="small" onClick={() => handleRemoveDuplicates([duplicate.id])} color="error">
                            <DeleteIcon />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          {filteredDuplicates.length === 0 && (
            <Box textAlign="center" py={4}>
              <DeduplicationIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" color="textSecondary">
                No duplicates found
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Run duplicate detection to find similar articles
              </Typography>
            </Box>
          )}
        </Box>
      )}

      {/* Statistics Tab */}
      {activeTab === 1 && stats && (
        <Box>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Card>
                <CardHeader title="Similarity Distribution" />
                <CardContent>
                  <List>
                    <ListItem>
                      <ListItemText
                        primary="Very High (90%+)"
                        secondary={`${stats.very_high_similarity} pairs`}
                      />
                      <LinearProgress
                        variant="determinate"
                        value={(stats.very_high_similarity / stats.total_duplicates) * 100}
                        color="error"
                        sx={{ width: 100 }}
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemText
                        primary="High (80-90%)"
                        secondary={`${stats.high_similarity} pairs`}
                      />
                      <LinearProgress
                        variant="determinate"
                        value={(stats.high_similarity / stats.total_duplicates) * 100}
                        color="warning"
                        sx={{ width: 100 }}
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemText
                        primary="Medium (60-80%)"
                        secondary={`${stats.medium_similarity} pairs`}
                      />
                      <LinearProgress
                        variant="determinate"
                        value={(stats.medium_similarity / stats.total_duplicates) * 100}
                        color="info"
                        sx={{ width: 100 }}
                      />
                    </ListItem>
                  </List>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={6}>
              <Card>
                <CardHeader title="Algorithm Performance" />
                <CardContent>
                  <List>
                    {stats.algorithm_performance?.map((algo, index) => (
                      <ListItem key={index}>
                        <ListItemText
                          primary={algo.name}
                          secondary={`${algo.detections} detections, ${algo.accuracy}% accuracy`}
                        />
                        <LinearProgress
                          variant="determinate"
                          value={algo.accuracy}
                          color={algo.accuracy >= 90 ? 'success' : algo.accuracy >= 70 ? 'warning' : 'error'}
                          sx={{ width: 100 }}
                        />
                      </ListItem>
                    ))}
                  </List>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Box>
      )}

      {/* Settings Tab */}
      {activeTab === 2 && (
        <Box>
          <Card>
            <CardHeader title="Deduplication Settings" />
            <CardContent>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                <Box>
                  <Typography variant="h6" gutterBottom>
                    Similarity Threshold
                  </Typography>
                  <Box display="flex" alignItems="center" gap={2}>
                    <Slider
                      value={settings.similarity_threshold}
                      onChange={(e, value) => setSettings({...settings, similarity_threshold: value})}
                      min={0.5}
                      max={1.0}
                      step={0.05}
                      marks={[
                        { value: 0.5, label: '50%' },
                        { value: 0.7, label: '70%' },
                        { value: 0.85, label: '85%' },
                        { value: 1.0, label: '100%' }
                      ]}
                      sx={{ flexGrow: 1 }}
                    />
                    <Typography variant="h6">
                      {formatSimilarity(settings.similarity_threshold)}
                    </Typography>
                  </Box>
                </Box>

                <Box>
                  <Typography variant="h6" gutterBottom>
                    Processing Limits
                  </Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={6}>
                      <TextField
                        label="Min Article Length"
                        type="number"
                        value={settings.min_article_length}
                        onChange={(e) => setSettings({...settings, min_article_length: parseInt(e.target.value)})}
                        fullWidth
                      />
                    </Grid>
                    <Grid item xs={6}>
                      <TextField
                        label="Max Articles to Process"
                        type="number"
                        value={settings.max_articles_to_process}
                        onChange={(e) => setSettings({...settings, max_articles_to_process: parseInt(e.target.value)})}
                        fullWidth
                      />
                    </Grid>
                  </Grid>
                </Box>

                <Box>
                  <Typography variant="h6" gutterBottom>
                    Enabled Algorithms
                  </Typography>
                  <FormGroup>
                    <FormControlLabelCheckbox
                      control={
                        <Checkbox
                          checked={settings.enabled_algorithms.includes('content_similarity')}
                          onChange={(e) => {
                            const algorithms = e.target.checked
                              ? [...settings.enabled_algorithms, 'content_similarity']
                              : settings.enabled_algorithms.filter(a => a !== 'content_similarity');
                            setSettings({...settings, enabled_algorithms: algorithms});
                          }}
                        />
                      }
                      label="Content Similarity"
                    />
                    <FormControlLabelCheckbox
                      control={
                        <Checkbox
                          checked={settings.enabled_algorithms.includes('title_similarity')}
                          onChange={(e) => {
                            const algorithms = e.target.checked
                              ? [...settings.enabled_algorithms, 'title_similarity']
                              : settings.enabled_algorithms.filter(a => a !== 'title_similarity');
                            setSettings({...settings, enabled_algorithms: algorithms});
                          }}
                        />
                      }
                      label="Title Similarity"
                    />
                    <FormControlLabelCheckbox
                      control={
                        <Checkbox
                          checked={settings.enabled_algorithms.includes('url_similarity')}
                          onChange={(e) => {
                            const algorithms = e.target.checked
                              ? [...settings.enabled_algorithms, 'url_similarity']
                              : settings.enabled_algorithms.filter(a => a !== 'url_similarity');
                            setSettings({...settings, enabled_algorithms: algorithms});
                          }}
                        />
                      }
                      label="URL Similarity"
                    />
                  </FormGroup>
                </Box>

                <Box>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={settings.auto_remove}
                        onChange={(e) => setSettings({...settings, auto_remove: e.target.checked})}
                      />
                    }
                    label="Auto-remove high similarity duplicates"
                  />
                </Box>

                <Box>
                  <Button
                    variant="contained"
                    onClick={handleUpdateSettings}
                    disabled={processing}
                    startIcon={processing ? <CircularProgress size={20} /> : <SettingsIcon />}
                  >
                    {processing ? 'Updating...' : 'Update Settings'}
                  </Button>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Box>
      )}

      {/* History Tab */}
      {activeTab === 3 && (
        <Box>
          <Card>
            <CardHeader title="Deduplication History" />
            <CardContent>
              <List>
                {stats?.recent_actions?.map((action, index) => (
                  <ListItem key={index}>
                    <ListItemIcon>
                      {action.type === 'detection' && <SearchIcon />}
                      {action.type === 'removal' && <DeleteIcon />}
                      {action.type === 'rejection' && <CheckCircleIcon />}
                    </ListItemIcon>
                    <ListItemText
                      primary={action.description}
                      secondary={`${formatDate(action.timestamp)} - ${action.count} items`}
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Box>
      )}

      {/* Duplicate Detail Dialog */}
      <Dialog open={!!selectedDuplicate} onClose={() => setSelectedDuplicate(null)} maxWidth="lg" fullWidth>
        <DialogTitle>Duplicate Analysis</DialogTitle>
        <DialogContent>
          {selectedDuplicate && (
            <Box>
              <Grid container spacing={3}>
                <Grid item xs={12} md={6}>
                  <Card>
                    <CardHeader title="Article 1" />
                    <CardContent>
                      <Typography variant="h6" gutterBottom>
                        {selectedDuplicate.article1.title}
                      </Typography>
                      <Typography variant="body2" paragraph>
                        {selectedDuplicate.article1.content}
                      </Typography>
                      <Box display="flex" gap={1} flexWrap="wrap">
                        <Chip label={selectedDuplicate.article1.source} />
                        <Chip label={formatDate(selectedDuplicate.article1.published_at)} />
                        <Chip label={`${selectedDuplicate.article1.word_count} words`} />
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Card>
                    <CardHeader title="Article 2" />
                    <CardContent>
                      <Typography variant="h6" gutterBottom>
                        {selectedDuplicate.article2.title}
                      </Typography>
                      <Typography variant="body2" paragraph>
                        {selectedDuplicate.article2.content}
                      </Typography>
                      <Box display="flex" gap={1} flexWrap="wrap">
                        <Chip label={selectedDuplicate.article2.source} />
                        <Chip label={formatDate(selectedDuplicate.article2.published_at)} />
                        <Chip label={`${selectedDuplicate.article2.word_count} words`} />
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
              
              <Box mt={3}>
                <Typography variant="h6" gutterBottom>
                  Similarity Analysis
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={4}>
                    <Box textAlign="center">
                      <Typography variant="h4" color="primary">
                        {formatSimilarity(selectedDuplicate.similarity_score)}
                      </Typography>
                      <Typography variant="body2">Overall Similarity</Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={4}>
                    <Box textAlign="center">
                      <Typography variant="h4" color="secondary">
                        {formatSimilarity(selectedDuplicate.title_similarity)}
                      </Typography>
                      <Typography variant="body2">Title Similarity</Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={4}>
                    <Box textAlign="center">
                      <Typography variant="h4" color="info">
                        {formatSimilarity(selectedDuplicate.content_similarity)}
                      </Typography>
                      <Typography variant="body2">Content Similarity</Typography>
                    </Box>
                  </Grid>
                </Grid>
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelectedDuplicate(null)}>Close</Button>
          <Button
            onClick={() => handleMarkAsNotDuplicate(selectedDuplicate?.id)}
            variant="outlined"
            startIcon={<CheckCircleIcon />}
          >
            Mark as Not Duplicate
          </Button>
          <Button
            onClick={() => handleRemoveDuplicates([selectedDuplicate?.id])}
            variant="contained"
            color="error"
            startIcon={<DeleteIcon />}
          >
            Remove Duplicate
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default DeduplicationManagement;
