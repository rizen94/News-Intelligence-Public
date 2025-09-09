import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  Button,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tabs,
  Tab,
  Paper,
  Divider,
  Tooltip,
  Badge,
  LinearProgress,
  Alert,
  Collapse
} from '@mui/material';
import {
  OpenInNew,
  BookmarkBorder,
  Bookmark,
  Share,
  Analytics,
  Timeline,
  Language,
  CalendarToday,
  Source,
  Category,
  TrendingUp,
  Visibility,
  ExpandMore,
  ExpandLess,
  ContentCopy,
  CheckCircle
} from '@mui/icons-material';

interface ArticleViewerProps {
  article: {
    id: number;
    title: string;
    content: string;
    url: string;
    source: string;
    published_at: string;
    processing_status: string;
    summary?: string;
    quality_score?: number;
    category?: string;
    sentiment_score?: number;
    entities_extracted?: string[];
    topics_extracted?: string[];
    key_points?: string[];
    readability_score?: number;
    engagement_score?: number;
    ml_data?: any;
  };
  onClose?: () => void;
  onAnalyze?: (articleId: number) => void;
  onAddToStoryline?: (articleId: number) => void;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`article-tabpanel-${index}`}
      aria-labelledby={`article-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

const ArticleViewer: React.FC<ArticleViewerProps> = ({
  article,
  onClose,
  onAnalyze,
  onAddToStoryline
}) => {
  const [activeTab, setActiveTab] = useState(0);
  const [isBookmarked, setIsBookmarked] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);
  const [showAnalysis, setShowAnalysis] = useState(false);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const handleBookmark = () => {
    setIsBookmarked(!isBookmarked);
    // TODO: Implement bookmark API call
  };

  const handleShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: article.title,
          text: article.summary || article.content.substring(0, 200),
          url: article.url
        });
      } catch (err) {
        console.log('Error sharing:', err);
      }
    } else {
      // Fallback to clipboard
      navigator.clipboard.writeText(article.url);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    }
  };

  const handleAnalyze = () => {
    setShowAnalysis(true);
    onAnalyze?.(article.id);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'success';
      case 'processing': return 'warning';
      case 'pending': return 'info';
      case 'error': return 'error';
      default: return 'default';
    }
  };

  const getSentimentColor = (score?: number) => {
    if (!score) return 'default';
    if (score > 0.1) return 'success';
    if (score < -0.1) return 'error';
    return 'warning';
  };

  const getSentimentLabel = (score?: number) => {
    if (!score) return 'Neutral';
    if (score > 0.3) return 'Very Positive';
    if (score > 0.1) return 'Positive';
    if (score < -0.3) return 'Very Negative';
    if (score < -0.1) return 'Negative';
    return 'Neutral';
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <Dialog
      open={true}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: { height: '90vh' }
      }}
    >
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6" sx={{ flexGrow: 1, mr: 2 }}>
            {article.title}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title={isBookmarked ? 'Remove bookmark' : 'Bookmark'}>
              <IconButton onClick={handleBookmark} size="small">
                {isBookmarked ? <Bookmark color="primary" /> : <BookmarkBorder />}
              </IconButton>
            </Tooltip>
            <Tooltip title="Share">
              <IconButton onClick={handleShare} size="small">
                {copySuccess ? <CheckCircle color="success" /> : <Share />}
              </IconButton>
            </Tooltip>
            <Tooltip title="Open in new tab">
              <IconButton 
                onClick={() => window.open(article.url, '_blank')} 
                size="small"
              >
                <OpenInNew />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>
      </DialogTitle>

      <DialogContent dividers>
        {/* Article Metadata */}
        <Paper sx={{ p: 2, mb: 2, bgcolor: 'grey.50' }}>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
            <Chip
              icon={<Source />}
              label={article.source}
              color="primary"
              variant="outlined"
              size="small"
            />
            <Chip
              icon={<CalendarToday />}
              label={formatDate(article.published_at)}
              color="default"
              variant="outlined"
              size="small"
            />
            {article.category && (
              <Chip
                icon={<Category />}
                label={article.category}
                color="secondary"
                variant="outlined"
                size="small"
              />
            )}
            <Chip
              icon={<Analytics />}
              label={article.processing_status}
              color={getStatusColor(article.processing_status)}
              variant="outlined"
              size="small"
            />
          </Box>

          {/* Quality and Sentiment Scores */}
          <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
            {article.quality_score && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="body2" color="text.secondary">
                  Quality:
                </Typography>
                <Chip
                  label={`${Math.round(article.quality_score * 100)}%`}
                  color={article.quality_score > 0.7 ? 'success' : 'warning'}
                  size="small"
                />
              </Box>
            )}
            {article.sentiment_score !== null && article.sentiment_score !== undefined && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="body2" color="text.secondary">
                  Sentiment:
                </Typography>
                <Chip
                  label={getSentimentLabel(article.sentiment_score)}
                  color={getSentimentColor(article.sentiment_score)}
                  size="small"
                />
              </Box>
            )}
            {article.readability_score && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="body2" color="text.secondary">
                  Readability:
                </Typography>
                <Chip
                  label={`${Math.round(article.readability_score * 100)}%`}
                  color={article.readability_score > 0.7 ? 'success' : 'warning'}
                  size="small"
                />
              </Box>
            )}
          </Box>

          {/* Action Buttons */}
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              variant="contained"
              startIcon={<Analytics />}
              onClick={handleAnalyze}
              size="small"
            >
              Analyze
            </Button>
            <Button
              variant="outlined"
              startIcon={<Timeline />}
              onClick={() => onAddToStoryline?.(article.id)}
              size="small"
            >
              Add to Storyline
            </Button>
            <Button
              variant="outlined"
              startIcon={<Visibility />}
              onClick={() => setIsExpanded(!isExpanded)}
              size="small"
            >
              {isExpanded ? 'Show Less' : 'Show More'}
            </Button>
          </Box>
        </Paper>

        {/* Tabs for different views */}
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={activeTab} onChange={handleTabChange}>
            <Tab label="Content" />
            <Tab label="Analysis" />
            <Tab label="Metadata" />
          </Tabs>
        </Box>

        {/* Content Tab */}
        <TabPanel value={activeTab} index={0}>
          {article.summary && (
            <Alert severity="info" sx={{ mb: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                AI Summary:
              </Typography>
              <Typography variant="body2">
                {article.summary}
              </Typography>
            </Alert>
          )}

          <Typography variant="body1" sx={{ lineHeight: 1.8 }}>
            {article.content}
          </Typography>

          {isExpanded && article.key_points && article.key_points.length > 0 && (
            <Box sx={{ mt: 3 }}>
              <Typography variant="h6" gutterBottom>
                Key Points:
              </Typography>
              <Box component="ul" sx={{ pl: 2 }}>
                {article.key_points.map((point, index) => (
                  <li key={index}>
                    <Typography variant="body2">{point}</Typography>
                  </li>
                ))}
              </Box>
            </Box>
          )}
        </TabPanel>

        {/* Analysis Tab */}
        <TabPanel value={activeTab} index={1}>
          {showAnalysis ? (
            <Box>
              <Typography variant="h6" gutterBottom>
                AI Analysis Results
              </Typography>
              <LinearProgress sx={{ mb: 2 }} />
              <Typography variant="body2" color="text.secondary">
                Analysis in progress... This may take a few moments.
              </Typography>
            </Box>
          ) : (
            <Box>
              <Typography variant="h6" gutterBottom>
                Analysis Data
              </Typography>
              
              {article.entities_extracted && article.entities_extracted.length > 0 && (
                <Box sx={{ mb: 3 }}>
                  <Typography variant="subtitle1" gutterBottom>
                    Extracted Entities:
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {article.entities_extracted.map((entity, index) => (
                      <Chip key={index} label={entity} size="small" />
                    ))}
                  </Box>
                </Box>
              )}

              {article.topics_extracted && article.topics_extracted.length > 0 && (
                <Box sx={{ mb: 3 }}>
                  <Typography variant="subtitle1" gutterBottom>
                    Topics:
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {article.topics_extracted.map((topic, index) => (
                      <Chip key={index} label={topic} color="secondary" size="small" />
                    ))}
                  </Box>
                </Box>
              )}

              {article.ml_data && Object.keys(article.ml_data).length > 0 && (
                <Box sx={{ mb: 3 }}>
                  <Typography variant="subtitle1" gutterBottom>
                    ML Analysis:
                  </Typography>
                  <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                    <pre style={{ fontSize: '0.875rem', margin: 0 }}>
                      {JSON.stringify(article.ml_data, null, 2)}
                    </pre>
                  </Paper>
                </Box>
              )}

              <Button
                variant="contained"
                startIcon={<Analytics />}
                onClick={handleAnalyze}
                fullWidth
              >
                Run New Analysis
              </Button>
            </Box>
          )}
        </TabPanel>

        {/* Metadata Tab */}
        <TabPanel value={activeTab} index={2}>
          <Typography variant="h6" gutterBottom>
            Article Metadata
          </Typography>
          
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
            <Box>
              <Typography variant="subtitle2" color="text.secondary">
                Article ID:
              </Typography>
              <Typography variant="body2">{article.id}</Typography>
            </Box>
            
            <Box>
              <Typography variant="subtitle2" color="text.secondary">
                Processing Status:
              </Typography>
              <Chip
                label={article.processing_status}
                color={getStatusColor(article.processing_status)}
                size="small"
              />
            </Box>
            
            <Box>
              <Typography variant="subtitle2" color="text.secondary">
                Created At:
              </Typography>
              <Typography variant="body2">
                {formatDate(article.published_at)}
              </Typography>
            </Box>
            
            <Box>
              <Typography variant="subtitle2" color="text.secondary">
                Source URL:
              </Typography>
              <Typography 
                variant="body2" 
                sx={{ 
                  wordBreak: 'break-all',
                  color: 'primary.main',
                  cursor: 'pointer'
                }}
                onClick={() => window.open(article.url, '_blank')}
              >
                {article.url}
              </Typography>
            </Box>
          </Box>
        </TabPanel>
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

export default ArticleViewer;
