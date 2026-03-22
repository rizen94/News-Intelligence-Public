import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Typography,
  Paper,
  Grid,
  Card,
  CardContent,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  CircularProgress,
  Alert,
  Button,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ToggleButtonGroup,
  ToggleButton,
  Tooltip,
  IconButton,
  Tabs,
  Tab,
  Link,
  Breadcrumbs,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  Article as ArticleIcon,
  Timeline as TimelineIcon,
  MenuBook as GlossaryIcon,
  Source as SourceIcon,
  ContentCopy as CopyIcon,
  Download as DownloadIcon,
  ArrowBack as BackIcon,
  AutoStories as SynthesisIcon,
  Assessment as QualityIcon,
  Refresh as RefreshIcon,
  Share as ShareIcon,
} from '@mui/icons-material';
import ReactMarkdown from 'react-markdown';

function TabPanel({ children, value, index, ...other }) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`synthesis-tabpanel-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
}

function SynthesizedView() {
  const { domain, id } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [synthesis, setSynthesis] = useState(null);
  const [quality, setQuality] = useState(null);
  const [depth, setDepth] = useState('comprehensive');
  const [tabValue, setTabValue] = useState(0);
  const [viewMode, setViewMode] = useState('formatted'); // formatted or markdown

  useEffect(() => {
    if (id) {
      loadSynthesis();
      loadQuality();
    }
  }, [domain, id, depth]);

  async function loadSynthesis(forceRegenerate = false) {
    setLoading(true);
    setError(null);

    try {
      // First try to load cached synthesis (unless forcing regenerate)
      if (!forceRegenerate) {
        const cachedResponse = await fetch(`/api/${domain}/synthesis/storyline/${id}/cached`);
        if (cachedResponse.ok) {
          const cachedData = await cachedResponse.json();
          if (cachedData.has_synthesis && cachedData.content) {
            // Parse cached content back into sections format
            setSynthesis({
              title: cachedData.title,
              summary: cachedData.content?.split('\n\n')[0] || '',
              word_count: cachedData.word_count,
              quality_score: cachedData.quality_score,
              synthesized_at: cachedData.synthesized_at,
              cached: true,
              // Parse markdown sections
              sections: parseSectionsFromContent(cachedData.content),
              markdown: cachedData.markdown,
              total_sources: 0,
            });
            setLoading(false);
            return;
          }
        }
      }

      // Generate fresh synthesis
      const response = await fetch(`/api/${domain}/synthesis/storyline/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          depth: depth,
          include_terms: true,
          include_timeline: true,
          format: 'json',
        }),
      });

      if (!response.ok) {
        throw new Error(`Synthesis failed: ${response.status}`);
      }

      const data = await response.json();
      setSynthesis(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  // Helper to parse sections from cached content
  function parseSectionsFromContent(content) {
    if (!content) return [];
    const sections = [];
    const parts = content.split(/^## /m);
    for (let i = 1; i < parts.length; i++) {
      const lines = parts[i].split('\n');
      const title = lines[0]?.trim() || 'Section';
      const sectionContent = lines.slice(1).join('\n').trim();
      sections.push({ title, content: sectionContent });
    }
    return sections;
  }

  async function loadQuality() {
    try {
      const response = await fetch(`/api/${domain}/synthesis/quality/${id}`);
      if (response.ok) {
        const data = await response.json();
        setQuality(data);
      }
    } catch (err) {
      console.error('Quality check failed:', err);
    }
  }

  async function downloadMarkdown() {
    try {
      const response = await fetch(`/api/${domain}/synthesis/storyline/${id}/markdown?depth=${depth}`);
      if (response.ok) {
        const data = await response.json();
        const blob = new Blob([data.markdown], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${synthesis?.title || 'synthesis'}.md`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (err) {
      console.error('Download failed:', err);
    }
  }

  function copyToClipboard(text) {
    navigator.clipboard.writeText(text);
  }

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
          <CircularProgress size={60} />
          <Typography variant="h6">Synthesizing Content...</Typography>
          <Typography color="text.secondary">
            Analyzing articles, extracting facts, and generating comprehensive content
          </Typography>
        </Box>
      </Container>
    );
  }

  if (error) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
        <Button startIcon={<BackIcon />} onClick={() => navigate(-1)}>
          Go Back
        </Button>
      </Container>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Breadcrumbs */}
      <Breadcrumbs sx={{ mb: 2 }}>
        <Link href={`/${domain}/dashboard`} underline="hover" color="inherit">
          {domain.toUpperCase()}
        </Link>
        <Link href={`/${domain}/storylines`} underline="hover" color="inherit">
          Storylines
        </Link>
        <Typography color="text.primary">Synthesized View</Typography>
      </Breadcrumbs>

      {/* Header */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2 }}>
          <Box>
            <Typography variant="h4" component="h1" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <SynthesisIcon sx={{ fontSize: 36 }} />
              {synthesis?.title || 'Synthesized Article'}
            </Typography>
            <Box sx={{ mt: 1, display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
              <Chip label={`${synthesis?.word_count || 0} words`} size="small" />
              <Chip label={`${synthesis?.total_sources || synthesis?.source_articles?.length || 0} sources`} size="small" color="primary" />
              <Chip
                label={`Quality: ${((synthesis?.quality_score || 0) * 100).toFixed(0)}%`}
                size="small"
                color={synthesis?.quality_score > 0.7 ? 'success' : 'warning'}
              />
              {synthesis?.cached && (
                <Chip label="Cached" size="small" color="info" variant="outlined" />
              )}
              {synthesis?.synthesized_at && (
                <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                  Generated: {new Date(synthesis.synthesized_at).toLocaleString()}
                </Typography>
              )}
            </Box>
          </Box>

          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <ToggleButtonGroup
              value={depth}
              exclusive
              onChange={(e, val) => val && setDepth(val)}
              size="small"
            >
              <ToggleButton value="brief">Brief</ToggleButton>
              <ToggleButton value="standard">Standard</ToggleButton>
              <ToggleButton value="comprehensive">Comprehensive</ToggleButton>
            </ToggleButtonGroup>

            <IconButton onClick={() => loadSynthesis(true)} title="Regenerate">
              <RefreshIcon />
            </IconButton>
            <IconButton onClick={downloadMarkdown} title="Download Markdown">
              <DownloadIcon />
            </IconButton>
            <IconButton onClick={() => copyToClipboard(synthesis?.summary || '')} title="Copy Summary">
              <CopyIcon />
            </IconButton>
          </Box>
        </Box>
      </Paper>

      <Grid container spacing={3}>
        {/* Main Content */}
        <Grid item xs={12} md={8}>
          {/* Summary */}
          <Paper sx={{ p: 3, mb: 3 }}>
            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <ArticleIcon color="primary" />
              Summary
            </Typography>
            <Typography variant="body1" sx={{ lineHeight: 1.8, textAlign: 'justify' }}>
              {synthesis?.summary}
            </Typography>
          </Paper>

          {/* Sections */}
          <Paper sx={{ p: 3, mb: 3 }}>
            <Tabs value={tabValue} onChange={(e, v) => setTabValue(v)} sx={{ mb: 2 }}>
              <Tab label="Formatted" />
              <Tab label="Markdown" />
            </Tabs>

            <TabPanel value={tabValue} index={0}>
              {synthesis?.sections?.map((section, idx) => (
                <Box key={idx} sx={{ mb: 4 }}>
                  <Typography variant="h5" gutterBottom sx={{ borderBottom: 2, borderColor: 'divider', pb: 1 }}>
                    {section.title}
                  </Typography>
                  <Typography variant="body1" sx={{ lineHeight: 1.8, textAlign: 'justify', whiteSpace: 'pre-wrap' }}>
                    {section.content}
                  </Typography>

                  {/* Subsections */}
                  {section.subsections?.map((sub, subIdx) => (
                    <Box key={subIdx} sx={{ ml: 2, mt: 2 }}>
                      <Typography variant="h6" gutterBottom color="primary">
                        {sub.title}
                      </Typography>
                      <Typography variant="body2" sx={{ lineHeight: 1.7 }}>
                        {sub.content}
                      </Typography>
                    </Box>
                  ))}

                  {/* Section Sources */}
                  {section.sources?.length > 0 && (
                    <Box sx={{ mt: 2, p: 1, bgcolor: 'grey.50', borderRadius: 1 }}>
                      <Typography variant="caption" color="text.secondary">
                        Sources: {section.sources.map((s, i) => (
                          <Link key={i} href={s.url} target="_blank" rel="noopener" sx={{ mr: 1 }}>
                            {s.title}
                          </Link>
                        ))}
                      </Typography>
                    </Box>
                  )}
                </Box>
              ))}
            </TabPanel>

            <TabPanel value={tabValue} index={1}>
              <Box sx={{ fontFamily: 'monospace', fontSize: '0.9rem', bgcolor: 'grey.50', p: 2, borderRadius: 1, overflow: 'auto' }}>
                <ReactMarkdown>
                  {synthesis?.markdown || `# ${synthesis?.title}\n\n${synthesis?.summary}\n\n${synthesis?.sections?.map(s => `## ${s.title}\n\n${s.content}`).join('\n\n')}`}
                </ReactMarkdown>
              </Box>
            </TabPanel>
          </Paper>
        </Grid>

        {/* Sidebar */}
        <Grid item xs={12} md={4}>
          {/* Quality Score */}
          {quality && (
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle1" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <QualityIcon fontSize="small" />
                Quality Assessment
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1 }}>
                <Chip
                  label={`Score: ${(quality.overall_score * 100).toFixed(0)}%`}
                  color={quality.overall_score > 0.7 ? 'success' : quality.overall_score > 0.4 ? 'warning' : 'error'}
                  size="small"
                />
                <Chip label={`${quality.quality_factors?.article_count || 0} articles`} size="small" variant="outlined" />
                <Chip label={`${quality.quality_factors?.source_diversity || 0} sources`} size="small" variant="outlined" />
              </Box>
              {quality.recommendations?.length > 0 && (
                <Box sx={{ mt: 1 }}>
                  <Typography variant="caption" color="text.secondary">Recommendations:</Typography>
                  <List dense>
                    {quality.recommendations.map((rec, i) => (
                      <ListItem key={i} sx={{ py: 0 }}>
                        <ListItemText primaryTypographyProps={{ variant: 'caption' }} primary={`• ${rec}`} />
                      </ListItem>
                    ))}
                  </List>
                </Box>
              )}
            </Paper>
          )}

          {/* Key Entities */}
          {synthesis?.key_entities?.length > 0 && (
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle1" gutterBottom>Key Entities</Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {synthesis.key_entities.map((entity, idx) => (
                  <Chip key={idx} label={entity} size="small" variant="outlined" />
                ))}
              </Box>
            </Paper>
          )}

          {/* Glossary */}
          {synthesis?.key_terms_explained && Object.keys(synthesis.key_terms_explained).length > 0 && (
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle1" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <GlossaryIcon fontSize="small" />
                Key Terms
              </Typography>
              {Object.entries(synthesis.key_terms_explained).map(([term, definition], idx) => (
                <Accordion key={idx} disableGutters sx={{ boxShadow: 'none', '&:before': { display: 'none' } }}>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ px: 0 }}>
                    <Typography variant="body2" fontWeight="medium">{term}</Typography>
                  </AccordionSummary>
                  <AccordionDetails sx={{ px: 0 }}>
                    <Typography variant="caption">{definition}</Typography>
                  </AccordionDetails>
                </Accordion>
              ))}
            </Paper>
          )}

          {/* Timeline */}
          {synthesis?.timeline?.length > 0 && (
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle1" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <TimelineIcon fontSize="small" />
                Timeline
              </Typography>
              <List dense>
                {synthesis.timeline.map((event, idx) => (
                  <ListItem key={idx} sx={{ alignItems: 'flex-start', px: 0 }}>
                    <ListItemIcon sx={{ minWidth: 80 }}>
                      <Typography variant="caption" color="primary" fontWeight="bold">
                        {event.date || '—'}
                      </Typography>
                    </ListItemIcon>
                    <ListItemText
                      primary={event.event}
                      secondary={event.source}
                      primaryTypographyProps={{ variant: 'body2' }}
                      secondaryTypographyProps={{ variant: 'caption' }}
                    />
                  </ListItem>
                ))}
              </List>
            </Paper>
          )}

          {/* Sources */}
          {synthesis?.source_articles?.length > 0 && (
            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle1" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <SourceIcon fontSize="small" />
                Sources ({synthesis.source_articles.length})
              </Typography>
              <List dense sx={{ maxHeight: 500, overflow: 'auto' }}>
                {synthesis.source_articles.map((article, idx) => (
                  <ListItem key={idx} sx={{ px: 0 }}>
                    <ListItemText
                      primary={
                        <Link href={article.url} target="_blank" rel="noopener" underline="hover">
                          {article.title}
                        </Link>
                      }
                      secondary={article.source_name}
                      primaryTypographyProps={{ variant: 'body2' }}
                      secondaryTypographyProps={{ variant: 'caption' }}
                    />
                  </ListItem>
                ))}
              </List>
            </Paper>
          )}
        </Grid>
      </Grid>

      {/* Back Button */}
      <Box sx={{ mt: 3 }}>
        <Button startIcon={<BackIcon />} onClick={() => navigate(-1)}>
          Back to Storyline
        </Button>
      </Box>
    </Container>
  );
}

export default SynthesizedView;

