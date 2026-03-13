import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
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
  Chip,
  CircularProgress,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  TablePagination,
} from '@mui/material';
import { useDomain } from '../../contexts/DomainContext';
import apiService from '../../services/apiService';

const EVENT_TYPES = [
  'all', 'legal_action', 'policy_decision', 'election', 'conflict',
  'economic_event', 'scientific_discovery', 'natural_disaster',
  'public_statement', 'investigation', 'legislation', 'court_ruling',
  'arrest', 'protest', 'agreement', 'appointment', 'resignation',
  'death', 'meeting', 'report_release', 'other',
];

const TYPE_COLORS: Record<string, 'error' | 'primary' | 'secondary' | 'success' | 'warning' | 'info' | 'default'> = {
  court_ruling: 'error',
  legal_action: 'error',
  investigation: 'warning',
  policy_decision: 'primary',
  legislation: 'primary',
  conflict: 'error',
  agreement: 'success',
  economic_event: 'info',
  election: 'secondary',
};

const Events: React.FC = () => {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const [events, setEvents] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [eventType, setEventType] = useState('all');
  const [ongoingOnly, setOngoingOnly] = useState(false);

  const loadEvents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = {
        limit: rowsPerPage,
        offset: page * rowsPerPage,
        ongoing_only: ongoingOnly,
      };
      if (eventType !== 'all') params.event_type = eventType;

      const result = await apiService.getDomainEvents(params);
      if (result?.success) {
        setEvents(result.data || []);
        setTotal(result.total || 0);
      } else {
        setError(result?.error || 'Failed to load events');
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [page, rowsPerPage, eventType, ongoingOnly, domain]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Extracted Events
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Discrete real-world events extracted from articles with temporal grounding.
      </Typography>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3, display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>Event Type</InputLabel>
          <Select
            value={eventType}
            label="Event Type"
            onChange={(e) => { setEventType(e.target.value); setPage(0); }}
          >
            {EVENT_TYPES.map(t => (
              <MenuItem key={t} value={t}>{t === 'all' ? 'All Types' : t.replace(/_/g, ' ')}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControlLabel
          control={<Switch checked={ongoingOnly} onChange={(_, v) => { setOngoingOnly(v); setPage(0); }} />}
          label="Ongoing only"
        />
        <Chip label={`${total} events`} color="primary" variant="outlined" />
      </Paper>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Date</TableCell>
                <TableCell>Title</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Location</TableCell>
                <TableCell align="center">Sources</TableCell>
                <TableCell align="center">Ongoing</TableCell>
                <TableCell>Storyline</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {events.map((evt) => (
                <TableRow
                  key={evt.id}
                  hover
                  sx={{ cursor: evt.storyline_id ? 'pointer' : 'default' }}
                  onClick={() => {
                    if (evt.storyline_id) {
                      navigate(`/${domain}/storylines/${evt.storyline_id}/timeline`);
                    }
                  }}
                >
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>
                    {evt.event_date || '—'}
                    {evt.date_precision && evt.date_precision !== 'exact' && evt.date_precision !== 'unknown' && (
                      <Typography variant="caption" display="block" color="text.disabled">
                        ~{evt.date_precision}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>{evt.title}</TableCell>
                  <TableCell>
                    <Chip
                      label={evt.event_type.replace(/_/g, ' ')}
                      size="small"
                      color={TYPE_COLORS[evt.event_type] || 'default'}
                    />
                  </TableCell>
                  <TableCell>{evt.location !== 'unknown' ? evt.location : '—'}</TableCell>
                  <TableCell align="center">{evt.source_count}</TableCell>
                  <TableCell align="center">{evt.is_ongoing ? '✓' : ''}</TableCell>
                  <TableCell>
                    {evt.storyline_id ? (
                      <Chip label={`#${evt.storyline_id}`} size="small" variant="outlined" />
                    ) : (
                      <Typography variant="caption" color="text.disabled">unlinked</Typography>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {events.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} align="center" sx={{ py: 4 }}>
                    <Typography color="text.secondary">No events found</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
          <TablePagination
            component="div"
            count={total}
            page={page}
            onPageChange={(_, p) => setPage(p)}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={(e) => { setRowsPerPage(parseInt(e.target.value, 10)); setPage(0); }}
            rowsPerPageOptions={[10, 25, 50, 100]}
          />
        </TableContainer>
      )}
    </Box>
  );
};

export default Events;
