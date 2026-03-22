/**
 * Context Browser — Phase 4.3 context-centric.
 * List intelligence.contexts with filters (domain, source_type).
 */
import React, { useState, useEffect, useCallback } from 'react';
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
} from '@mui/material';
import Article as ArticleIcon from '@mui/icons-material/Article';
import { contextCentricApi, type Context } from '../../services/api/contextCentric';
import Logger from '../../utils/logger';

const DOMAIN_OPTIONS = [
  { value: '', label: 'All domains' },
  { value: 'politics', label: 'Politics' },
  { value: 'finance', label: 'Finance' },
  { value: 'science-tech', label: 'Science & Tech' },
];

const SOURCE_OPTIONS = [
  { value: '', label: 'All types' },
  { value: 'article', label: 'Article' },
  { value: 'pdf_section', label: 'PDF section' },
  { value: 'structured', label: 'Structured' },
];

function truncate(s: string | null, max: number): string {
  if (!s) return '—';
  return s.length <= max ? s : s.slice(0, max) + '…';
}

const ContextBrowser: React.FC = () => {
  const [items, setItems] = useState<Context[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [domainKey, setDomainKey] = useState<string>('');
  const [sourceType, setSourceType] = useState<string>('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { domain_key?: string; source_type?: string; limit: number; offset: number } = {
        limit: rowsPerPage,
        offset: page * rowsPerPage,
      };
      if (domainKey) params.domain_key = domainKey;
      if (sourceType) params.source_type = sourceType;
      const data = await contextCentricApi.getContexts(params);
      setItems(data.items);
    } catch (e) {
      Logger.apiError('Contexts load failed', e as Error);
      setError((e as Error).message ?? 'Failed to load contexts');
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [domainKey, sourceType, page, rowsPerPage]);

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
        <ArticleIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
        Context Browser
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Universal content units (contexts). Articles and other sources map here. Filter by domain or source type.
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
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel>Source type</InputLabel>
            <Select
              value={sourceType}
              label="Source type"
              onChange={(e) => {
                setSourceType(e.target.value);
                setPage(0);
              }}
            >
              {SOURCE_OPTIONS.map((opt) => (
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
                  <TableCell>ID</TableCell>
                  <TableCell>Title</TableCell>
                  <TableCell>Domain</TableCell>
                  <TableCell>Source</TableCell>
                  <TableCell align="right">Created</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} align="center" sx={{ py: 4 }}>
                      No contexts found. Run context_sync to backfill from articles.
                    </TableCell>
                  </TableRow>
                ) : (
                  items.map((ctx) => (
                    <TableRow key={ctx.id} hover>
                      <TableCell>{ctx.id}</TableCell>
                      <TableCell>
                        <Typography variant="body2" title={ctx.title ?? undefined}>
                          {truncate(ctx.title, 60)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip label={ctx.domain_key} size="small" variant="outlined" />
                      </TableCell>
                      <TableCell>{ctx.source_type}</TableCell>
                      <TableCell align="right">
                        {ctx.created_at ? new Date(ctx.created_at).toLocaleDateString() : '—'}
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

export default ContextBrowser;
