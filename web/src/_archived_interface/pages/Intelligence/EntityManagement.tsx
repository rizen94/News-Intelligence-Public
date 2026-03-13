/**
 * Entity Management — Phase 4.2 context-centric.
 * Control panel: importance, merge tool. Same domain required for merge.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Box,
  Typography,
  Paper,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Button,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  CircularProgress,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import Person as PersonIcon from '@mui/icons-material/Person';
import Merge as MergeIcon from '@mui/icons-material/Merge';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import { contextCentricApi, type EntityProfile } from '../../services/api/contextCentric';
import Logger from '../../utils/logger';

const DOMAIN_OPTIONS = [
  { value: 'politics', label: 'Politics' },
  { value: 'finance', label: 'Finance' },
  { value: 'science-tech', label: 'Science & Tech' },
];

const IMPORTANCE_OPTIONS = [
  { value: '', label: '—' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
] as const;

function displayName(profile: EntityProfile): string {
  const meta = profile.metadata as Record<string, unknown> | null;
  if (meta && typeof meta.canonical_name === 'string') return meta.canonical_name;
  if (meta?.merged_into_profile_id) return `(merged into #${meta.merged_into_profile_id})`;
  if (profile.canonical_entity_id != null) return `Entity #${profile.canonical_entity_id}`;
  return `Profile #${profile.id}`;
}

function getImportance(profile: EntityProfile): string {
  const meta = profile.metadata as Record<string, unknown> | null;
  const v = meta?.importance;
  return typeof v === 'string' && ['high', 'medium', 'low'].includes(v) ? v : '';
}

const EntityManagement: React.FC = () => {
  const { getDomainPath } = useDomainRoute();
  const [items, setItems] = useState<EntityProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [domainKey, setDomainKey] = useState<string>('politics');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [mergeTargetId, setMergeTargetId] = useState<number | null>(null);
  const [mergeSourceId, setMergeSourceId] = useState<number>(-1);
  const [mergeLoading, setMergeLoading] = useState(false);
  const [mergeError, setMergeError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await contextCentricApi.getEntityProfiles({
        domain_key: domainKey,
        limit: rowsPerPage,
        offset: page * rowsPerPage,
      });
      setItems(data.items);
    } catch (e) {
      Logger.apiError('Entity management load failed', e as Error);
      setError((e as Error).message ?? 'Failed to load profiles');
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [domainKey, page, rowsPerPage]);

  useEffect(() => {
    load();
  }, [load]);

  const handleImportanceChange = async (profileId: number, importance: string) => {
    setSavingId(profileId);
    setError(null);
    try {
      await contextCentricApi.updateEntityProfile(profileId, {
        importance: importance === '' ? undefined : (importance as 'high' | 'medium' | 'low'),
      });
      setItems((prev) =>
        prev.map((p) =>
          p.id === profileId
            ? { ...p, metadata: { ...(p.metadata as object), importance: importance || undefined } }
            : p,
        ),
      );
    } catch (e) {
      Logger.apiError('Update importance failed', e as Error);
      setError((e as Error).message ?? 'Failed to update');
    } finally {
      setSavingId(null);
    }
  };

  const openMerge = (targetId: number) => {
    setMergeTargetId(targetId);
    setMergeSourceId(-1);
    setMergeError(null);
  };
  const closeMerge = () => {
    setMergeTargetId(null);
    setMergeSourceId(-1);
    setMergeError(null);
  };
  const confirmMerge = async () => {
    if (mergeTargetId == null || mergeSourceId < 0 || mergeSourceId === mergeTargetId) return;
    setMergeLoading(true);
    setMergeError(null);
    try {
      await contextCentricApi.mergeEntityProfiles(mergeTargetId, mergeSourceId);
      closeMerge();
      load();
    } catch (e) {
      Logger.apiError('Merge failed', e as Error);
      setMergeError((e as Error).message ?? 'Merge failed');
    } finally {
      setMergeLoading(false);
    }
  };

  const isMerged = (p: EntityProfile) => (p.metadata as Record<string, unknown>)?.merged_into_profile_id != null;
  const mergeCandidates = items.filter((p) => !isMerged(p) && p.id !== mergeTargetId);

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }} component="h1">
        <PersonIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
        Entity Management
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Set importance and merge duplicate entity profiles (same domain only). Merged profiles are retained for audit.
      </Typography>

      <Paper sx={{ mb: 2 }}>
        <Box sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel>Domain</InputLabel>
            <Select
              value={domainKey}
              label="Domain"
              onChange={(e) => {
                setDomainKey(e.target.value);
                setPage(0);
              }}
            >
              {DOMAIN_OPTIONS.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Button variant="outlined" size="small" onClick={load} disabled={loading}>
            Refresh
          </Button>
        </Box>
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <TableContainer component={Paper}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : (
          <>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Importance</TableCell>
                  <TableCell>Canonical ID</TableCell>
                  <TableCell align="right">Updated</TableCell>
                  <TableCell></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} align="center" sx={{ py: 4 }}>
                      No entity profiles in this domain. Run entity_profile_sync to populate.
                    </TableCell>
                  </TableRow>
                ) : (
                  items.map((profile) => (
                    <TableRow key={profile.id} hover sx={{ opacity: isMerged(profile) ? 0.7 : 1 }}>
                      <TableCell>
                        <Typography variant="body2" fontWeight={500}>
                          {displayName(profile)}
                        </Typography>
                        {isMerged(profile) && (
                          <Chip size="small" label="Merged" color="default" sx={{ mt: 0.5 }} />
                        )}
                      </TableCell>
                      <TableCell>
                        <Select
                          size="small"
                          value={getImportance(profile)}
                          onChange={(e) => handleImportanceChange(profile.id, e.target.value)}
                          disabled={savingId === profile.id || isMerged(profile)}
                          sx={{ minWidth: 110 }}
                        >
                          {IMPORTANCE_OPTIONS.map((opt) => (
                            <MenuItem key={opt.value || 'none'} value={opt.value}>
                              {opt.label}
                            </MenuItem>
                          ))}
                        </Select>
                        {savingId === profile.id && <CircularProgress size={14} sx={{ ml: 1 }} />}
                      </TableCell>
                      <TableCell>{profile.canonical_entity_id ?? '—'}</TableCell>
                      <TableCell align="right">
                        {profile.updated_at ? new Date(profile.updated_at).toLocaleDateString() : '—'}
                      </TableCell>
                      <TableCell>
                        <Button
                          size="small"
                          component={Link}
                          to={getDomainPath(`/intelligence/entity-profiles/${profile.id}`)}
                          sx={{ mr: 1 }}
                        >
                          View
                        </Button>
                        {!isMerged(profile) && (
                          <Button
                            size="small"
                            startIcon={<MergeIcon />}
                            onClick={() => openMerge(profile.id)}
                          >
                            Merge into…
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
            <TablePagination
              rowsPerPageOptions={[10, 25, 50]}
              component="div"
              count={items.length < rowsPerPage ? page * rowsPerPage + items.length : page * rowsPerPage + items.length + 1}
              rowsPerPage={rowsPerPage}
              page={page}
              onPageChange={(_, newPage) => setPage(newPage)}
              onRowsPerPageChange={(e) => {
                setRowsPerPage(parseInt(e.target.value, 10));
                setPage(0);
              }}
              labelRowsPerPage="Rows:"
            />
          </>
        )}
      </TableContainer>

      <Dialog open={mergeTargetId != null} onClose={closeMerge} maxWidth="sm" fullWidth>
        <DialogTitle>Merge entity profile into this one</DialogTitle>
        <DialogContent>
          {mergeTargetId != null && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Target: <strong>{items.find((p) => p.id === mergeTargetId)?.metadata && displayName(items.find((p) => p.id === mergeTargetId)!)}</strong> (ID {mergeTargetId}).
              Select the source profile to merge into it. Mappings and mentions will point to the target.
            </Typography>
          )}
          <FormControl fullWidth size="small">
            <InputLabel>Source profile</InputLabel>
            <Select
              value={mergeSourceId < 0 ? '' : mergeSourceId}
              label="Source profile"
              onChange={(e) => setMergeSourceId(Number(e.target.value))}
            >
              <MenuItem value="">— Select —</MenuItem>
              {mergeCandidates.map((p) => (
                <MenuItem key={p.id} value={p.id}>
                  {displayName(p)} (ID {p.id})
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          {mergeError && (
            <Alert severity="error" sx={{ mt: 2 }} onClose={() => setMergeError(null)}>
              {mergeError}
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={closeMerge}>Cancel</Button>
          <Button
            variant="contained"
            onClick={confirmMerge}
            disabled={mergeLoading || mergeSourceId < 0 || mergeSourceId === mergeTargetId}
          >
            {mergeLoading ? 'Merging…' : 'Merge'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default EntityManagement;
