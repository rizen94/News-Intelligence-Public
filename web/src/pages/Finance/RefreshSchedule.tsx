/**
 * Refresh Schedule — Scheduled refreshes, task queue, manual triggers
 */
import React, { useEffect, useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import apiService from '../../services/apiService';

export default function RefreshSchedule() {
  const { domain } = useDomainRoute();
  const [schedule, setSchedule] = useState<{ tasks: any[] }>({ tasks: [] });
  const [triggerSource, setTriggerSource] = useState<string>('gold');
  const [triggering, setTriggering] = useState(false);

  useEffect(() => {
    if (!domain) return;
    apiService.getFinanceRefreshSchedule(domain).then((res) => {
      setSchedule(res?.data || { tasks: [] });
    });
  }, [domain]);

  const handleTrigger = async () => {
    if (!domain) return;
    setTriggering(true);
    try {
      await apiService.triggerFinanceRefresh(
        triggerSource as 'gold' | 'edgar' | 'fred',
        {},
        domain
      );
    } finally {
      setTriggering(false);
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        Refresh Schedule
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Scheduled task runs and manual refresh triggers.
      </Typography>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" gutterBottom>
          Manual trigger
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel>Source</InputLabel>
            <Select
              value={triggerSource}
              label="Source"
              onChange={(e) => setTriggerSource(e.target.value)}
            >
              <MenuItem value="gold">Gold</MenuItem>
              <MenuItem value="edgar">EDGAR</MenuItem>
              <MenuItem value="fred">FRED</MenuItem>
            </Select>
          </FormControl>
          <Button
            variant="contained"
            onClick={handleTrigger}
            disabled={triggering}
          >
            {triggering ? 'Running…' : 'Trigger refresh'}
          </Button>
        </Box>
      </Paper>

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Task</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Interval</TableCell>
              <TableCell>Last run</TableCell>
              <TableCell>Next run</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(schedule.tasks || []).map((t: any) => (
              <TableRow key={t.name}>
                <TableCell>{t.name}</TableCell>
                <TableCell>{t.task_type}</TableCell>
                <TableCell>{t.interval_hours}h</TableCell>
                <TableCell>{t.last_run || '—'}</TableCell>
                <TableCell>{t.next_run || '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
