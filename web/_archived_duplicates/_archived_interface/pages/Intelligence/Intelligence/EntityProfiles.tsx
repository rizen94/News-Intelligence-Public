/**
 * Entity Profiles list — Phase 4.1 context-centric.
 * Lists intelligence.entity_profiles with optional domain filter.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Box,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  Button,
  CircularProgress,
  Chip,
} from '@mui/material';
import Person as PersonIcon from '@mui/icons-material/Person';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import { contextCentricApi, type EntityProfile } from '../../services/api/contextCentric';
import Logger from '../../utils/logger';

const DOMAIN_OPTIONS = [
  { value: '', label: 'All domains' },
  { value: 'politics', label: 'Politics' },
  { value: 'finance', label: 'Finance' },
  { value: 'science-tech', label: 'Science & Tech' },
];

function displayName(profile: EntityProfile): string {
  const meta = profile.metadata as Record<string, unknown> | null;
  if (meta && typeof meta.canonical_name === 'string') return meta.canonical_name;
  if (profile.canonical_entity_id != null) return `Entity #${profile.canonical_entity_id}`;
  return `Profile #${profile.id}`;
}

const EntityProfiles: React.FC = () => {
  const { getDomainPath } = useDomainRoute();
  const [items, setItems] = useState<EntityProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [domainKey, setDomainKey] = useState<string>('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [totalLoaded, setTotalLoaded] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { domain_key?: string; limit: number; offset: number } = {
        limit: rowsPerPage,
        offset: page * rowsPerPage,
      };
      if (domainKey) params.domain_key = domainKey;
      const data = await contextCentricApi.getEntityProfiles(params);
      setItems(data.items);
      setTotalLoaded(data.items.length);
    } catch (e) {
      Logger.apiError('Entity profiles load failed', e as Error);
      setError((e as Error).message ?? 'Failed to load entity profiles');
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [domainKey, page, rowsPerPage]);

  useEffect(() => {
    load();
  }, [load]);

  const handleChangePage = (_: unknown, newPage: number) => setPage(newPage);
  const handleChangeRowsPerPage = (e: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(e.target.value, 10));
    setPage(0);
  };

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }} component="h1">
        <PersonIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
        Entity Profiles
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Living entity profiles built from contexts (context-centric pipeline). Filter by domain or browse all.
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
                <MenuItem key={opt.value || 'all'} value={opt.value}>
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
                  <TableCell>Domain</TableCell>
                  <TableCell>Canonical ID</TableCell>
                  <TableCell align="right">Updated</TableCell>
                  <TableCell></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} align="center" sx={{ py: 4 }}>
                      No entity profiles found. Run entity_profile_sync and entity_profile_build tasks to populate.
                    </TableCell>
                  </TableRow>
                ) : (
                  items.map((profile) => (
                    <TableRow key={profile.id} hover>
                      <TableCell>
                        <Typography variant="body2" fontWeight={500}>
                          {displayName(profile)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip label={profile.domain_key} size="small" variant="outlined" />
                      </TableCell>
                      <TableCell>{profile.canonical_entity_id ?? '—'}</TableCell>
                      <TableCell align="right">
                        {profile.updated_at
                          ? new Date(profile.updated_at).toLocaleDateString()
                          : '—'}
                      </TableCell>
                      <TableCell>
                        <Button
                          size="small"
                          component={Link}
                          to={getDomainPath(`/intelligence/entity-profiles/${profile.id}`)}
                        >
                          View
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
            <TablePagination
              rowsPerPageOptions={[10, 25, 50]}
              component="div"
              count={totalLoaded < rowsPerPage ? page * rowsPerPage + totalLoaded : page * rowsPerPage + totalLoaded + 1}
              rowsPerPage={rowsPerPage}
              page={page}
              onPageChange={handleChangePage}
              onRowsPerPageChange={handleChangeRowsPerPage}
              labelRowsPerPage="Rows:"
            />
          </>
        )}
      </TableContainer>
    </Box>
  );
};

export default EntityProfiles;
