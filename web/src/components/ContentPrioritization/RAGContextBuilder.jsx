import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  CircularProgress,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  Article as ArticleIcon,
  Timeline as TimelineIcon,
  History as HistoryIcon,
  Link as LinkIcon,
  Build as BuildIcon
} from '@mui/icons-material';

const RAGContextBuilder = ({ thread, onClose }) => {
  const [contextType, setContextType] = useState('historical');
  const [maxArticles, setMaxArticles] = useState(10);
  const [context, setContext] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const contextTypes = [
    { value: 'historical', label: 'Historical Context', icon: <HistoryIcon /> },
    { value: 'related', label: 'Related Content', icon: <LinkIcon /> },
    { value: 'background', label: 'Background Info', icon: <ArticleIcon /> },
    { value: 'timeline', label: 'Timeline', icon: <TimelineIcon /> }
  ];

  const buildContext = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(`/api/prioritization/rag-context/${thread.id}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          context_type: contextType,
          max_articles: maxArticles
        }),
      });
      
      const data = await response.json();
      
      if (data.success) {
        setContext(data.data);
      } else {
        setError(data.error);
      }
    } catch (err) {
      setError('Failed to build RAG context');
    } finally {
      setLoading(false);
    }
  };

  const getContextIcon = (type) => {
    const contextType = contextTypes.find(ct => ct.value === type);
    return contextType ? contextType.icon : <BuildIcon />;
  };

  const getContextLabel = (type) => {
    const contextType = contextTypes.find(ct => ct.value === type);
    return contextType ? contextType.label : type;
  };

  const renderContextSummary = () => {
    if (!context) return null;

    return (
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Context Summary
          </Typography>
          <Typography variant="body1">
            {context.context_summary}
          </Typography>
          
          <Box sx={{ mt: 2 }}>
            <Chip
              label={`${context.articles_found} articles found`}
              color="primary"
              sx={{ mr: 1 }}
            />
            {context.context_type === 'historical' && context.historical_period && (
              <Chip
                label={`Period: ${context.historical_period}`}
                variant="outlined"
                sx={{ mr: 1 }}
              />
            )}
            {context.context_type === 'timeline' && context.timeline_period && (
              <Chip
                label={`Timeline: ${context.timeline_period}`}
                variant="outlined"
                sx={{ mr: 1 }}
              />
            )}
          </Box>
        </CardContent>
      </Card>
    );
  };

  const renderKeyElements = () => {
    if (!context) return null;

    const elements = [];
    
    if (context.key_events && context.key_events.length > 0) {
      elements.push({
        title: 'Key Events',
        items: context.key_events,
        icon: <TimelineIcon />
      });
    }
    
    if (context.key_concepts && context.key_concepts.length > 0) {
      elements.push({
        title: 'Key Concepts',
        items: context.key_concepts,
        icon: <ArticleIcon />
      });
    }
    
    if (context.key_milestones && context.key_milestones.length > 0) {
      elements.push({
        title: 'Key Milestones',
        items: context.key_milestones,
        icon: <TimelineIcon />
      });
    }
    
    if (context.key_entities && context.key_entities.length > 0) {
      elements.push({
        title: 'Key Entities',
        items: context.key_entities,
        icon: <LinkIcon />
      });
    }

    if (elements.length === 0) return null;

    return (
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {elements.map((element, index) => (
          <Grid item xs={12} md={6} key={index}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  {element.icon}
                  <Typography variant="h6" sx={{ ml: 1 }}>
                    {element.title}
                  </Typography>
                </Box>
                <List dense>
                  {element.items.slice(0, 5).map((item, idx) => (
                    <ListItem key={idx} sx={{ px: 0 }}>
                      <ListItemText
                        primary={item}
                        primaryTypographyProps={{ variant: 'body2' }}
                      />
                    </ListItem>
                  ))}
                  {element.items.length > 5 && (
                    <ListItem sx={{ px: 0 }}>
                      <ListItemText
                        primary={`... and ${element.items.length - 5} more`}
                        primaryTypographyProps={{ variant: 'caption', color: 'text.secondary' }}
                      />
                    </ListItem>
                  )}
                </List>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    );
  };

  const renderTimeline = () => {
    if (!context || !context.timeline || context.timeline.length === 0) return null;

    return (
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Timeline
          </Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Date</TableCell>
                  <TableCell>Title</TableCell>
                  <TableCell>Source</TableCell>
                  <TableCell>Summary</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {context.timeline.map((item, index) => (
                  <TableRow key={index}>
                    <TableCell>
                      {new Date(item.date).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" fontWeight="medium">
                        {item.title}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip label={item.source} size="small" variant="outlined" />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {item.summary}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>
    );
  };

  const renderArticles = () => {
    if (!context || !context.articles || context.articles.length === 0) return null;

    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Context Articles
          </Typography>
          <List>
            {context.articles.map((article, index) => (
              <React.Fragment key={index}>
                <ListItem alignItems="flex-start">
                  <ListItemIcon>
                    <ArticleIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Typography variant="subtitle1" fontWeight="medium">
                        {article.title}
                      </Typography>
                    }
                    secondary={
                      <Box>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                          {article.content}
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                          <Chip label={article.source} size="small" variant="outlined" />
                          <Chip label={article.category} size="small" variant="outlined" />
                          {article.published_date && (
                            <Chip 
                              label={new Date(article.published_date).toLocaleDateString()} 
                              size="small" 
                              variant="outlined" 
                            />
                          )}
                        </Box>
                      </Box>
                    }
                  />
                </ListItem>
                {index < context.articles.length - 1 && <Divider />}
              </React.Fragment>
            ))}
          </List>
        </CardContent>
      </Card>
    );
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" gutterBottom>
          RAG Context Builder
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Build contextual information for: <strong>{thread.title}</strong>
        </Typography>
      </Box>

      {/* Controls */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} sm={4}>
              <FormControl fullWidth>
                <InputLabel>Context Type</InputLabel>
                <Select
                  value={contextType}
                  label="Context Type"
                  onChange={(e) => setContextType(e.target.value)}
                >
                  {contextTypes.map((type) => (
                    <MenuItem key={type.value} value={type.value}>
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        {type.icon}
                        <Typography sx={{ ml: 1 }}>{type.label}</Typography>
                      </Box>
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12} sm={4}>
              <FormControl fullWidth>
                <InputLabel>Max Articles</InputLabel>
                <Select
                  value={maxArticles}
                  label="Max Articles"
                  onChange={(e) => setMaxArticles(e.target.value)}
                >
                  <MenuItem value={5}>5 articles</MenuItem>
                  <MenuItem value={10}>10 articles</MenuItem>
                  <MenuItem value={20}>20 articles</MenuItem>
                  <MenuItem value={50}>50 articles</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12} sm={4}>
              <Button
                variant="contained"
                startIcon={<BuildIcon />}
                onClick={buildContext}
                disabled={loading}
                fullWidth
              >
                {loading ? <CircularProgress size={20} /> : 'Build Context'}
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Context Results */}
      {context && (
        <Box>
          {renderContextSummary()}
          {renderKeyElements()}
          {renderTimeline()}
          {renderArticles()}
        </Box>
      )}

      {/* No Context Message */}
      {!context && !loading && (
        <Card>
          <CardContent>
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <BuildIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" color="text.secondary" gutterBottom>
                No Context Built Yet
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Select a context type and click "Build Context" to generate contextual information for this story thread.
              </Typography>
            </Box>
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default RAGContextBuilder;
