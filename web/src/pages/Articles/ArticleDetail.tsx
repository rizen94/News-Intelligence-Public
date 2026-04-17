import React, { useEffect, useState } from 'react';
import { useParams, Link as RouterLink } from 'react-router-dom';
import {
  ArrowBack as ArrowBackIcon,
  Share as ShareIcon,
  Bookmark,
  Event as EventIcon,
} from '@mui/icons-material';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Link,
  List,
  ListItem,
  ListItemText,
  Paper,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';

import ArticleTopics from '../../components/ArticleTopics/ArticleTopics';
import ProvenancePanel, {
  articleProvenanceRows,
} from '../../components/ProvenancePanel/ProvenancePanel';
import { useDomainNavigation } from '../../hooks/useDomainNavigation';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import apiService from '../../services/apiService';
import { sanitizeSnippet } from '../../utils/sanitizeSnippet';

type ArticleRecord = Record<string, any>;
type ArticleEvent = Record<string, any>;
type DepthMode = 'narrative' | 'structured' | 'raw';

const ArticleDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { navigateToDomain } = useDomainNavigation();
  const { domain } = useDomainRoute();
  const [article, setArticle] = useState<ArticleRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [extractedEvents, setExtractedEvents] = useState<ArticleEvent[]>([]);
  const [depthMode, setDepthMode] = useState<DepthMode>('narrative');

  useEffect(() => {
    if (!id) return;
    const loadArticle = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await apiService.getArticle(id, domain);
        if (response?.success) {
          setArticle(response.data);
          try {
            const evts = await apiService.getArticleEvents(id, domain);
            if (evts?.success) setExtractedEvents(evts.data || []);
          } catch {
            // Optional side panel data; do not block page render.
          }
        } else {
          setError('Failed to load article');
        }
      } catch {
        setError('Failed to load article');
      } finally {
        setLoading(false);
      }
    };
    loadArticle();
  }, [id, domain]);

  const formatDate = (dateString?: string | null): string => {
    if (!dateString) return 'No date';
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return 'Invalid date';
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }
  if (error) {
    return (
      <Alert severity='error' sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }
  if (!article) {
    return (
      <Alert severity='warning' sx={{ mb: 2 }}>
        Article not found
      </Alert>
    );
  }

  const articleId = Number.parseInt(id || '0', 10);

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigateToDomain('/articles')}
        >
          Back to Articles
        </Button>
        <Button startIcon={<ShareIcon />} variant='outlined'>
          Share
        </Button>
        <Button startIcon={<Bookmark />} variant='outlined'>
          Bookmark
        </Button>
      </Box>

      <ProvenancePanel
        title='Provenance & pipeline'
        subtitle='Source and processing metadata for audits'
        rows={articleProvenanceRows(article, domain, id)}
      />

      <Paper sx={{ p: 3 }}>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 2,
          }}
        >
          <Typography variant='h4' component='h1'>
            {article.title || 'Untitled Article'}
          </Typography>
          <ToggleButtonGroup
            value={depthMode}
            exclusive
            onChange={(_, value: DepthMode | null) =>
              value && setDepthMode(value)
            }
            size='small'
          >
            <ToggleButton value='narrative'>Narrative</ToggleButton>
            <ToggleButton value='structured'>Structured</ToggleButton>
            <ToggleButton value='raw'>Raw</ToggleButton>
          </ToggleButtonGroup>
        </Box>

        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            mb: 2,
            flexWrap: 'wrap',
          }}
        >
          <Typography variant='body2' color='text.secondary'>
            {article.source || article.source_domain || 'Unknown source'}
          </Typography>
          <Typography variant='body2' color='text.secondary'>
            •
          </Typography>
          <Typography variant='body2' color='text.secondary'>
            {formatDate(article.published_date || article.published_at)}
          </Typography>
          {article.category && <Chip label={article.category} size='small' />}
        </Box>

        {depthMode === 'narrative' && (
          <>
            {(article.summary || article.excerpt) && (
              <Typography
                variant='h6'
                color='text.secondary'
                sx={{ mb: 3, fontStyle: 'italic' }}
              >
                {sanitizeSnippet(article.summary || article.excerpt)}
              </Typography>
            )}
            <Divider sx={{ mb: 3 }} />
            <Typography
              variant='body1'
              sx={{ lineHeight: 1.8, whiteSpace: 'pre-wrap' }}
            >
              {sanitizeSnippet(
                article.content || article.excerpt || article.summary,
                'No content available for this article.'
              )}
            </Typography>
          </>
        )}

        {depthMode === 'structured' && (
          <Box sx={{ display: 'grid', gap: 1 }}>
            <Typography variant='body2'>
              <strong>Article ID:</strong> {article.id ?? id}
            </Typography>
            <Typography variant='body2'>
              <strong>Domain:</strong>{' '}
              {domain || article.domain_key || 'unknown'}
            </Typography>
            <Typography variant='body2'>
              <strong>Quality score:</strong> {article.quality_score ?? 'n/a'}
            </Typography>
            <Typography variant='body2'>
              <strong>ML status:</strong>{' '}
              {article.ml_processing_status || 'unknown'}
            </Typography>
            <Typography variant='body2'>
              <strong>Extracted events:</strong> {extractedEvents.length}
            </Typography>
          </Box>
        )}

        {depthMode === 'raw' && (
          <Paper variant='outlined' sx={{ p: 2, bgcolor: 'grey.50' }}>
            <Typography
              variant='caption'
              sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}
            >
              {JSON.stringify(article, null, 2)}
            </Typography>
          </Paper>
        )}

        {article.url && (
          <Box sx={{ mt: 3, pt: 3, borderTop: 1, borderColor: 'divider' }}>
            <Typography variant='body2' color='text.secondary' sx={{ mb: 1 }}>
              Original source
            </Typography>
            <Button
              variant='outlined'
              href={article.url}
              target='_blank'
              rel='noopener noreferrer'
            >
              View Original Article
            </Button>
          </Box>
        )}
      </Paper>

      {extractedEvents.length > 0 && (
        <Card sx={{ mt: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <EventIcon color='primary' />
              <Typography variant='h6'>
                Extracted Events ({extractedEvents.length})
              </Typography>
            </Box>
            <List dense>
              {extractedEvents.map((evt, i) => (
                <ListItem
                  key={i}
                  divider
                  sx={{ cursor: evt.storyline_id ? 'pointer' : 'default' }}
                >
                  <ListItemText
                    primary={evt.title}
                    secondary={
                      <>
                        {evt.event_date || 'date unknown'} {' · '}
                        {(evt.event_type || '').replace(/_/g, ' ')}
                        {evt.date_precision &&
                          evt.date_precision !== 'unknown' &&
                          ` · ~${evt.date_precision}`}
                        {evt.location &&
                          evt.location !== 'unknown' &&
                          ` · ${evt.location}`}
                        {evt.extraction_method &&
                          ` · via ${evt.extraction_method}`}
                        {evt.dedup_role && ` · ${evt.dedup_role}`}
                        {evt.source_article_id && (
                          <>
                            {' · '}
                            <Link
                              component={RouterLink}
                              to={`/${domain}/articles/${evt.source_article_id}`}
                              underline='hover'
                            >
                              source article #{evt.source_article_id}
                            </Link>
                          </>
                        )}
                      </>
                    }
                  />
                  <Box sx={{ display: 'flex', gap: 0.5 }}>
                    {evt.source_count > 1 && (
                      <Chip
                        label={`${evt.source_count} sources`}
                        size='small'
                        color='info'
                        variant='outlined'
                      />
                    )}
                    {evt.is_ongoing && (
                      <Chip
                        label='ongoing'
                        size='small'
                        color='warning'
                        variant='outlined'
                      />
                    )}
                    {evt.storyline_id && (
                      <Chip
                        label={`Story #${evt.storyline_id}`}
                        size='small'
                        variant='outlined'
                      />
                    )}
                  </Box>
                </ListItem>
              ))}
            </List>
          </CardContent>
        </Card>
      )}

      <Box sx={{ mt: 3 }}>
        <ArticleTopics articleId={articleId} domain={domain} />
      </Box>
    </Box>
  );
};

export default ArticleDetail;
