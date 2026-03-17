/**
 * Entity management page (Investigate section).
 * Tab 1: Entity profiles (existing)
 * Tab 2: Canonical entities — browse, search, view aliases, resolve, merge
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  LinearProgress,
  List,
  ListItemButton,
  ListItemText,
  Paper,
  Skeleton,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import MergeIcon from '@mui/icons-material/MergeType';
import SearchIcon from '@mui/icons-material/Search';
import SyncIcon from '@mui/icons-material/Sync';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import LinkIcon from '@mui/icons-material/Link';
import {
  contextCentricApi,
  type CanonicalEntity,
  type EntityProfile,
  type MergeCandidate,
} from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';
import { getCurrentApiUrl } from '@/config/apiConfig';

function displayName(p: EntityProfile): string {
  const meta = p.metadata as Record<string, unknown> | null;
  return (meta?.canonical_name as string) || `Entity #${p.id}`;
}

function entityTypeColor(type: string): 'primary' | 'secondary' | 'success' | 'warning' | 'info' {
  switch (type) {
    case 'person': return 'primary';
    case 'organization': return 'secondary';
    case 'subject': return 'success';
    case 'recurring_event': return 'warning';
    default: return 'info';
  }
}

// ---------------------------------------------------------------------------
// Entity Profiles Tab (existing functionality)
// ---------------------------------------------------------------------------

function EntityProfilesTab() {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const [entities, setEntities] = useState<EntityProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  const loadEntities = useCallback(() => {
    contextCentricApi.getEntityProfiles({ domain_key: domain, limit: 50, brief: true })
      .then((res) => setEntities(res?.items ?? []))
      .catch(() => setEntities([]))
      .finally(() => setLoading(false));
  }, [domain]);

  useEffect(() => {
    setLoading(true);
    loadEntities();
  }, [loadEntities]);

  const handleSyncEntities = async () => {
    setSyncMessage(null);
    setSyncLoading(true);
    try {
      const res = await contextCentricApi.syncEntityProfiles(domain);
      if (res.success && res.created_by_domain) {
        const total = Object.values(res.created_by_domain).reduce((a, b) => a + (b > 0 ? b : 0), 0);
        setSyncMessage(total > 0 ? `Synced: ${total} new entity profile(s).` : 'No new entities to sync.');
        if (total > 0) {
          setLoading(true);
          loadEntities();
        }
      } else {
        setSyncMessage(res.error ?? 'Sync failed.');
      }
    } finally {
      setSyncLoading(false);
    }
  };

  return (
    <>
      {syncMessage && (
        <Alert severity={syncMessage.startsWith('Synced') ? 'success' : 'info'} sx={{ mb: 2 }} onClose={() => setSyncMessage(null)}>
          {syncMessage}
        </Alert>
      )}
      {loading ? (
        <Skeleton variant="rectangular" height={300} />
      ) : entities.length === 0 ? (
        <Box>
          <Typography color="text.secondary" paragraph>
            No entity profiles yet. Run sync to copy from entity_canonical.
          </Typography>
          <Typography variant="caption" display="block" color="text.secondary" sx={{ mb: 1 }}>
            API base: {getCurrentApiUrl() || '(dev proxy)'}
          </Typography>
          <Button variant="outlined" onClick={handleSyncEntities} disabled={syncLoading}>
            {syncLoading ? 'Syncing\u2026' : 'Sync entities for this domain'}
          </Button>
        </Box>
      ) : (
        <>
          <Box sx={{ mb: 2 }}>
            <Button variant="outlined" size="small" onClick={handleSyncEntities} disabled={syncLoading} startIcon={<SyncIcon />}>
              {syncLoading ? 'Syncing\u2026' : 'Sync from canonical'}
            </Button>
          </Box>
          <List dense>
            {entities.map((p) => (
              <ListItemButton key={p.id} onClick={() => navigate(`/${domain}/investigate/entities/${p.id}`)}>
                <ListItemText primary={displayName(p)} secondary={p.domain_key} primaryTypographyProps={{ noWrap: true }} />
              </ListItemButton>
            ))}
          </List>
        </>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Canonical Entities Tab (new — aliases, search, merge)
// ---------------------------------------------------------------------------

function CanonicalEntitiesTab() {
  const { domain } = useDomain();
  const [entities, setEntities] = useState<CanonicalEntity[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState<{ text: string; severity: 'success' | 'info' | 'warning' | 'error' } | null>(null);

  // Merge candidates
  const [candidates, setCandidates] = useState<MergeCandidate[]>([]);
  const [showCandidates, setShowCandidates] = useState(false);
  const [candidatesLoading, setCandidatesLoading] = useState(false);

  // Resolve dialog
  const [resolveOpen, setResolveOpen] = useState(false);
  const [resolveName, setResolveName] = useState('');
  const [resolveType, setResolveType] = useState('person');
  const [resolveResults, setResolveResults] = useState<CanonicalEntity[]>([]);
  const [resolveLoading, setResolveLoading] = useState(false);

  const loadEntities = useCallback(() => {
    setLoading(true);
    const params: Record<string, string | number> = { domain_key: domain, limit: 200, min_mentions: 0 };
    if (search) params.search = search;
    if (typeFilter) params.entity_type = typeFilter;
    contextCentricApi.getCanonicalEntities(params as Parameters<typeof contextCentricApi.getCanonicalEntities>[0])
      .then((res) => setEntities(res?.entities ?? []))
      .catch(() => setEntities([]))
      .finally(() => setLoading(false));
  }, [domain, search, typeFilter]);

  useEffect(() => {
    const t = setTimeout(loadEntities, 300);
    return () => clearTimeout(t);
  }, [loadEntities]);

  const handlePopulateAliases = async () => {
    setActionLoading(true);
    setActionMsg(null);
    try {
      const res = await contextCentricApi.populateAliases(domain);
      const dr = res?.results?.[domain];
      setActionMsg({
        text: `Aliases populated: ${dr?.updated ?? 0} entities updated, ${dr?.new_aliases ?? 0} new aliases added.`,
        severity: 'success',
      });
      loadEntities();
    } catch {
      setActionMsg({ text: 'Failed to populate aliases.', severity: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleAutoMerge = async () => {
    setActionLoading(true);
    setActionMsg(null);
    try {
      const res = await contextCentricApi.autoMergeEntities(domain);
      const dr = res?.results?.[domain];
      setActionMsg({
        text: `Auto-merge: ${dr?.merges_performed ?? 0} entities merged.`,
        severity: 'success',
      });
      loadEntities();
    } catch {
      setActionMsg({ text: 'Failed to auto-merge.', severity: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleCrossDomainLink = async () => {
    setActionLoading(true);
    setActionMsg(null);
    try {
      const res = await contextCentricApi.crossDomainLinkEntities();
      setActionMsg({
        text: `Cross-domain linking: ${res?.relationships_created ?? 0} relationships created from ${res?.linked ?? 0} matches.`,
        severity: 'success',
      });
    } catch {
      setActionMsg({ text: 'Failed to link cross-domain entities.', severity: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleShowCandidates = async () => {
    setCandidatesLoading(true);
    setShowCandidates(true);
    try {
      const res = await contextCentricApi.getMergeCandidates({ domain_key: domain, min_confidence: 0.5, limit: 50 });
      setCandidates(res?.candidates ?? []);
    } catch {
      setCandidates([]);
    } finally {
      setCandidatesLoading(false);
    }
  };

  const handleMerge = async (keepId: number, mergeId: number) => {
    setActionLoading(true);
    try {
      const res = await contextCentricApi.mergeCanonicalEntities({ domain_key: domain, keep_id: keepId, merge_id: mergeId });
      if (res.success) {
        setActionMsg({
          text: `Merged: ${res.articles_reassigned} articles reassigned, ${res.aliases_added} aliases added.`,
          severity: 'success',
        });
        setCandidates((prev) => prev.filter((c) => !(c.source_id === keepId && c.target_id === mergeId)));
        loadEntities();
      } else {
        setActionMsg({ text: res.error || 'Merge failed.', severity: 'error' });
      }
    } catch {
      setActionMsg({ text: 'Merge request failed.', severity: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleResolve = async () => {
    if (!resolveName.trim()) return;
    setResolveLoading(true);
    try {
      const res = await contextCentricApi.resolveEntity({ domain_key: domain, entity_name: resolveName, entity_type: resolveType });
      setResolveResults(res?.candidates ?? []);
    } catch {
      setResolveResults([]);
    } finally {
      setResolveLoading(false);
    }
  };

  return (
    <>
      {actionMsg && (
        <Alert severity={actionMsg.severity} sx={{ mb: 2 }} onClose={() => setActionMsg(null)}>
          {actionMsg.text}
        </Alert>
      )}

      {/* Action buttons */}
      <Stack direction="row" spacing={1} sx={{ mb: 2 }} flexWrap="wrap" useFlexGap>
        <Button size="small" variant="outlined" startIcon={<SyncIcon />} onClick={handlePopulateAliases} disabled={actionLoading}>
          Populate aliases
        </Button>
        <Button size="small" variant="outlined" startIcon={<AutoFixHighIcon />} onClick={handleAutoMerge} disabled={actionLoading}>
          Auto-merge duplicates
        </Button>
        <Button size="small" variant="outlined" startIcon={<MergeIcon />} onClick={handleShowCandidates} disabled={actionLoading}>
          Review merge candidates
        </Button>
        <Button size="small" variant="outlined" startIcon={<LinkIcon />} onClick={handleCrossDomainLink} disabled={actionLoading}>
          Cross-domain link
        </Button>
        <Button size="small" variant="outlined" startIcon={<SearchIcon />} onClick={() => setResolveOpen(true)}>
          Resolve name
        </Button>
      </Stack>

      {actionLoading && <LinearProgress sx={{ mb: 2 }} />}

      {/* Search + filter */}
      <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
        <TextField
          size="small"
          placeholder="Search entities\u2026"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{ flex: 1, maxWidth: 400 }}
        />
        <TextField
          size="small"
          select
          label="Type"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          SelectProps={{ native: true }}
          sx={{ minWidth: 140 }}
        >
          <option value="">All types</option>
          <option value="person">Person</option>
          <option value="organization">Organization</option>
          <option value="subject">Subject</option>
          <option value="recurring_event">Recurring event</option>
        </TextField>
      </Stack>

      {/* Entity table */}
      {loading ? (
        <Skeleton variant="rectangular" height={300} />
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Aliases</TableCell>
                <TableCell align="right">Mentions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {entities.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4}>
                    <Typography color="text.secondary" variant="body2">No canonical entities found.</Typography>
                  </TableCell>
                </TableRow>
              ) : (
                entities.map((e) => (
                  <TableRow key={e.canonical_entity_id} hover>
                    <TableCell>
                      <Typography variant="body2" fontWeight={500}>{e.canonical_name}</Typography>
                    </TableCell>
                    <TableCell>
                      <Chip label={e.entity_type} size="small" color={entityTypeColor(e.entity_type)} variant="outlined" />
                    </TableCell>
                    <TableCell>
                      <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                        {(e.aliases || []).slice(0, 5).map((a, i) => (
                          <Chip key={i} label={a} size="small" variant="outlined" sx={{ fontSize: '0.75rem' }} />
                        ))}
                        {(e.aliases || []).length > 5 && (
                          <Tooltip title={(e.aliases || []).slice(5).join(', ')}>
                            <Chip label={`+${(e.aliases || []).length - 5}`} size="small" />
                          </Tooltip>
                        )}
                      </Stack>
                    </TableCell>
                    <TableCell align="right">{e.mention_count ?? 0}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Merge candidates panel */}
      {showCandidates && (
        <Paper variant="outlined" sx={{ mt: 3, p: 2 }}>
          <Typography variant="subtitle1" gutterBottom>Merge candidates</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Pairs of canonical entities that likely refer to the same real-world entity. Review and merge to consolidate.
          </Typography>
          {candidatesLoading ? (
            <CircularProgress size={24} />
          ) : candidates.length === 0 ? (
            <Typography color="text.secondary" variant="body2">No merge candidates found above threshold.</Typography>
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Keep</TableCell>
                    <TableCell>Merge into</TableCell>
                    <TableCell>Type</TableCell>
                    <TableCell>Confidence</TableCell>
                    <TableCell>Reason</TableCell>
                    <TableCell />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {candidates.map((c, i) => (
                    <TableRow key={i}>
                      <TableCell>{c.source_name}</TableCell>
                      <TableCell>{c.target_name}</TableCell>
                      <TableCell><Chip label={c.entity_type} size="small" variant="outlined" /></TableCell>
                      <TableCell>
                        <Chip
                          label={`${Math.round(c.confidence * 100)}%`}
                          size="small"
                          color={c.confidence >= 0.9 ? 'success' : c.confidence >= 0.7 ? 'warning' : 'default'}
                        />
                      </TableCell>
                      <TableCell>{c.reason.replace(/_/g, ' ')}</TableCell>
                      <TableCell>
                        <Button
                          size="small"
                          variant="contained"
                          color="warning"
                          onClick={() => handleMerge(c.source_id, c.target_id)}
                          disabled={actionLoading}
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
          <Button size="small" sx={{ mt: 1 }} onClick={() => setShowCandidates(false)}>Close</Button>
        </Paper>
      )}

      {/* Resolve dialog */}
      <Dialog open={resolveOpen} onClose={() => setResolveOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Resolve entity name</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Enter a name to find matching canonical entities with confidence scores.
          </Typography>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Entity name" fullWidth value={resolveName} onChange={(e) => setResolveName(e.target.value)} />
            <TextField
              label="Type"
              select
              fullWidth
              value={resolveType}
              onChange={(e) => setResolveType(e.target.value)}
              SelectProps={{ native: true }}
            >
              <option value="person">Person</option>
              <option value="organization">Organization</option>
              <option value="subject">Subject</option>
              <option value="recurring_event">Recurring event</option>
            </TextField>
            <Button variant="contained" onClick={handleResolve} disabled={resolveLoading || !resolveName.trim()}>
              {resolveLoading ? 'Resolving\u2026' : 'Resolve'}
            </Button>
          </Stack>
          {resolveResults.length > 0 && (
            <TableContainer sx={{ mt: 2 }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Name</TableCell>
                    <TableCell>Confidence</TableCell>
                    <TableCell>Reason</TableCell>
                    <TableCell>Aliases</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {resolveResults.map((r) => (
                    <TableRow key={r.canonical_entity_id}>
                      <TableCell>{r.canonical_name}</TableCell>
                      <TableCell>
                        <Chip
                          label={`${Math.round((r.confidence ?? 0) * 100)}%`}
                          size="small"
                          color={(r.confidence ?? 0) >= 0.9 ? 'success' : (r.confidence ?? 0) >= 0.7 ? 'warning' : 'default'}
                        />
                      </TableCell>
                      <TableCell>{(r.match_reason || '').replace(/_/g, ' ')}</TableCell>
                      <TableCell>
                        {(r.aliases || []).slice(0, 3).map((a, i) => (
                          <Chip key={i} label={a} size="small" variant="outlined" sx={{ mr: 0.5, fontSize: '0.7rem' }} />
                        ))}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setResolveOpen(false); setResolveResults([]); }}>Close</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

// ---------------------------------------------------------------------------
// Top Entities Tab — ranked by mention count, with dossier links
// ---------------------------------------------------------------------------

function TopEntitiesTab() {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const [entities, setEntities] = useState<CanonicalEntity[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState('');

  const loadTopEntities = useCallback(() => {
    setLoading(true);
    const params: Parameters<typeof contextCentricApi.getCanonicalEntities>[0] = {
      domain_key: domain,
      limit: 50,
      min_mentions: 3,
    };
    if (typeFilter) params.entity_type = typeFilter;
    contextCentricApi.getCanonicalEntities(params)
      .then((res) => {
        const sorted = [...(res?.entities ?? [])].sort(
          (a, b) => (b.mention_count ?? 0) - (a.mention_count ?? 0),
        );
        setEntities(sorted);
      })
      .catch(() => setEntities([]))
      .finally(() => setLoading(false));
  }, [domain, typeFilter]);

  useEffect(() => { loadTopEntities(); }, [loadTopEntities]);

  return (
    <Box>
      <Stack direction="row" spacing={1} sx={{ mb: 2, alignItems: 'center' }}>
        <Typography variant="body2" color="text.secondary">Filter:</Typography>
        {['', 'person', 'organization', 'subject'].map((t) => (
          <Chip
            key={t || 'all'}
            label={t || 'All'}
            size="small"
            variant={typeFilter === t ? 'filled' : 'outlined'}
            color={typeFilter === t ? 'primary' : 'default'}
            onClick={() => setTypeFilter(t)}
          />
        ))}
      </Stack>
      {loading ? (
        <Skeleton variant="rectangular" height={300} />
      ) : entities.length === 0 ? (
        <Typography color="text.secondary">No entities with 3+ mentions found.</Typography>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600 }}>Entity</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Type</TableCell>
                <TableCell align="right" sx={{ fontWeight: 600 }}>Mentions</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>Aliases</TableCell>
                <TableCell align="center" sx={{ fontWeight: 600 }}>Dossier</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {entities.map((e) => (
                <TableRow
                  key={e.canonical_entity_id}
                  hover
                  sx={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/${domain}/investigate/entities/${e.canonical_entity_id}/dossier`)}
                >
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>{e.canonical_name}</Typography>
                  </TableCell>
                  <TableCell>
                    <Chip label={e.entity_type} size="small" color={entityTypeColor(e.entity_type)} variant="outlined" />
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" sx={{ fontWeight: 700 }}>{e.mention_count ?? 0}</Typography>
                  </TableCell>
                  <TableCell>
                    {(e.aliases || []).slice(0, 2).map((a, i) => (
                      <Chip key={i} label={a} size="small" variant="outlined" sx={{ mr: 0.5, fontSize: '0.7rem' }} />
                    ))}
                    {(e.aliases?.length ?? 0) > 2 && (
                      <Typography variant="caption" color="text.secondary">+{(e.aliases?.length ?? 0) - 2}</Typography>
                    )}
                  </TableCell>
                  <TableCell align="center">
                    <Button size="small" variant="outlined" onClick={(ev) => {
                      ev.stopPropagation();
                      navigate(`/${domain}/investigate/entities/${e.canonical_entity_id}/dossier`);
                    }}>
                      View
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Main page with tabs
// ---------------------------------------------------------------------------

export default function EntitiesListPage() {
  const { domain } = useDomain();
  const [tab, setTab] = useState(0);

  return (
    <Card>
      <CardHeader title="Entity management" subheader={domain} />
      <CardContent>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
          <Tab label="Top entities" />
          <Tab label="Entity profiles" />
          <Tab label="Canonical entities" />
        </Tabs>
        <Divider sx={{ mb: 2 }} />
        {tab === 0 && <TopEntitiesTab />}
        {tab === 1 && <EntityProfilesTab />}
        {tab === 2 && <CanonicalEntitiesTab />}
      </CardContent>
    </Card>
  );
}
