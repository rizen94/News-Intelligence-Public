/**
 * Tracked Events list — Phase 4.4 context-centric.
 * Lists intelligence.tracked_events with optional event_type filter.
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
} from '@mui/material';
import Event as EventIcon from '@mui/icons-material/Event';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import { contextCentricApi, type TrackedEvent } from '../../services/api/contextCentric';
import Logger from '../../utils/logger';

const TrackedEvents: React.FC = () => {
  const { getDomainPath } = useDomainRoute();
  const [items, setItems] = useState<TrackedEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [eventType, setEventType] = useState<string>('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { event_type?: string; limit: number; offset: number } = {
        limit: rowsPerPage,
        offset: page * rowsPerPage,
      };
      if (eventType) params.event_type = eventType;
      const data = await contextCentricApi.getTrackedEvents(params);
      setItems(data.items);
    } catch (e) {
      Logger.apiError('Tracked events load failed', e as Error);
      setError((e as Error).message ?? 'Failed to load tracked events');
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [eventType, page, rowsPerPage]);

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
        <EventIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
        Tracked Events
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Events extracted from contexts (event_tracking task). Filter by type or view details with chronicles.
      </Typography>

      <Paper sx={{ mb: 2 }}>
        <Box sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel>Event type</InputLabel>
            <Select
              value={eventType}
              label="Event type"
              onChange={(e) => {
                setEventType(e.target.value);
                setPage(0);
              }}
            >
              <MenuItem value="">All types</MenuItem>
              <MenuItem value="election">Election</MenuItem>
              <MenuItem value="policy">Policy</MenuItem>
              <MenuItem value="market">Market</MenuItem>
              <MenuItem value="conference">Conference</MenuItem>
              <MenuItem value="other">Other</MenuItem>
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
                  <TableCell>Type</TableCell>
                  <TableCell>Start</TableCell>
                  <TableCell>Scope</TableCell>
                  <TableCell></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} align="center" sx={{ py: 4 }}>
                      No tracked events yet. Run event_tracking task to extract from contexts.
                    </TableCell>
                  </TableRow>
                ) : (
                  items.map((ev) => (
                    <TableRow key={ev.id} hover>
                      <TableCell>
                        <Typography variant="body2" fontWeight={500}>
                          {ev.event_name ?? `Event #${ev.id}`}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip label={ev.event_type ?? '—'} size="small" variant="outlined" />
                      </TableCell>
                      <TableCell>{ev.start_date ? new Date(ev.start_date).toLocaleDateString() : '—'}</TableCell>
                      <TableCell>{ev.geographic_scope ?? '—'}</TableCell>
                      <TableCell>
                        <Button
                          size="small"
                          component={Link}
                          to={getDomainPath(`/intelligence/tracked-events/${ev.id}`)}
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

export default TrackedEvents;
