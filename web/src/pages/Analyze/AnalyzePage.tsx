/**
 * Analyze — Trend analysis, network graphs, reports (placeholder).
 *
 * Note: For the finance domain, `/finance/analyze` now redirects to the
 * dedicated finance analysis flow at `/finance/analysis`.
 */
import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, Typography, Box } from '@mui/material';
import { useDomainRoute } from '../../hooks/useDomainRoute';

export default function AnalyzePage() {
  const navigate = useNavigate();
  const { domain, getDomainPath } = useDomainRoute();

  useEffect(() => {
    if (domain === 'finance') {
      // Keep URL semantics consistent: /finance/analyze → /finance/analysis
      const target = getDomainPath('/analysis');
      navigate(target, { replace: true });
    }
  }, [domain, getDomainPath, navigate]);

  // For non-finance domains, show the existing placeholder.
  if (domain === 'finance') {
    return null;
  }

  return (
    <Box>
      <Typography variant='h5' sx={{ mb: 2, fontWeight: 600 }}>
        Analyze
      </Typography>
      <Card>
        <CardContent>
          <Typography color='text.secondary'>
            Trend analysis, network graphs, timeline builder, and report
            generator are planned for a future release.
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
}
