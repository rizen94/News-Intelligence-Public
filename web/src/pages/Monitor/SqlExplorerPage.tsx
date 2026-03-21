/**
 * Read-only SQL explorer — schema browser + SELECT / EXPLAIN / TABLE.
 * API must set NEWS_INTEL_SQL_EXPLORER=true (trusted / local use only).
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  CircularProgress,
  Collapse,
  IconButton,
  Link,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import { Link as RouterLink } from 'react-router-dom';
import { useDomainRoute } from '@/hooks/useDomainRoute';
import apiService from '@/services/apiService';
import Logger from '@/utils/logger';

type SchemaColumn = { name: string; data_type: string; nullable: boolean };
type SchemaTable = { schema: string; table: string; columns: SchemaColumn[] };

type SqlQueryOk = {
  success: true;
  columns?: string[];
  rows?: unknown[][];
  row_count_returned?: number;
  truncated?: boolean;
  cursor_rowcount?: number | null;
};

const DEFAULT_SQL = `SELECT phase_name, COUNT(*) AS runs,
  SUM(CASE WHEN success THEN 1 ELSE 0 END) AS ok
FROM automation_run_history
WHERE finished_at >= NOW() AT TIME ZONE 'UTC' - INTERVAL '4 days'
GROUP BY phase_name
ORDER BY runs DESC
LIMIT 50;`;

export default function SqlExplorerPage() {
  const { domain } = useDomainRoute();
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [schemaOpen, setSchemaOpen] = useState(true);
  const [tables, setTables] = useState<SchemaTable[]>([]);
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [sql, setSql] = useState(DEFAULT_SQL);
  const [maxRows, setMaxRows] = useState(500);
  const [loadingSchema, setLoadingSchema] = useState(false);
  const [running, setRunning] = useState(false);
  const [columns, setColumns] = useState<string[]>([]);
  const [rows, setRows] = useState<unknown[][]>([]);
  const [truncated, setTruncated] = useState(false);
  const [resultMeta, setResultMeta] = useState<string | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);

  const refreshEnabled = useCallback(async () => {
    const res = await apiService.getSqlExplorerEnabled();
    setEnabled(!!res.enabled);
  }, []);

  const loadSchema = useCallback(async () => {
    setLoadingSchema(true);
    setSchemaError(null);
    try {
      const res = await apiService.getSqlExplorerSchema();
      if (res.success && res.tables) setTables(res.tables);
      else setSchemaError(res.error || 'Could not load schema');
    } catch (e) {
      setSchemaError((e as Error).message);
      Logger.error('SqlExplorer schema', e as Error);
    } finally {
      setLoadingSchema(false);
    }
  }, []);

  useEffect(() => {
    void refreshEnabled();
  }, [refreshEnabled]);

  useEffect(() => {
    if (enabled) void loadSchema();
  }, [enabled, loadSchema]);

  const runQuery = async () => {
    setRunning(true);
    setQueryError(null);
    setResultMeta(null);
    try {
      const res = await apiService.postSqlExplorerQuery(sql, maxRows);
      if (!res.success) {
        setColumns([]);
        setRows([]);
        setQueryError(
          'error' in res && res.error
            ? res.error
            : (res as { detail?: string }).detail || 'Query failed'
        );
        return;
      }
      const ok = res as SqlQueryOk;
      setColumns(ok.columns || []);
      setRows((ok.rows || []) as unknown[][]);
      setTruncated(!!ok.truncated);
      const n = ok.row_count_returned ?? (ok.rows || []).length;
      const crc = ok.cursor_rowcount;
      setResultMeta(
        `${n} row(s)${ok.truncated ? ' (truncated to max_rows)' : ''}` +
          (crc != null && crc >= 0 ? ` · cursor rowcount ${crc}` : '')
      );
    } finally {
      setRunning(false);
    }
  };

  return (
    <Box sx={{ p: 2, maxWidth: 1400, mx: 'auto' }}>
      <Typography variant='h5' sx={{ mb: 1 }}>
        SQL explorer
      </Typography>
      <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>
        Read-only queries against your Postgres (SELECT / WITH / TABLE /
        EXPLAIN). For heavier work,{' '}
        <Link
          href='https://www.pgadmin.org/'
          target='_blank'
          rel='noopener noreferrer'
        >
          pgAdmin
        </Link>
        ,{' '}
        <Link
          href='https://dbeaver.io/'
          target='_blank'
          rel='noopener noreferrer'
        >
          DBeaver
        </Link>
        , or <code>psql</code> are safer and more capable.
      </Typography>

      <Alert severity='warning' sx={{ mb: 2 }}>
        Enabling this on an API reachable from untrusted networks exposes all
        data the DB user can read. Use <code>NEWS_INTEL_SQL_EXPLORER=true</code>{' '}
        only on trusted hosts or VPN.
      </Alert>

      {enabled === false && (
        <Alert severity='info' sx={{ mb: 2 }}>
          SQL explorer is off. Set environment variable{' '}
          <code>NEWS_INTEL_SQL_EXPLORER=true</code> on the API server and
          restart, then reload this page.
        </Alert>
      )}

      <Box sx={{ mb: 1 }}>
        <Link
          component={RouterLink}
          to={`/${domain}/monitor`}
          underline='hover'
        >
          ← Back to Monitor
        </Link>
      </Box>

      <Card sx={{ mb: 2 }}>
        <CardHeader
          title={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <span>Tables &amp; columns</span>
              <IconButton
                size='small'
                onClick={() => setSchemaOpen(!schemaOpen)}
                aria-label='toggle schema'
              >
                {schemaOpen ? <ExpandLessIcon /> : <ExpandMoreIcon />}
              </IconButton>
              {loadingSchema && <CircularProgress size={20} />}
            </Box>
          }
          subheader='pg_catalog / information_schema hidden'
        />
        <Collapse in={schemaOpen}>
          <CardContent>
            {schemaError && (
              <Alert severity='error' sx={{ mb: 1 }}>
                {schemaError}
              </Alert>
            )}
            {tables.length === 0 &&
              !loadingSchema &&
              enabled &&
              !schemaError && (
                <Typography color='text.secondary'>
                  No tables returned.
                </Typography>
              )}
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                gap: 2,
                maxHeight: 360,
                overflow: 'auto',
              }}
            >
              {tables.map(t => (
                <Paper
                  key={`${t.schema}.${t.table}`}
                  variant='outlined'
                  sx={{ p: 1.5 }}
                >
                  <Typography
                    variant='subtitle2'
                    sx={{ fontFamily: 'monospace', mb: 0.5 }}
                  >
                    {t.schema}.{t.table}
                  </Typography>
                  <Typography
                    variant='caption'
                    component='div'
                    color='text.secondary'
                    sx={{ fontFamily: 'monospace' }}
                  >
                    {t.columns
                      .map(
                        c =>
                          `${c.name} (${c.data_type}${
                            c.nullable ? '' : ' NOT NULL'
                          })`
                      )
                      .join(', ')}
                  </Typography>
                </Paper>
              ))}
            </Box>
            <Button
              size='small'
              onClick={() => void loadSchema()}
              disabled={!enabled || loadingSchema}
              sx={{ mt: 1 }}
            >
              Refresh schema
            </Button>
          </CardContent>
        </Collapse>
      </Card>

      <Card sx={{ mb: 2 }}>
        <CardHeader title='Query' />
        <CardContent>
          <TextField
            fullWidth
            multiline
            minRows={8}
            value={sql}
            onChange={e => setSql(e.target.value)}
            disabled={!enabled}
            sx={{ fontFamily: 'monospace', mb: 2 }}
            InputProps={{
              sx: { fontFamily: 'monospace', fontSize: '0.85rem' },
            }}
          />
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 2,
              flexWrap: 'wrap',
            }}
          >
            <TextField
              label='Max rows'
              type='number'
              size='small'
              value={maxRows}
              onChange={e =>
                setMaxRows(
                  Math.min(
                    2000,
                    Math.max(1, parseInt(e.target.value, 10) || 500)
                  )
                )
              }
              disabled={!enabled}
              inputProps={{ min: 1, max: 2000 }}
              sx={{ width: 120 }}
            />
            <Button
              variant='contained'
              startIcon={
                running ? (
                  <CircularProgress size={18} color='inherit' />
                ) : (
                  <PlayArrowIcon />
                )
              }
              onClick={() => void runQuery()}
              disabled={!enabled || running}
            >
              Run
            </Button>
          </Box>
          {queryError && (
            <Alert severity='error' sx={{ mt: 2 }}>
              {queryError}
            </Alert>
          )}
          {resultMeta && (
            <Typography variant='body2' color='text.secondary' sx={{ mt: 1 }}>
              {resultMeta}
            </Typography>
          )}
        </CardContent>
      </Card>

      {columns.length > 0 && (
        <TableContainer
          component={Paper}
          variant='outlined'
          sx={{ maxHeight: 560 }}
        >
          <Table size='small' stickyHeader>
            <TableHead>
              <TableRow>
                {columns.map(c => (
                  <TableCell
                    key={c}
                    sx={{
                      fontWeight: 700,
                      fontFamily: 'monospace',
                      fontSize: '0.75rem',
                    }}
                  >
                    {c}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((r, i) => (
                <TableRow key={i}>
                  {r.map((cell, j) => (
                    <TableCell
                      key={j}
                      sx={{
                        fontFamily: 'monospace',
                        fontSize: '0.75rem',
                        whiteSpace: 'pre-wrap',
                        maxWidth: 360,
                      }}
                    >
                      {cell === null || cell === undefined ? '' : String(cell)}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {truncated && columns.length > 0 && (
        <Alert severity='warning' sx={{ mt: 2 }}>
          Result limited by max rows; narrow the query or increase the cap (max
          2000).
        </Alert>
      )}
    </Box>
  );
}
