/**
 * Evidence Explorer — Browse evidence index with DataGrid
 */
import React, { useEffect, useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import apiService from '../../services/apiService';
import type { EvidenceIndexEntry } from '../../types/finance';

export default function EvidenceExplorer() {
  const { domain } = useDomainRoute();
  const [entries, setEntries] = useState<EvidenceIndexEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [source, setSource] = useState<string>('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!domain) return;
    setLoading(true);
    apiService
      .getFinanceEvidenceIndex({ source: source || undefined, limit: 100 }, domain)
      .then((res) => {
        const d = res?.data;
        setEntries(d?.entries || []);
        setTotal(d?.total ?? 0);
      })
      .catch(() => setEntries([]))
      .finally(() => setLoading(false));
  }, [domain, source]);

  const columns: GridColDef[] = [
    { field: 'ref_id', headerName: 'Ref ID', width: 100 },
    { field: 'source', headerName: 'Source', width: 120 },
    { field: 'identifier', headerName: 'Identifier', width: 120 },
    { field: 'value', headerName: 'Value', width: 100 },
    { field: 'unit', headerName: 'Unit', width: 80 },
    { field: 'date', headerName: 'Date', width: 110 },
    { field: 'context', headerName: 'Context', flex: 1 },
  ];

  const rows = entries.map((e, i) => ({
    id: i,
    ref_id: e.ref_id,
    source: e.source,
    identifier: e.identifier || '',
    value: e.value,
    unit: e.unit || '',
    date: e.date,
    context: e.context || '',
  }));

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        Evidence Explorer
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Browse verifiable facts from completed analysis and refresh tasks.
      </Typography>

      <FormControl size="small" sx={{ minWidth: 140, mb: 2 }}>
        <InputLabel>Filter by source</InputLabel>
        <Select
          value={source}
          label="Filter by source"
          onChange={(e) => setSource(e.target.value)}
        >
          <MenuItem value="">All</MenuItem>
          <MenuItem value="gold">Gold</MenuItem>
          <MenuItem value="fred">FRED</MenuItem>
          <MenuItem value="edgar_10k">EDGAR 10-K</MenuItem>
        </Select>
      </FormControl>

      <Paper sx={{ height: 400 }}>
        <DataGrid
          rows={rows}
          columns={columns}
          loading={loading}
          pageSizeOptions={[25, 50, 100]}
          initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
          disableRowSelectionOnClick
        />
      </Paper>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
        {total} total entries
      </Typography>
    </Box>
  );
}
