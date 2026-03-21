import React, { useEffect, useState } from 'react';
import { useNavigate, useParams, Link as RouterLink } from 'react-router-dom';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Breadcrumbs,
  Button,
  Chip,
  CircularProgress,
  Container,
  Grid,
  IconButton,
  Link,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Paper,
  Tab,
  Tabs,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import {
  Article as ArticleIcon,
  ArrowBack as BackIcon,
  Assessment as QualityIcon,
  AutoStories as SynthesisIcon,
  ContentCopy as CopyIcon,
  Download as DownloadIcon,
  ExpandMore as ExpandMoreIcon,
  MenuBook as GlossaryIcon,
  Refresh as RefreshIcon,
  Source as SourceIcon,
  Timeline as TimelineIcon,
} from '@mui/icons-material';
import ReactMarkdown from 'react-markdown';

import { sanitizeSnippet } from '../../utils/sanitizeSnippet';

type SynthesisResponse = Record<string, any> | null;
type QualityResponse = Record<string, any> | null;

function TabPanel({
  children,
  value,
  index,
}: {
  children: React.ReactNode;
  value: number;
  index: number;
}) {
  return (
    <div hidden={value !== index}>
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
}

const SynthesizedView: React.FC = () => {
  const { domain, id } = useParams<{ domain: string; id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [synthesis, setSynthesis] = useState<SynthesisResponse>(null);
  const [quality, setQuality] = useState<QualityResponse>(null);
  const [depth, setDepth] = useState('comprehensive');
  const [tabValue, setTabValue] = useState(0);

  useEffect(() => {
    if (!id || !domain) return;
    void loadSynthesis();
    void loadQuality();
  }, [domain, id, depth]);

  const parseSectionsFromContent = (
    content: string
  ): Array<{ title: string; content: string }> => {
    if (!content) return [];
    return content
      .split(/^## /m)
      .slice(1)
      .map(part => {
        const lines = part.split('\n');
        return {
          title: lines[0]?.trim() || 'Section',
          content: lines.slice(1).join('\n').trim(),
        };
      });
  };

  const loadSynthesis = async (forceRegenerate = false) => {
    setLoading(true);
    setError(null);
    try {
      if (!forceRegenerate) {
        const cachedResponse = await fetch(
          `/api/${domain}/synthesis/storyline/${id}/cached`
        );
        if (cachedResponse.ok) {
          const cachedData = await cachedResponse.json();
          if (cachedData.has_synthesis && cachedData.content) {
            setSynthesis({
              title: cachedData.title,
              summary: cachedData.content?.split('\n\n')[0] || '',
              word_count: cachedData.word_count,
              quality_score: cachedData.quality_score,
              synthesized_at: cachedData.synthesized_at,
              cached: true,
              sections: parseSectionsFromContent(cachedData.content),
              markdown: cachedData.markdown,
              total_sources: 0,
            });
            setLoading(false);
            return;
          }
        }
      }
      const response = await fetch(`/api/${domain}/synthesis/storyline/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          depth,
          include_terms: true,
          include_timeline: true,
          format: 'json',
        }),
      });
      if (!response.ok) throw new Error(`Synthesis failed: ${response.status}`);
      setSynthesis(await response.json());
    } catch (err: any) {
      setError(err?.message || 'Failed to load synthesis');
    } finally {
      setLoading(false);
    }
  };

  const loadQuality = async () => {
    try {
      const response = await fetch(`/api/${domain}/synthesis/quality/${id}`);
      if (response.ok) setQuality(await response.json());
    } catch {
      // Non-blocking.
    }
  };

  const downloadMarkdown = async () => {
    const response = await fetch(
      `/api/${domain}/synthesis/storyline/${id}/markdown?depth=${depth}`
    );
    if (!response.ok) return;
    const data = await response.json();
    const blob = new Blob([data.markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${synthesis?.title || 'synthesis'}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <Container maxWidth='lg' sx={{ py: 4 }}>
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 2,
          }}
        >
          <CircularProgress size={60} />
          <Typography variant='h6'>Synthesizing Content...</Typography>
        </Box>
      </Container>
    );
  }
  if (error) {
    return (
      <Container maxWidth='lg' sx={{ py: 4 }}>
        <Alert severity='error' sx={{ mb: 2 }}>
          {error}
        </Alert>
        <Button startIcon={<BackIcon />} onClick={() => navigate(-1)}>
          Go Back
        </Button>
      </Container>
    );
  }

  return (
    <Container maxWidth='xl' sx={{ py: 4 }}>
      <Breadcrumbs sx={{ mb: 2 }}>
        <Link
          component={RouterLink}
          to={`/${domain}/dashboard`}
          underline='hover'
          color='inherit'
        >
          {(domain || '').toUpperCase()}
        </Link>
        <Link
          component={RouterLink}
          to={`/${domain}/storylines`}
          underline='hover'
          color='inherit'
        >
          Storylines
        </Link>
        <Typography color='text.primary'>Synthesized View</Typography>
      </Breadcrumbs>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            flexWrap: 'wrap',
            gap: 2,
          }}
        >
          <Box>
            <Typography
              variant='h4'
              component='h1'
              sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
            >
              <SynthesisIcon sx={{ fontSize: 36 }} />
              {synthesis?.title || 'Synthesized Article'}
            </Typography>
            <Box
              sx={{
                mt: 1,
                display: 'flex',
                gap: 1,
                flexWrap: 'wrap',
                alignItems: 'center',
              }}
            >
              <Chip
                label={`${synthesis?.word_count || 0} words`}
                size='small'
              />
              <Chip
                label={`${
                  synthesis?.total_sources ||
                  synthesis?.source_articles?.length ||
                  0
                } sources`}
                size='small'
                color='primary'
              />
              <Chip
                label={`Quality: ${(
                  (synthesis?.quality_score || 0) * 100
                ).toFixed(0)}%`}
                size='small'
                color={synthesis?.quality_score > 0.7 ? 'success' : 'warning'}
              />
              {synthesis?.synthesized_at && (
                <Typography variant='caption' color='text.secondary'>
                  Generated:{' '}
                  {new Date(synthesis.synthesized_at).toLocaleString()}
                </Typography>
              )}
            </Box>
          </Box>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <ToggleButtonGroup
              value={depth}
              exclusive
              onChange={(_, val) => val && setDepth(val)}
              size='small'
            >
              <ToggleButton value='brief'>Brief</ToggleButton>
              <ToggleButton value='standard'>Standard</ToggleButton>
              <ToggleButton value='comprehensive'>Comprehensive</ToggleButton>
            </ToggleButtonGroup>
            <IconButton onClick={() => loadSynthesis(true)} title='Regenerate'>
              <RefreshIcon />
            </IconButton>
            <IconButton onClick={downloadMarkdown} title='Download Markdown'>
              <DownloadIcon />
            </IconButton>
            <IconButton
              onClick={() =>
                navigator.clipboard.writeText(synthesis?.summary || '')
              }
              title='Copy Summary'
            >
              <CopyIcon />
            </IconButton>
          </Box>
        </Box>
      </Paper>

      <Grid container spacing={3}>
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3, mb: 3 }}>
            <Typography
              variant='h6'
              gutterBottom
              sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
            >
              <ArticleIcon color='primary' /> Summary
            </Typography>
            <Typography variant='body1' sx={{ lineHeight: 1.8 }}>
              {sanitizeSnippet(synthesis?.summary, '')}
            </Typography>
          </Paper>
          <Paper sx={{ p: 3, mb: 3 }}>
            <Tabs
              value={tabValue}
              onChange={(_, v) => setTabValue(v)}
              sx={{ mb: 2 }}
            >
              <Tab label='Formatted' />
              <Tab label='Markdown' />
              <Tab label='Raw' />
            </Tabs>
            <TabPanel value={tabValue} index={0}>
              {(synthesis?.sections || []).map((section: any, idx: number) => (
                <Box key={idx} sx={{ mb: 4 }}>
                  <Typography
                    variant='h5'
                    gutterBottom
                    sx={{ borderBottom: 2, borderColor: 'divider', pb: 1 }}
                  >
                    {section.title}
                  </Typography>
                  <Typography
                    variant='body1'
                    sx={{ lineHeight: 1.8, whiteSpace: 'pre-wrap' }}
                  >
                    {sanitizeSnippet(section.content, '')}
                  </Typography>
                </Box>
              ))}
            </TabPanel>
            <TabPanel value={tabValue} index={1}>
              <ReactMarkdown>{synthesis?.markdown || ''}</ReactMarkdown>
            </TabPanel>
            <TabPanel value={tabValue} index={2}>
              <Typography
                variant='caption'
                sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}
              >
                {JSON.stringify(synthesis, null, 2)}
              </Typography>
            </TabPanel>
          </Paper>
        </Grid>

        <Grid item xs={12} md={4}>
          {quality && (
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography
                variant='subtitle1'
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}
              >
                <QualityIcon fontSize='small' />
                Quality Assessment
              </Typography>
              <Chip
                label={`Score: ${((quality.overall_score || 0) * 100).toFixed(
                  0
                )}%`}
                size='small'
              />
            </Paper>
          )}
          {!!synthesis?.key_terms_explained && (
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography
                variant='subtitle1'
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}
              >
                <GlossaryIcon fontSize='small' />
                Key Terms
              </Typography>
              {Object.entries(synthesis.key_terms_explained).map(
                ([term, definition], idx) => (
                  <Accordion
                    key={idx}
                    disableGutters
                    sx={{ boxShadow: 'none', '&:before': { display: 'none' } }}
                  >
                    <AccordionSummary
                      expandIcon={<ExpandMoreIcon />}
                      sx={{ px: 0 }}
                    >
                      <Typography variant='body2' fontWeight='medium'>
                        {term}
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails sx={{ px: 0 }}>
                      <Typography variant='caption'>
                        {String(definition)}
                      </Typography>
                    </AccordionDetails>
                  </Accordion>
                )
              )}
            </Paper>
          )}
          {!!synthesis?.timeline?.length && (
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography
                variant='subtitle1'
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}
              >
                <TimelineIcon fontSize='small' />
                Timeline
              </Typography>
              <List dense>
                {synthesis.timeline.map((event: any, idx: number) => (
                  <ListItem key={idx} sx={{ alignItems: 'flex-start', px: 0 }}>
                    <ListItemIcon sx={{ minWidth: 80 }}>
                      <Typography
                        variant='caption'
                        color='primary'
                        fontWeight='bold'
                      >
                        {event.date || '—'}
                      </Typography>
                    </ListItemIcon>
                    <ListItemText
                      primary={event.event}
                      secondary={event.source}
                    />
                  </ListItem>
                ))}
              </List>
            </Paper>
          )}
          {!!synthesis?.source_articles?.length && (
            <Paper sx={{ p: 2 }}>
              <Typography
                variant='subtitle1'
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}
              >
                <SourceIcon fontSize='small' />
                Sources ({synthesis.source_articles.length})
              </Typography>
              <List dense>
                {synthesis.source_articles.map((article: any, idx: number) => (
                  <ListItem key={idx} sx={{ px: 0 }}>
                    <ListItemText
                      primary={
                        <Link
                          href={article.url}
                          target='_blank'
                          rel='noopener'
                          underline='hover'
                        >
                          {sanitizeSnippet(
                            article.title,
                            `Article #${idx + 1}`
                          )}
                        </Link>
                      }
                      secondary={article.source_name}
                    />
                  </ListItem>
                ))}
              </List>
            </Paper>
          )}
        </Grid>
      </Grid>

      <Box sx={{ mt: 3 }}>
        <Button startIcon={<BackIcon />} onClick={() => navigate(-1)}>
          Back to Storyline
        </Button>
      </Box>
    </Container>
  );
};

export default SynthesizedView;
