import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  TextField,
  Button,
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
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  ToggleButtonGroup,
  ToggleButton,
  Slider,
  FormControlLabel,
  Switch,
  Tab,
  Tabs,
  Tooltip,
  IconButton,
  Link,
} from '@mui/material';
import {
  Search as SearchIcon,
  ExpandMore as ExpandMoreIcon,
  Lightbulb as InsightIcon,
  Source as SourceIcon,
  MenuBook as TermIcon,
  Person as EntityIcon,
  Timeline as TimelineIcon,
  Public as PublicIcon,
  TrendingUp as TrendingIcon,
  Science as ScienceIcon,
  AccountBalance as PoliticsIcon,
  AttachMoney as FinanceIcon,
  Psychology as AIIcon,
  OpenInNew as OpenNewIcon,
  ContentCopy as CopyIcon,
} from '@mui/icons-material';
import apiService from '../../services/apiService';

const DOMAIN_ICONS = {
  politics: <PoliticsIcon />,
  finance: <FinanceIcon />,
  'science-tech': <ScienceIcon />,
};

const DOMAIN_COLORS = {
  politics: '#d32f2f',
  finance: '#388e3c',
  'science-tech': '#1976d2',
};

function TabPanel({ children, value, index, ...other }) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`rag-tabpanel-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 2 }}>{children}</Box>}
    </div>
  );
}

function DomainRAG() {
  const [query, setQuery] = useState('');
  const [domain, setDomain] = useState('politics');
  const [hours, setHours] = useState(72);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [crossDomain, setCrossDomain] = useState(false);
  const [tabValue, setTabValue] = useState(0);
  const [entities, setEntities] = useState([]);
  const [terminology, setTerminology] = useState({});
  const [sources, setSources] = useState([]);
  const [loadingKnowledge, setLoadingKnowledge] = useState(false);

  // Load domain knowledge base on domain change
  useEffect(() => {
    loadDomainKnowledge();
  }, [domain]);

  async function loadDomainKnowledge() {
    setLoadingKnowledge(true);
    try {
      const [entitiesRes, termsRes, sourcesRes] = await Promise.all([
        fetch(`/api/v4/${domain}/rag/knowledge/entities`),
        fetch(`/api/v4/${domain}/rag/knowledge/terminology`),
        fetch(`/api/v4/${domain}/rag/knowledge/sources`),
      ]);

      if (entitiesRes.ok) {
        const data = await entitiesRes.json();
        setEntities(data.entities || []);
      }
      if (termsRes.ok) {
        const data = await termsRes.json();
        setTerminology(data.terminology || {});
      }
      if (sourcesRes.ok) {
        const data = await sourcesRes.json();
        setSources(data.sources || []);
      }
    } catch (err) {
      console.error('Failed to load domain knowledge:', err);
    } finally {
      setLoadingKnowledge(false);
    }
  }

  async function handleQuery() {
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      let response;
      if (crossDomain) {
        response = await fetch('/api/v4/rag/cross-domain', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query, hours, max_chunks: 10 }),
        });
      } else {
        response = await fetch(`/api/v4/${domain}/rag/query`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query, hours, max_chunks: 10 }),
        });
      }

      if (!response.ok) {
        throw new Error(`Query failed: ${response.status}`);
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyPress(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleQuery();
    }
  }

  function copyToClipboard(text) {
    navigator.clipboard.writeText(text);
  }

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" component="h1" sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <AIIcon sx={{ fontSize: 40 }} />
          Domain-Aware RAG Analysis
        </Typography>
        <Typography variant="subtitle1" color="text.secondary" sx={{ mt: 1 }}>
          Query news with domain-specific knowledge enrichment
        </Typography>
      </Box>

      {/* Query Interface */}
      <Paper sx={{ p: 3, mb: 4 }}>
        <Grid container spacing={3}>
          {/* Domain Selection */}
          <Grid item xs={12}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
              <ToggleButtonGroup
                value={domain}
                exclusive
                onChange={(e, val) => val && setDomain(val)}
                disabled={crossDomain}
              >
                <ToggleButton value="politics" sx={{ gap: 1 }}>
                  <PoliticsIcon /> Politics
                </ToggleButton>
                <ToggleButton value="finance" sx={{ gap: 1 }}>
                  <FinanceIcon /> Finance
                </ToggleButton>
                <ToggleButton value="science-tech" sx={{ gap: 1 }}>
                  <ScienceIcon /> Science & Tech
                </ToggleButton>
              </ToggleButtonGroup>

              <FormControlLabel
                control={
                  <Switch
                    checked={crossDomain}
                    onChange={(e) => setCrossDomain(e.target.checked)}
                  />
                }
                label="Cross-Domain Analysis"
              />
            </Box>
          </Grid>

          {/* Time Range */}
          <Grid item xs={12} md={4}>
            <Typography gutterBottom>Time Range: {hours} hours</Typography>
            <Slider
              value={hours}
              onChange={(e, val) => setHours(val)}
              min={6}
              max={168}
              step={6}
              marks={[
                { value: 24, label: '24h' },
                { value: 72, label: '3d' },
                { value: 168, label: '7d' },
              ]}
            />
          </Grid>

          {/* Query Input */}
          <Grid item xs={12}>
            <TextField
              fullWidth
              multiline
              rows={2}
              variant="outlined"
              placeholder="Ask a question about current news events..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyPress={handleKeyPress}
              InputProps={{
                endAdornment: (
                  <Button
                    variant="contained"
                    onClick={handleQuery}
                    disabled={loading || !query.trim()}
                    startIcon={loading ? <CircularProgress size={20} /> : <SearchIcon />}
                    sx={{ ml: 1 }}
                  >
                    Analyze
                  </Button>
                ),
              }}
            />
          </Grid>
        </Grid>
      </Paper>

      {/* Error Display */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Results */}
      {result && (
        <Grid container spacing={3}>
          {/* Main Answer */}
          <Grid item xs={12} md={8}>
            <Paper sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <InsightIcon color="primary" />
                  Analysis Result
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Chip
                    label={`${Math.round((result.confidence || 0) * 100)}% confidence`}
                    color={result.confidence > 0.7 ? 'success' : result.confidence > 0.4 ? 'warning' : 'default'}
                    size="small"
                  />
                  <Tooltip title="Copy response">
                    <IconButton size="small" onClick={() => copyToClipboard(result.answer || result.synthesized_answer)}>
                      <CopyIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Box>
              </Box>

              <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>
                {result.answer || result.synthesized_answer}
              </Typography>

              {result.processing_time_ms && (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
                  Processed in {result.processing_time_ms.toFixed(0)}ms
                </Typography>
              )}

              {/* Cross-domain results */}
              {crossDomain && result.domain_results && (
                <Box sx={{ mt: 3 }}>
                  <Divider sx={{ mb: 2 }} />
                  <Typography variant="subtitle2" gutterBottom>Domain-Specific Perspectives:</Typography>
                  <Grid container spacing={2}>
                    {Object.entries(result.domain_results).map(([dom, data]) => (
                      <Grid item xs={12} md={4} key={dom}>
                        <Card variant="outlined" sx={{ borderColor: DOMAIN_COLORS[dom] }}>
                          <CardContent>
                            <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center', gap: 1, color: DOMAIN_COLORS[dom] }}>
                              {DOMAIN_ICONS[dom]}
                              {dom.replace('-', ' ').toUpperCase()}
                            </Typography>
                            <Typography variant="body2" sx={{ mt: 1, fontSize: '0.85rem' }}>
                              {data.answer?.slice(0, 200)}...
                            </Typography>
                          </CardContent>
                        </Card>
                      </Grid>
                    ))}
                  </Grid>
                </Box>
              )}
            </Paper>

            {/* Sources */}
            {result.sources_cited && result.sources_cited.length > 0 && (
              <Paper sx={{ p: 3, mt: 2 }}>
                <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <SourceIcon color="primary" />
                  Sources Cited
                </Typography>
                <List dense>
                  {result.sources_cited.map((source, idx) => (
                    <ListItem key={idx}>
                      <ListItemIcon>
                        <SourceIcon fontSize="small" />
                      </ListItemIcon>
                      <ListItemText primary={source} />
                    </ListItem>
                  ))}
                </List>
              </Paper>
            )}

            {/* Historical Context */}
            {result.historical_context && (
              <Paper sx={{ p: 3, mt: 2 }}>
                <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <TimelineIcon color="primary" />
                  Historical Context
                </Typography>
                <Typography variant="body2">
                  {result.historical_context}
                </Typography>
              </Paper>
            )}
          </Grid>

          {/* Side Panel */}
          <Grid item xs={12} md={4}>
            {/* Domain Entities Found */}
            {result.domain_entities && result.domain_entities.length > 0 && (
              <Paper sx={{ p: 2, mb: 2 }}>
                <Typography variant="subtitle1" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  <EntityIcon fontSize="small" />
                  Relevant Entities
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {result.domain_entities.map((entity, idx) => (
                    <Chip
                      key={idx}
                      label={entity.name}
                      size="small"
                      variant="outlined"
                      color={entity.importance > 0.8 ? 'primary' : 'default'}
                    />
                  ))}
                </Box>
              </Paper>
            )}

            {/* Key Terms */}
            {result.key_terms && Object.keys(result.key_terms).length > 0 && (
              <Paper sx={{ p: 2, mb: 2 }}>
                <Typography variant="subtitle1" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  <TermIcon fontSize="small" />
                  Key Terms
                </Typography>
                {Object.entries(result.key_terms).map(([term, def], idx) => (
                  <Accordion key={idx} disableGutters sx={{ boxShadow: 'none' }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ px: 0 }}>
                      <Typography variant="body2" fontWeight="medium">{term}</Typography>
                    </AccordionSummary>
                    <AccordionDetails sx={{ px: 0 }}>
                      <Typography variant="caption">{def}</Typography>
                    </AccordionDetails>
                  </Accordion>
                ))}
              </Paper>
            )}

            {/* Related Topics */}
            {result.related_topics && result.related_topics.length > 0 && (
              <Paper sx={{ p: 2 }}>
                <Typography variant="subtitle1" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  <TrendingIcon fontSize="small" />
                  Related Topics
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {result.related_topics.map((topic, idx) => (
                    <Chip
                      key={idx}
                      label={topic}
                      size="small"
                      onClick={() => setQuery(`What is ${topic}?`)}
                      clickable
                    />
                  ))}
                </Box>
              </Paper>
            )}
          </Grid>
        </Grid>
      )}

      {/* Domain Knowledge Base Browser */}
      <Paper sx={{ mt: 4, p: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          {domain.replace('-', ' ').toUpperCase()} Knowledge Base
        </Typography>

        <Tabs value={tabValue} onChange={(e, v) => setTabValue(v)}>
          <Tab label={`Entities (${entities.length})`} icon={<EntityIcon />} iconPosition="start" />
          <Tab label={`Terminology (${Object.keys(terminology).length})`} icon={<TermIcon />} iconPosition="start" />
          <Tab label={`Sources (${sources.length})`} icon={<PublicIcon />} iconPosition="start" />
        </Tabs>

        {loadingKnowledge ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <CircularProgress />
          </Box>
        ) : (
          <>
            <TabPanel value={tabValue} index={0}>
              <Grid container spacing={2}>
                {entities.slice(0, 12).map((entity, idx) => (
                  <Grid item xs={12} sm={6} md={4} key={idx}>
                    <Card variant="outlined">
                      <CardContent>
                        <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          {entity.name}
                          <Chip label={entity.type} size="small" variant="outlined" />
                        </Typography>
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                          {entity.description?.slice(0, 100)}
                          {entity.description?.length > 100 ? '...' : ''}
                        </Typography>
                        {entity.aliases && entity.aliases.length > 0 && (
                          <Box sx={{ mt: 1 }}>
                            {entity.aliases.slice(0, 3).map((alias, i) => (
                              <Chip key={i} label={alias} size="small" sx={{ mr: 0.5, mb: 0.5 }} />
                            ))}
                          </Box>
                        )}
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            </TabPanel>

            <TabPanel value={tabValue} index={1}>
              <List>
                {Object.entries(terminology).map(([term, definition], idx) => (
                  <React.Fragment key={idx}>
                    <ListItem>
                      <ListItemText
                        primary={<Typography fontWeight="medium">{term}</Typography>}
                        secondary={definition}
                      />
                    </ListItem>
                    {idx < Object.keys(terminology).length - 1 && <Divider />}
                  </React.Fragment>
                ))}
              </List>
            </TabPanel>

            <TabPanel value={tabValue} index={2}>
              <Grid container spacing={2}>
                {sources.map((source, idx) => (
                  <Grid item xs={12} sm={6} md={4} key={idx}>
                    <Card variant="outlined">
                      <CardContent>
                        <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          {source.name}
                          <Link href={source.url} target="_blank" rel="noopener">
                            <IconButton size="small">
                              <OpenNewIcon fontSize="small" />
                            </IconButton>
                          </Link>
                        </Typography>
                        <Chip label={source.type} size="small" sx={{ mt: 1 }} />
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            </TabPanel>
          </>
        )}
      </Paper>
    </Container>
  );
}

export default DomainRAG;

