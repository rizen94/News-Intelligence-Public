import { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Button,
  Alert,
  CircularProgress,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Switch,
  FormControlLabel,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Slider,
  TextField,
} from '@mui/material';
import {
  Refresh,
  Warning,
  CheckCircle,
  Error,
  Merge,
  ExpandMore,
  Info,
  Search,
  AutoFixHigh,
  Security,
  ContentCopy,
  Link,
} from '@mui/icons-material';
import apiService, { api } from '../../services/apiService';

const ArticleDeduplicationManager = () => {
  const [duplicates, setDuplicates] = useState([]);
  const [contentDuplicates, setContentDuplicates] = useState([]);
  const [similarities, setSimilarities] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [mergeDialog, setMergeDialog] = useState({
    open: false,
    duplicates: null,
  });
  const [dryRun, setDryRun] = useState(true);
  const [similarityThreshold, setSimilarityThreshold] = useState(85);

  const loadDeduplicationData = useCallback(async() => {
    setLoading(true);
    setError(null);

    try {
      const [duplicatesRes, contentRes, similaritiesRes, statsRes] =
        await Promise.all([
          api.get('/api/v4/articles/duplicates/url'),
          api.get('/api/v4/articles/duplicates/content'),
          api.get('/api/v4/articles/duplicates/similar'),
          api.get('/api/v4/articles/duplicates/stats'),
        ]);

      if (duplicatesRes.data?.success) {
        setDuplicates(duplicatesRes.data.data?.duplicates || []);
      } else if (duplicatesRes.data) {
        setDuplicates(duplicatesRes.data.duplicates || []);
      }

      if (contentRes.data?.success) {
        setContentDuplicates(contentRes.data.data?.duplicates || []);
      } else if (contentRes.data) {
        setContentDuplicates(contentRes.data.duplicates || []);
      }

      if (similaritiesRes.data?.success) {
        setSimilarities(similaritiesRes.data.data?.similarities || []);
      } else if (similaritiesRes.data) {
        setSimilarities(similaritiesRes.data.similarities || []);
      }

      if (statsRes.data?.success) {
        setStats(statsRes.data.data || {});
      } else if (statsRes.data) {
        setStats(statsRes.data);
      }
    } catch (err) {
      console.error('Error loading deduplication data:', err);
      setError('Failed to load deduplication data. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDeduplicationData();
  }, [loadDeduplicationData]);

  const handleDetectDuplicates = async() => {
    setLoading(true);
    try {
      const response = await api.get(
        '/api/v4/articles/duplicates/detect',
      );
      if (response.data?.success) {
        setDuplicates(response.data.data?.url_duplicates || []);
        setContentDuplicates(response.data.data?.content_duplicates || []);
        setSimilarities(response.data.data?.content_similarities || []);
      } else if (response.data) {
        setDuplicates(response.data.url_duplicates || []);
        setContentDuplicates(response.data.content_duplicates || []);
        setSimilarities(response.data.content_similarities || []);
        setError(null);
      }
    } catch (err) {
      setError('Failed to detect duplicates');
    } finally {
      setLoading(false);
    }
  };

  const handleAutoMerge = async() => {
    setLoading(true);
    try {
      const response = await api.post(
        '/api/v4/articles/duplicates/auto-merge',
        null,
        {
          params: { dry_run: dryRun },
        },
      );

      if (response.data?.success) {
        alert(
          `${dryRun ? 'Dry run: ' : ''}Merged ${
            response.data.data?.total_processed || 0
          } duplicate articles`,
        );
        loadDeduplicationData(); // Refresh data
      }
    } catch (err) {
      setError('Failed to merge duplicates');
    } finally {
      setLoading(false);
    }
  };

  const handleAddPrevention = async() => {
    setLoading(true);
    try {
      const response = await api.post(
        '/api/v4/articles/duplicates/prevent',
      );

      if (response.data?.success) {
        alert('Deduplication prevention constraints added successfully');
        loadDeduplicationData(); // Refresh data
      }
    } catch (err) {
      setError('Failed to add deduplication prevention');
    } finally {
      setLoading(false);
    }
  };

  const openMergeDialog = duplicateGroup => {
    setMergeDialog({ open: true, duplicates: duplicateGroup });
  };

  const closeMergeDialog = () => {
    setMergeDialog({ open: false, duplicates: null });
  };

  const getSeverityColor = count => {
    if (count >= 5) return 'error';
    if (count >= 3) return 'warning';
    return 'info';
  };

  const getDuplicateTypeIcon = type => {
    switch (type) {
    case 'exact_url':
      return <Link color='error' />;
    case 'content_hash':
      return <ContentCopy color='warning' />;
    case 'content_similarity':
      return <Info color='info' />;
    default:
      return <Info />;
    }
  };

  if (
    loading &&
    !duplicates.length &&
    !contentDuplicates.length &&
    !similarities.length
  ) {
    return (
      <Box
        display='flex'
        justifyContent='center'
        alignItems='center'
        minHeight='400px'
      >
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box
        display='flex'
        justifyContent='space-between'
        alignItems='center'
        mb={3}
      >
        <Typography variant='h4' component='h1' sx={{ fontWeight: 'bold' }}>
          Article Deduplication Manager
        </Typography>
        <Box>
          <Button
            startIcon={<Refresh />}
            onClick={loadDeduplicationData}
            variant='outlined'
            sx={{ mr: 1 }}
          >
            Refresh
          </Button>
          <Button
            startIcon={<Search />}
            onClick={handleDetectDuplicates}
            variant='contained'
            color='primary'
          >
            Detect Duplicates
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity='error' sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Statistics */}
      {stats && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant='h6' gutterBottom>
              Deduplication Statistics
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6} md={3}>
                <Box textAlign='center'>
                  <Typography variant='h4' color='primary'>
                    {stats.total_articles.toLocaleString()}
                  </Typography>
                  <Typography variant='body2' color='text.secondary'>
                    Total Articles
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Box textAlign='center'>
                  <Typography variant='h4' color='success.main'>
                    {stats.hash_coverage_percentage.toFixed(1)}%
                  </Typography>
                  <Typography variant='body2' color='text.secondary'>
                    Hash Coverage
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Box textAlign='center'>
                  <Typography variant='h4' color='error.main'>
                    {stats.url_duplicate_groups}
                  </Typography>
                  <Typography variant='body2' color='text.secondary'>
                    URL Duplicates
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Box textAlign='center'>
                  <Typography variant='h4' color='warning.main'>
                    {stats.content_duplicate_groups}
                  </Typography>
                  <Typography variant='body2' color='text.secondary'>
                    Content Duplicates
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* Action Buttons */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant='h6' gutterBottom>
            Deduplication Management Actions
          </Typography>
          <Box display='flex' gap={2} flexWrap='wrap' alignItems='center'>
            <FormControlLabel
              control={
                <Switch
                  checked={dryRun}
                  onChange={e => setDryRun(e.target.checked)}
                />
              }
              label='Dry Run Mode'
            />
            <Button
              startIcon={<AutoFixHigh />}
              onClick={handleAutoMerge}
              variant='contained'
              color='warning'
              disabled={loading}
            >
              Auto-Merge URL Duplicates
            </Button>
            <Button
              startIcon={<Security />}
              onClick={handleAddPrevention}
              variant='contained'
              color='success'
              disabled={loading}
            >
              Add Prevention Constraints
            </Button>
          </Box>
          <Box sx={{ mt: 2 }}>
            <Typography variant='subtitle2' gutterBottom>
              Content Similarity Threshold: {similarityThreshold}%
            </Typography>
            <Slider
              value={similarityThreshold}
              onChange={(e, value) => setSimilarityThreshold(value)}
              min={70}
              max={95}
              step={5}
              marks={[
                { value: 70, label: '70%' },
                { value: 80, label: '80%' },
                { value: 85, label: '85%' },
                { value: 90, label: '90%' },
                { value: 95, label: '95%' },
              ]}
              sx={{ maxWidth: 300 }}
            />
          </Box>
        </CardContent>
      </Card>

      {/* URL Duplicates */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant='h6' gutterBottom>
            <Link color='error' sx={{ mr: 1 }} />
            URL Duplicates ({duplicates.length})
          </Typography>

          {duplicates.length === 0 ? (
            <Alert severity='success'>
              <CheckCircle sx={{ mr: 1 }} />
              No URL duplicates found!
            </Alert>
          ) : (
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>URL</TableCell>
                    <TableCell>Count</TableCell>
                    <TableCell>Titles</TableCell>
                    <TableCell>Domains</TableCell>
                    <TableCell>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {duplicates.map((duplicate, index) => (
                    <TableRow key={index}>
                      <TableCell>
                        <Typography
                          variant='body2'
                          sx={{ wordBreak: 'break-all', maxWidth: 200 }}
                        >
                          {duplicate.url}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={duplicate.count}
                          color={getSeverityColor(duplicate.count)}
                          size='small'
                        />
                      </TableCell>
                      <TableCell>
                        <Box>
                          {duplicate.titles
                            .slice(0, 2)
                            .map((title, titleIndex) => (
                              <Chip
                                key={titleIndex}
                                label={
                                  title.length > 30
                                    ? title.substring(0, 30) + '...'
                                    : title
                                }
                                size='small'
                                sx={{ mr: 0.5, mb: 0.5 }}
                              />
                            ))}
                          {duplicate.titles.length > 2 && (
                            <Chip
                              label={`+${duplicate.titles.length - 2} more`}
                              size='small'
                              color='default'
                            />
                          )}
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Box>
                          {duplicate.domains
                            .slice(0, 3)
                            .map((domain, domainIndex) => (
                              <Chip
                                key={domainIndex}
                                label={domain}
                                size='small'
                                sx={{ mr: 0.5, mb: 0.5 }}
                              />
                            ))}
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Button
                          startIcon={<Merge />}
                          onClick={() => openMergeDialog(duplicate)}
                          size='small'
                          color='warning'
                        >
                          Merge
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

      {/* Content Duplicates */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant='h6' gutterBottom>
            <ContentCopy color='warning' sx={{ mr: 1 }} />
            Content Duplicates ({contentDuplicates.length})
          </Typography>

          {contentDuplicates.length === 0 ? (
            <Alert severity='info'>
              <Info sx={{ mr: 1 }} />
              No content duplicates found!
            </Alert>
          ) : (
            <Box>
              {contentDuplicates.slice(0, 10).map((duplicate, index) => (
                <Accordion key={index}>
                  <AccordionSummary expandIcon={<ExpandMore />}>
                    <Box display='flex' alignItems='center' width='100%'>
                      <Typography variant='subtitle1' sx={{ mr: 2 }}>
                        Content Hash: {duplicate.content_hash.substring(0, 16)}
                        ...
                      </Typography>
                      <Chip
                        label={`${duplicate.count} articles`}
                        color='warning'
                        size='small'
                      />
                    </Box>
                  </AccordionSummary>
                  <AccordionDetails>
                    <List>
                      {duplicate.articles.map((article, articleIndex) => (
                        <ListItem key={articleIndex}>
                          <ListItemText
                            primary={article.title}
                            secondary={`${article.domain} - ${new Date(
                              article.created_at,
                            ).toLocaleDateString()}`}
                          />
                          <ListItemSecondaryAction>
                            <Button
                              size='small'
                              onClick={() => window.open(article.url, '_blank')}
                            >
                              View
                            </Button>
                          </ListItemSecondaryAction>
                        </ListItem>
                      ))}
                    </List>
                  </AccordionDetails>
                </Accordion>
              ))}
              {contentDuplicates.length > 10 && (
                <Typography
                  variant='body2'
                  color='text.secondary'
                  sx={{ mt: 2 }}
                >
                  Showing first 10 of {contentDuplicates.length} content
                  duplicate groups
                </Typography>
              )}
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Content Similarities */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant='h6' gutterBottom>
            <Info color='info' sx={{ mr: 1 }} />
            Content Similarities ({similarities.length})
          </Typography>

          {similarities.length === 0 ? (
            <Alert severity='info'>
              <Info sx={{ mr: 1 }} />
              No content similarities found!
            </Alert>
          ) : (
            <Box>
              {similarities.slice(0, 5).map((similarity, index) => (
                <Accordion key={index}>
                  <AccordionSummary expandIcon={<ExpandMore />}>
                    <Box display='flex' alignItems='center' width='100%'>
                      <Typography variant='subtitle1' sx={{ mr: 2 }}>
                        {similarity.primary_article.title.substring(0, 50)}...
                      </Typography>
                      <Chip
                        label={`${similarity.count} similar`}
                        color='info'
                        size='small'
                      />
                    </Box>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Typography variant='subtitle2' gutterBottom>
                      Primary Article:
                    </Typography>
                    <Typography variant='body2' sx={{ mb: 2 }}>
                      {similarity.primary_article.title}
                    </Typography>
                    <Typography variant='subtitle2' gutterBottom>
                      Similar Articles:
                    </Typography>
                    <List>
                      {similarity.similar_articles.map(
                        (article, articleIndex) => (
                          <ListItem key={articleIndex}>
                            <ListItemText
                              primary={article.title}
                              secondary={`${article.domain} - ${(
                                article.similarity * 100
                              ).toFixed(1)}% similar`}
                            />
                            <ListItemSecondaryAction>
                              <Chip
                                label={`${(article.similarity * 100).toFixed(
                                  1,
                                )}%`}
                                size='small'
                                color={
                                  article.similarity > 0.9 ? 'error' : 'warning'
                                }
                              />
                            </ListItemSecondaryAction>
                          </ListItem>
                        ),
                      )}
                    </List>
                  </AccordionDetails>
                </Accordion>
              ))}
              {similarities.length > 5 && (
                <Typography
                  variant='body2'
                  color='text.secondary'
                  sx={{ mt: 2 }}
                >
                  Showing first 5 of {similarities.length} content similarity
                  groups
                </Typography>
              )}
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Merge Dialog */}
      <Dialog
        open={mergeDialog.open}
        onClose={closeMergeDialog}
        maxWidth='md'
        fullWidth
      >
        <DialogTitle>Merge Duplicate Articles</DialogTitle>
        <DialogContent>
          {mergeDialog.duplicates && (
            <Box>
              <Typography variant='body1' gutterBottom>
                URL: {mergeDialog.duplicates.url}
              </Typography>
              <Typography variant='body2' color='text.secondary' gutterBottom>
                Found {mergeDialog.duplicates.count} duplicate articles. Choose
                which one to keep:
              </Typography>

              <List>
                {mergeDialog.duplicates.titles.map((title, index) => (
                  <ListItem key={index}>
                    <ListItemText
                      primary={title}
                      secondary={`ID: ${mergeDialog.duplicates.article_ids[index]}`}
                    />
                    <ListItemSecondaryAction>
                      <Chip
                        label={mergeDialog.duplicates.domains[index]}
                        size='small'
                        color='default'
                      />
                    </ListItemSecondaryAction>
                  </ListItem>
                ))}
              </List>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={closeMergeDialog}>Cancel</Button>
          <Button
            onClick={() => {
              // Implement merge logic here
              closeMergeDialog();
            }}
            color='warning'
          >
            Merge Selected
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ArticleDeduplicationManager;
