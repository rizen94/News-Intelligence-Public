/**
 * Intelligence Search — Phase 4.5 context-centric.
 * Search by claim, entity, pattern, temporal range.
 */
import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  CircularProgress,
  Tabs,
  Tab,
  List,
  ListItem,
  ListItemText,
  Chip,
  Divider,
} from '@mui/material';
import Search as SearchIcon from '@mui/icons-material/Search';
import { useDomain } from '../../contexts/DomainContext';
import { contextCentricApi } from '../../services/api/contextCentric';
import Logger from '../../utils/logger';

const PATTERN_TYPES = ['behavioral', 'temporal', 'network', 'event'];
const DOMAIN_OPTIONS = [
  { value: '', label: 'All domains' },
  { value: 'politics', label: 'Politics' },
  { value: 'finance', label: 'Finance' },
  { value: 'science-tech', label: 'Science & Tech' },
];

const IntelligenceSearch: React.FC = () => {
  const { domain } = useDomain();
  const [q, setQ] = useState('');
  const [claimSubject, setClaimSubject] = useState('');
  const [claimPredicate, setClaimPredicate] = useState('');
  const [entityId, setEntityId] = useState('');
  const [patternType, setPatternType] = useState('');
  const [validFrom, setValidFrom] = useState('');
  const [validTo, setValidTo] = useState('');
  const [domainKey, setDomainKey] = useState(domain || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    claims: Array<{
      id: number;
      context_id: number;
      subject_text: string | null;
      predicate_text: string | null;
      object_text: string | null;
      confidence: number | null;
      valid_from: string | null;
      valid_to: string | null;
      created_at: string | null;
    }>;
    contexts: Array<{
      id: number;
      source_type: string;
      domain_key: string;
      title: string | null;
      content_snippet: string | null;
      created_at: string | null;
    }>;
    pattern_discoveries: Array<{
      id: number;
      pattern_type: string;
      domain_key: string | null;
      confidence: number | null;
      created_at: string | null;
    }>;
  } | null>(null);
  const [tab, setTab] = useState(0);

  const handleSearch = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const params: Record<string, string | number | undefined> = {
        limit: 30,
        offset: 0,
      };
      if (q.trim()) params.q = q.trim();
      if (claimSubject.trim()) params.claim_subject = claimSubject.trim();
      if (claimPredicate.trim()) params.claim_predicate = claimPredicate.trim();
      const eid = entityId.trim() ? parseInt(entityId, 10) : NaN;
      if (!Number.isNaN(eid)) params.entity_id = eid;
      if (patternType) params.pattern_type = patternType;
      if (validFrom) params.valid_from = validFrom;
      if (validTo) params.valid_to = validTo;
      if (domainKey) params.domain_key = domainKey;
      const data = await contextCentricApi.search(params);
      setResult({
        claims: data.claims,
        contexts: data.contexts,
        pattern_discoveries: data.pattern_discoveries,
      });
    } catch (e) {
      Logger.apiError('Intelligence search failed', e as Error);
      setError((e as Error).message ?? 'Search failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }} component="h1">
        <SearchIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
        Intelligence Search
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Search by keyword, claim (subject/predicate), entity profile ID, pattern type, or temporal range (claim validity).
      </Typography>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'flex-start' }}>
          <TextField
            size="small"
            label="Keyword (claims & contexts)"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="e.g. election"
            sx={{ minWidth: 200 }}
          />
          <TextField
            size="small"
            label="Claim subject"
            value={claimSubject}
            onChange={(e) => setClaimSubject(e.target.value)}
            placeholder="ILIKE filter"
            sx={{ minWidth: 160 }}
          />
          <TextField
            size="small"
            label="Claim predicate"
            value={claimPredicate}
            onChange={(e) => setClaimPredicate(e.target.value)}
            placeholder="ILIKE filter"
            sx={{ minWidth: 160 }}
          />
          <TextField
            size="small"
            label="Entity profile ID"
            value={entityId}
            onChange={(e) => setEntityId(e.target.value)}
            placeholder="e.g. 5"
            type="number"
            sx={{ width: 120 }}
          />
          <FormControl size="small" sx={{ minWidth: 130 }}>
            <InputLabel>Pattern type</InputLabel>
            <Select
              value={patternType}
              label="Pattern type"
              onChange={(e) => setPatternType(e.target.value)}
            >
              <MenuItem value="">Any</MenuItem>
              {PATTERN_TYPES.map((t) => (
                <MenuItem key={t} value={t}>
                  {t}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            size="small"
            label="Valid from (date)"
            value={validFrom}
            onChange={(e) => setValidFrom(e.target.value)}
            placeholder="YYYY-MM-DD"
            sx={{ width: 140 }}
          />
          <TextField
            size="small"
            label="Valid to (date)"
            value={validTo}
            onChange={(e) => setValidTo(e.target.value)}
            placeholder="YYYY-MM-DD"
            sx={{ width: 140 }}
          />
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Domain</InputLabel>
            <Select
              value={domainKey}
              label="Domain"
              onChange={(e) => setDomainKey(e.target.value)}
            >
              {DOMAIN_OPTIONS.map((opt) => (
                <MenuItem key={opt.value || 'all'} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Button variant="contained" startIcon={<SearchIcon />} onClick={handleSearch} disabled={loading}>
            {loading ? 'Searching…' : 'Search'}
          </Button>
        </Box>
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {result && (
        <Paper sx={{ mt: 2 }}>
          <Tabs value={tab} onChange={(_, v) => setTab(v)}>
            <Tab label={`Claims (${result.claims.length})`} />
            <Tab label={`Contexts (${result.contexts.length})`} />
            <Tab label={`Patterns (${result.pattern_discoveries.length})`} />
          </Tabs>
          <Box sx={{ p: 2 }}>
            {tab === 0 && (
              <List dense>
                {result.claims.length === 0 ? (
                  <ListItem><ListItemText primary="No claims match." /></ListItem>
                ) : (
                  result.claims.map((c) => (
                    <ListItem key={c.id} divider>
                      <ListItemText
                        primary={
                          <Box component="span">
                            {[c.subject_text, c.predicate_text, c.object_text].filter(Boolean).join(' — ')}
                          </Box>
                        }
                        secondary={
                          <Box sx={{ mt: 0.5 }}>
                            {c.confidence != null && <Chip size="small" label={`${(c.confidence * 100).toFixed(0)}%`} sx={{ mr: 1 }} />}
                            {c.valid_from && <Typography variant="caption">From {c.valid_from}</Typography>}
                            {c.valid_to && <Typography variant="caption" sx={{ ml: 1 }}>To {c.valid_to}</Typography>}
                            <Typography variant="caption" display="block">Context ID: {c.context_id}</Typography>
                          </Box>
                        }
                      />
                    </ListItem>
                  ))
                )}
              </List>
            )}
            {tab === 1 && (
              <List dense>
                {result.contexts.length === 0 ? (
                  <ListItem><ListItemText primary="No contexts match." /></ListItem>
                ) : (
                  result.contexts.map((ctx) => (
                    <ListItem key={ctx.id} divider>
                      <ListItemText
                        primary={ctx.title || `Context #${ctx.id}`}
                        secondary={
                          <>
                            <Chip size="small" label={ctx.domain_key} sx={{ mr: 1 }} />
                            {ctx.content_snippet && (
                              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                                {ctx.content_snippet.slice(0, 200)}…
                              </Typography>
                            )}
                          </>
                        }
                      />
                    </ListItem>
                  ))
                )}
              </List>
            )}
            {tab === 2 && (
              <List dense>
                {result.pattern_discoveries.length === 0 ? (
                  <ListItem><ListItemText primary="No pattern discoveries match." /></ListItem>
                ) : (
                  result.pattern_discoveries.map((p) => (
                    <ListItem key={p.id} divider>
                      <ListItemText
                        primary={<Chip label={p.pattern_type} size="small" />}
                        secondary={
                          <>
                            {p.domain_key && <Typography variant="caption">Domain: {p.domain_key}</Typography>}
                            {p.confidence != null && (
                              <Typography variant="caption" sx={{ ml: 1 }}>
                                Confidence: {(p.confidence * 100).toFixed(0)}%
                              </Typography>
                            )}
                          </>
                        }
                      />
                    </ListItem>
                  ))
                )}
              </List>
            )}
          </Box>
        </Paper>
      )}
    </Box>
  );
};

export default IntelligenceSearch;
