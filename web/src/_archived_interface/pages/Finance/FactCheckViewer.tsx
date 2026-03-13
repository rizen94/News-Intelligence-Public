/**
 * Fact Check Viewer — Verification history, claim-to-evidence mapping
 */
import React, { useEffect, useState } from 'react';
import { Box, Paper, Typography, Chip } from '@mui/material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import apiService from '../../services/apiService';

export default function FactCheckViewer() {
  const { domain } = useDomainRoute();
  const [verifications, setVerifications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!domain) return;
    setLoading(true);
    apiService
      .getFinanceVerificationHistory({ limit: 50 }, domain)
      .then((res) => {
        setVerifications(res?.data?.verifications || []);
      })
      .catch(() => setVerifications([]))
      .finally(() => setLoading(false));
  }, [domain]);

  const columns: GridColDef[] = [
    { field: 'task_id', headerName: 'Task', width: 140 },
    { field: 'query', headerName: 'Query', flex: 1 },
    { field: 'total_claims', headerName: 'Claims', width: 80 },
    { field: 'verified', headerName: 'Verified', width: 80 },
    { field: 'unsupported', headerName: 'Unsupported', width: 100 },
    { field: 'fabricated', headerName: 'Fabricated', width: 90 },
    { field: 'updated_at', headerName: 'Updated', width: 170 },
  ];

  const rows = verifications.map((v, i) => ({
    id: i,
    task_id: v.task_id,
    query: (v.query || '').slice(0, 50) + (v.query?.length > 50 ? '…' : ''),
    total_claims: v.total_claims ?? 0,
    verified: v.verified ?? 0,
    unsupported: v.unsupported ?? 0,
    fabricated: v.fabricated ?? 0,
    updated_at: v.updated_at || '',
  }));

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        Fact Check History
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Verification results from completed analysis tasks.
      </Typography>

      <Paper sx={{ height: 400 }}>
        <DataGrid
          rows={rows}
          columns={columns}
          loading={loading}
          pageSizeOptions={[25, 50]}
          initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
          disableRowSelectionOnClick
        />
      </Paper>
    </Box>
  );
}
