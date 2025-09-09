import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  CardHeader,
  Paper,
  Chip,
  Button,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Avatar,
  Stack,
  LinearProgress,
  Alert,
  CircularProgress,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Tabs,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Accordion,
  AccordionSummary,
  AccordionDetails
} from '@mui/material';
import {
  Insights as InsightsIcon,
  TrendingUp as TrendingUpIcon,
  Psychology as PsychologyIcon,
  Security as SecurityIcon,
  Business as BusinessIcon,
  Public as PublicIcon,
  Computer as TechnologyIcon,
  Assessment as AssessmentIcon,
  Visibility as VisibilityIcon,
  Share as ShareIcon,
  Download as DownloadIcon,
  FilterList as FilterIcon,
  Search as SearchIcon,
  ExpandMore as ExpandMoreIcon,
  Star as StarIcon,
  Flag as FlagIcon,
  Schedule as ScheduleIcon,
  Person as PersonIcon,
  LocationOn as LocationIcon,
  AutoAwesome as AutoAwesomeIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon
} from '@mui/icons-material';
import newsSystemService from '../../services/newsSystemService';
import { useNotifications } from '../../components/Notifications/NotificationSystem';

const IntelligenceInsights = () => {
  const { showSuccess, showError, showLoading, showInfo } = useNotifications();
  const [insights, setInsights] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedInsight, setSelectedInsight] = useState(null);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [filterConfidence, setFilterConfidence] = useState('');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [activeTab, setActiveTab] = useState(0);
  const [buttonLoading, setButtonLoading] = useState({});

  useEffect(() => {
    fetchInsights();
  }, [filterCategory, filterConfidence, sortBy, sortOrder]);

  const fetchInsights = async (isManualRefresh = false) => {
    try {
      setLoading(true);
      setError(null);

      if (isManualRefresh) {
        showInfo('Loading intelligence insights...', 'Insights Refresh');
      }

      const response = await newsSystemService.getIntelligenceInsights(filterCategory, 100);
      setInsights(response.insights || []);

      if (isManualRefresh) {
        showSuccess(`Loaded ${response.insights?.length || 0} insights`, 'Insights Updated');
      }
    } catch (err) {
      console.error('Error fetching insights:', err);
      setError(err.message);
      
      if (isManualRefresh) {
        showError(`Failed to load insights: ${err.message}`, 'Load Error');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleViewInsight = (insight) => {
    setButtonLoading(prev => ({ ...prev, [`view-${insight.id}`]: true }));
    try {
      setSelectedInsight(insight);
      setDetailDialogOpen(true);
    } finally {
      setButtonLoading(prev => ({ ...prev, [`view-${insight.id}`]: false }));
    }
  };

  const handleFilter = async () => {
    setButtonLoading(prev => ({ ...prev, filter: true }));
    try {
      await fetchInsights(true);
    } finally {
      setButtonLoading(prev => ({ ...prev, filter: false }));
    }
  };

  const handleCloseDialog = () => {
    setDetailDialogOpen(false);
    setSelectedInsight(null);
  };

  const getInsightIcon = (category) => {
    switch (category?.toLowerCase()) {
      case 'security': return <SecurityIcon />;
      case 'business': return <BusinessIcon />;
      case 'politics': return <PublicIcon />;
      case 'technology': return <TechnologyIcon />;
      case 'trending': return <TrendingUpIcon />;
      default: return <InsightsIcon />;
    }
  };

  const getInsightColor = (confidence) => {
    if (confidence >= 0.8) return 'success';
    if (confidence >= 0.6) return 'warning';
    return 'error';
  };

  const getConfidenceLabel = (confidence) => {
    if (confidence >= 0.8) return 'High';
    if (confidence >= 0.6) return 'Medium';
    return 'Low';
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  const formatConfidence = (confidence) => {
    return `${(confidence * 100).toFixed(1)}%`;
  };

  const filteredInsights = insights.filter(insight => {
    const matchesSearch = !searchQuery || 
      insight.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      insight.description.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = !filterCategory || insight.category === filterCategory;
    const matchesConfidence = !filterConfidence || 
      (filterConfidence === 'high' && insight.confidence >= 0.8) ||
      (filterConfidence === 'medium' && insight.confidence >= 0.6 && insight.confidence < 0.8) ||
      (filterConfidence === 'low' && insight.confidence < 0.6);
    
    return matchesSearch && matchesCategory && matchesConfidence;
  }).sort((a, b) => {
    const aValue = a[sortBy];
    const bValue = b[sortBy];
    
    if (sortOrder === 'asc') {
      return aValue > bValue ? 1 : -1;
    } else {
      return aValue < bValue ? 1 : -1;
    }
  });

  const getCategoryStats = () => {
    const stats = {};
    insights.forEach(insight => {
      stats[insight.category] = (stats[insight.category] || 0) + 1;
    });
    return stats;
  };

  const categoryStats = getCategoryStats();

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
        <Typography variant="h6" ml={2}>
          Loading insights...
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error">
        Error loading insights: {error}
      </Alert>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            Intelligence Insights
          </Typography>
          <Typography variant="subtitle1" color="textSecondary">
            AI-generated insights from news analysis and pattern detection
          </Typography>
        </Box>
        <Box display="flex" gap={2}>
          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            size="small"
          >
            Export
          </Button>
          <Button
            variant="contained"
            startIcon={<ShareIcon />}
            size="small"
          >
            Share
          </Button>
        </Box>
      </Box>

      {/* Stats Overview */}
      <Grid container spacing={3} mb={3}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" justifyContent="space-between">
                <Box>
                  <Typography color="textSecondary" gutterBottom>
                    Total Insights
                  </Typography>
                  <Typography variant="h4">
                    {insights.length}
                  </Typography>
                </Box>
                <InsightsIcon sx={{ fontSize: 40, color: 'primary.main' }} />
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
                    High Confidence
                  </Typography>
                  <Typography variant="h4" color="success.main">
                    {insights.filter(i => i.confidence >= 0.8).length}
                  </Typography>
                </Box>
                <CheckCircleIcon sx={{ fontSize: 40, color: 'success.main' }} />
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
                    Categories
                  </Typography>
                  <Typography variant="h4" color="info.main">
                    {Object.keys(categoryStats).length}
                  </Typography>
                </Box>
                <AssessmentIcon sx={{ fontSize: 40, color: 'info.main' }} />
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
                    Avg Confidence
                  </Typography>
                  <Typography variant="h4" color="warning.main">
                    {insights.length > 0 ? formatConfidence(insights.reduce((sum, i) => sum + i.confidence, 0) / insights.length) : '0%'}
                  </Typography>
                </Box>
                <AutoAwesomeIcon sx={{ fontSize: 40, color: 'warning.main' }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              label="Search insights"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              InputProps={{
                startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />
              }}
            />
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Category</InputLabel>
              <Select
                value={filterCategory}
                label="Category"
                onChange={(e) => setFilterCategory(e.target.value)}
              >
                <MenuItem value="">All</MenuItem>
                {Object.keys(categoryStats).map(category => (
                  <MenuItem key={category} value={category}>
                    {category}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Confidence</InputLabel>
              <Select
                value={filterConfidence}
                label="Confidence"
                onChange={(e) => setFilterConfidence(e.target.value)}
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
                <MenuItem value="created_at">Date</MenuItem>
                <MenuItem value="confidence">Confidence</MenuItem>
                <MenuItem value="title">Title</MenuItem>
                <MenuItem value="category">Category</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Order</InputLabel>
              <Select
                value={sortOrder}
                label="Order"
                onChange={(e) => setSortOrder(e.target.value)}
              >
                <MenuItem value="desc">Descending</MenuItem>
                <MenuItem value="asc">Ascending</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={1}>
            <Button
              fullWidth
              variant="contained"
              startIcon={buttonLoading.filter ? <CircularProgress size={16} /> : <FilterIcon />}
              onClick={handleFilter}
              disabled={loading || buttonLoading.filter}
            >
              {buttonLoading.filter ? 'Filtering...' : 'Filter'}
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {/* Insights Grid */}
      <Grid container spacing={3}>
        {filteredInsights.map((insight, index) => (
          <Grid item xs={12} md={6} lg={4} key={index}>
            <Card sx={{ height: '100%', cursor: 'pointer' }} onClick={() => handleViewInsight(insight)}>
              <CardHeader
                avatar={
                  <Avatar sx={{ bgcolor: getInsightColor(insight.confidence) + '.main' }}>
                    {getInsightIcon(insight.category)}
                  </Avatar>
                }
                title={
                  <Box display="flex" alignItems="center" gap={1}>
                    <Typography variant="h6" noWrap>
                      {insight.title}
                    </Typography>
                    <Chip
                      label={getConfidenceLabel(insight.confidence)}
                      color={getInsightColor(insight.confidence)}
                      size="small"
                    />
                  </Box>
                }
                subheader={
                  <Box display="flex" alignItems="center" gap={1}>
                    <Chip label={insight.category} size="small" variant="outlined" />
                    <Typography variant="caption" color="textSecondary">
                      {formatDate(insight.created_at)}
                    </Typography>
                  </Box>
                }
                action={
                  <Tooltip title="View Details">
                    <IconButton 
                      size="small"
                      disabled={buttonLoading[`view-${insight.id}`]}
                    >
                      {buttonLoading[`view-${insight.id}`] ? 
                        <CircularProgress size={16} /> : 
                        <VisibilityIcon />
                      }
                    </IconButton>
                  </Tooltip>
                }
              />
              <CardContent>
                <Typography variant="body2" color="textSecondary" paragraph>
                  {insight.description}
                </Typography>
                
                <Box display="flex" alignItems="center" gap={1} mb={2}>
                  <Typography variant="caption" color="textSecondary">
                    Confidence:
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={insight.confidence * 100}
                    color={getInsightColor(insight.confidence)}
                    sx={{ flexGrow: 1 }}
                  />
                  <Typography variant="caption" color="textSecondary">
                    {formatConfidence(insight.confidence)}
                  </Typography>
                </Box>

                {insight.data && Object.keys(insight.data).length > 0 && (
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>
                      Key Data:
                    </Typography>
                    <Stack direction="row" spacing={1} flexWrap="wrap">
                      {Object.entries(insight.data).slice(0, 3).map(([key, value]) => (
                        <Chip
                          key={key}
                          label={`${key}: ${value}`}
                          size="small"
                          variant="outlined"
                        />
                      ))}
                      {Object.keys(insight.data).length > 3 && (
                        <Chip
                          label={`+${Object.keys(insight.data).length - 3} more`}
                          size="small"
                          variant="outlined"
                        />
                      )}
                    </Stack>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {filteredInsights.length === 0 && (
        <Box textAlign="center" py={4}>
          <InsightsIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" color="textSecondary">
            No insights found
          </Typography>
          <Typography variant="body2" color="textSecondary">
            Try adjusting your filters or search criteria
          </Typography>
        </Box>
      )}

      {/* Insight Detail Dialog */}
      <Dialog
        open={detailDialogOpen}
        onClose={handleCloseDialog}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          <Box display="flex" alignItems="center" gap={2}>
            <Avatar sx={{ bgcolor: getInsightColor(selectedInsight?.confidence) + '.main' }}>
              {selectedInsight && getInsightIcon(selectedInsight.category)}
            </Avatar>
            <Box>
              <Typography variant="h6">
                {selectedInsight?.title}
              </Typography>
              <Box display="flex" alignItems="center" gap={1}>
                <Chip label={selectedInsight?.category} size="small" variant="outlined" />
                <Chip
                  label={selectedInsight ? getConfidenceLabel(selectedInsight.confidence) : ''}
                  color={selectedInsight ? getInsightColor(selectedInsight.confidence) : 'default'}
                  size="small"
                />
              </Box>
            </Box>
          </Box>
        </DialogTitle>
        <DialogContent>
          {selectedInsight && (
            <Box>
              <Typography variant="body1" paragraph>
                {selectedInsight.description}
              </Typography>

              <Box mb={3}>
                <Typography variant="h6" gutterBottom>
                  Confidence Analysis
                </Typography>
                <Box display="flex" alignItems="center" gap={2}>
                  <LinearProgress
                    variant="determinate"
                    value={selectedInsight.confidence * 100}
                    color={getInsightColor(selectedInsight.confidence)}
                    sx={{ flexGrow: 1 }}
                  />
                  <Typography variant="h6">
                    {formatConfidence(selectedInsight.confidence)}
                  </Typography>
                </Box>
              </Box>

              {selectedInsight.data && Object.keys(selectedInsight.data).length > 0 && (
                <Box mb={3}>
                  <Typography variant="h6" gutterBottom>
                    Supporting Data
                  </Typography>
                  <TableContainer component={Paper} variant="outlined">
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Metric</TableCell>
                          <TableCell>Value</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {Object.entries(selectedInsight.data).map(([key, value]) => (
                          <TableRow key={key}>
                            <TableCell>{key}</TableCell>
                            <TableCell>{value}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Box>
              )}

              <Box display="flex" gap={2} flexWrap="wrap">
                <Chip
                  icon={<ScheduleIcon />}
                  label={`Created: ${formatDate(selectedInsight.created_at)}`}
                  variant="outlined"
                />
                <Chip
                  icon={<AssessmentIcon />}
                  label={`Category: ${selectedInsight.category}`}
                  variant="outlined"
                />
                <Chip
                  icon={<AutoAwesomeIcon />}
                  label={`AI Generated`}
                  variant="outlined"
                />
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Close</Button>
          <Button variant="contained" startIcon={<ShareIcon />}>
            Share
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default IntelligenceInsights;
