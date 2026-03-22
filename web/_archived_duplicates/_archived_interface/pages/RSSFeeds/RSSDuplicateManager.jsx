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
} from '@mui/icons-material';
import apiService, { api } from '../../services/apiService';

const RSSDuplicateManager = () => {
  const [duplicates, setDuplicates] = useState([]);
  const [similarFeeds, setSimilarFeeds] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [mergeDialog, setMergeDialog] = useState({
    open: false,
    duplicates: null,
  });
  const [dryRun, setDryRun] = useState(true);

  const loadDuplicateData = useCallback(async() => {
    setLoading(true);
    setError(null);
    try {
      const [duplicatesRes, similarRes, statsRes] = await Promise.all([
        api.get('/api/rss_feeds/duplicates/exact'),
        api.get('/api/rss_feeds/duplicates/similar'),
        api.get('/api/rss_feeds/duplicates/stats'),
      ]);

      if (duplicatesRes.data?.success) {
        setDuplicates(duplicatesRes.data.data?.duplicates || []);
      } else if (duplicatesRes.data) {
        setDuplicates(duplicatesRes.data.duplicates || []);
      }

      if (similarRes.data?.success) {
        setSimilarFeeds(similarRes.data.data?.similar_feeds || []);
      } else if (similarRes.data) {
        setSimilarFeeds(similarRes.data.similar_feeds || []);
      }

      if (statsRes.data?.success) {
        setStats(statsRes.data.data || {});
      } else if (statsRes.data) {
        setStats(statsRes.data);
      }
    } catch (err) {
      console.error('Error loading duplicate data:', err);
      setError('Failed to load duplicate data. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDuplicateData();
  }, [loadDuplicateData]);

  const handleDetectDuplicates = async() => {
    setLoading(true);
    try {
      const response = await api.get(
        '/api/rss_feeds/duplicates/detect',
      );
      if (response.data?.success) {
        setDuplicates(response.data.data?.exact_duplicates || []);
        setSimilarFeeds(response.data.data?.similar_domains || []);
        setError(null);
      } else if (response.data) {
        setDuplicates(response.data.exact_duplicates || []);
        setSimilarFeeds(response.data.similar_domains || []);
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
        '/api/rss_feeds/duplicates/auto_merge',
        null,
        {
          params: { dry_run: dryRun },
        },
      );

      if (response.data?.success) {
        alert(
          `${dryRun ? 'Dry run: ' : ''}Merged ${
            response.data.data?.total_processed || 0
          } duplicate feeds`,
        );
        loadDuplicateData(); // Refresh data
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
        '/api/rss_feeds/duplicates/prevent',
      );

      if (response.data?.success) {
        alert('Duplicate prevention constraints added successfully');
      }
    } catch (err) {
      setError('Failed to add duplicate prevention');
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

  if (loading && !duplicates.length && !similarFeeds.length) {
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
          RSS Feed Duplicate Manager
        </Typography>
        <Box>
          <Button
            startIcon={<Refresh />}
            onClick={loadDuplicateData}
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
              Duplicate Statistics
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6} md={3}>
                <Box textAlign='center'>
                  <Typography variant='h4' color='primary'>
                    {stats.total_feeds}
                  </Typography>
                  <Typography variant='body2' color='text.secondary'>
                    Total Feeds
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Box textAlign='center'>
                  <Typography variant='h4' color='success.main'>
                    {stats.active_feeds}
                  </Typography>
                  <Typography variant='body2' color='text.secondary'>
                    Active Feeds
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Box textAlign='center'>
                  <Typography variant='h4' color='error.main'>
                    {stats.duplicate_groups}
                  </Typography>
                  <Typography variant='body2' color='text.secondary'>
                    Duplicate Groups
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Box textAlign='center'>
                  <Typography variant='h4' color='info.main'>
                    {stats.active_percentage.toFixed(1)}%
                  </Typography>
                  <Typography variant='body2' color='text.secondary'>
                    Active Rate
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
            Duplicate Management Actions
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
              Auto-Merge All Duplicates
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
        </CardContent>
      </Card>

      {/* Exact Duplicates */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant='h6' gutterBottom>
            <Error color='error' sx={{ mr: 1 }} />
            Exact URL Duplicates ({duplicates.length})
          </Typography>

          {duplicates.length === 0 ? (
            <Alert severity='success'>
              <CheckCircle sx={{ mr: 1 }} />
              No exact URL duplicates found!
            </Alert>
          ) : (
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>URL</TableCell>
                    <TableCell>Count</TableCell>
                    <TableCell>Feed Names</TableCell>
                    <TableCell>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {duplicates.map((duplicate, index) => (
                    <TableRow key={index}>
                      <TableCell>
                        <Typography
                          variant='body2'
                          sx={{ wordBreak: 'break-all' }}
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
                          {duplicate.names.map((name, nameIndex) => (
                            <Chip
                              key={nameIndex}
                              label={name}
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

      {/* Similar Feeds */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant='h6' gutterBottom>
            <Warning color='warning' sx={{ mr: 1 }} />
            Similar Domain Feeds ({similarFeeds.length})
          </Typography>

          {similarFeeds.length === 0 ? (
            <Alert severity='info'>
              <Info sx={{ mr: 1 }} />
              No similar domain feeds found!
            </Alert>
          ) : (
            <Box>
              {similarFeeds.slice(0, 10).map((group, index) => (
                <Accordion key={index}>
                  <AccordionSummary expandIcon={<ExpandMore />}>
                    <Box display='flex' alignItems='center' width='100%'>
                      <Typography variant='subtitle1' sx={{ mr: 2 }}>
                        {group.domain}
                      </Typography>
                      <Chip
                        label={`${group.count} feeds`}
                        color='warning'
                        size='small'
                      />
                    </Box>
                  </AccordionSummary>
                  <AccordionDetails>
                    <List>
                      {group.feeds.map((feed, feedIndex) => (
                        <ListItem key={feedIndex}>
                          <ListItemText
                            primary={feed.name}
                            secondary={feed.url}
                          />
                          <ListItemSecondaryAction>
                            <Chip
                              label={feed.is_active ? 'Active' : 'Inactive'}
                              color={feed.is_active ? 'success' : 'default'}
                              size='small'
                            />
                          </ListItemSecondaryAction>
                        </ListItem>
                      ))}
                    </List>
                  </AccordionDetails>
                </Accordion>
              ))}
              {similarFeeds.length > 10 && (
                <Typography
                  variant='body2'
                  color='text.secondary'
                  sx={{ mt: 2 }}
                >
                  Showing first 10 of {similarFeeds.length} similar domain
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
        <DialogTitle>Merge Duplicate Feeds</DialogTitle>
        <DialogContent>
          {mergeDialog.duplicates && (
            <Box>
              <Typography variant='body1' gutterBottom>
                URL: {mergeDialog.duplicates.url}
              </Typography>
              <Typography variant='body2' color='text.secondary' gutterBottom>
                Found {mergeDialog.duplicates.count} duplicate feeds. Choose
                which one to keep:
              </Typography>

              <List>
                {mergeDialog.duplicates.names.map((name, index) => (
                  <ListItem key={index}>
                    <ListItemText
                      primary={name}
                      secondary={`ID: ${mergeDialog.duplicates.ids[index]}`}
                    />
                    <ListItemSecondaryAction>
                      <Chip
                        label={
                          mergeDialog.duplicates.active_status[index]
                            ? 'Active'
                            : 'Inactive'
                        }
                        color={
                          mergeDialog.duplicates.active_status[index]
                            ? 'success'
                            : 'default'
                        }
                        size='small'
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

export default RSSDuplicateManager;
