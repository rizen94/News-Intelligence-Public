/**
 * Finance Analysis — Query input, date range, source toggles, progress stepper
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  TextField,
  Stepper,
  Step,
  StepLabel,
  Alert,
  CircularProgress,
  Paper,
  Typography,
  FormGroup,
  FormControlLabel,
  Checkbox,
} from '@mui/material';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import apiService from '../../services/apiService';
import { format, subMonths } from 'date-fns';

const PHASES = ['Planning', 'Data Collection', 'Synthesis', 'Verification', 'Revision', 'Complete'];

function getTopicFromSources(sources: Record<string, boolean>): string {
  const { gold, edgar, fred } = sources;
  if (fred && !gold && !edgar) return 'fred';
  if (edgar && !gold && !fred) return 'edgar';
  if (gold && edgar && !fred) return 'all';
  return 'gold';
}

export default function FinancialAnalysis() {
  const navigate = useNavigate();
  const { domain, getDomainPath } = useDomainRoute();
  const [query, setQuery] = useState('');
  const [sources, setSources] = useState({ gold: true, edgar: false, fred: false });
  const [dateStart, setDateStart] = useState('');
  const [dateEnd, setDateEnd] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const topic = getTopicFromSources(sources);
  const hasSource = sources.gold || sources.edgar || sources.fred;
  const handleSourceChange = (k: keyof typeof sources) => (_: unknown, checked: boolean) => {
    setSources((s) => {
      const next = { ...s, [k]: checked };
      if (!next.gold && !next.edgar && !next.fred) next.gold = true;
      return next;
    });
  };

  const handleSubmit = async () => {
    if (!query.trim()) return;
    setError(null);
    setSubmitting(true);
    try {
      const hasDateRange = Boolean(dateStart || dateEnd);
      const date_range = hasDateRange
        ? {
            start: dateStart || format(subMonths(new Date(dateEnd || Date.now()), 1), 'yyyy-MM-dd'),
            end: dateEnd || format(new Date(), 'yyyy-MM-dd'),
          }
        : undefined;
      const res = await apiService.submitFinanceAnalysis(query, { topic, date_range, wait: false }, domain);
      const id = res?.data?.task_id;
      if (id) {
        const path = getDomainPath(`/analysis/${id}`);
        navigate(path);
      } else {
        setError('No task ID returned');
      }
    } catch (err: any) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      if (status === 503 && detail) {
        setError(`Backend: ${detail}`);
      } else if (status != null && detail) {
        setError(`Request failed (${status}): ${typeof detail === 'string' ? detail : String(detail)}`);
      } else if (err?.message === 'Network Error' || !err?.response) {
        setError('Cannot reach API. Check that the backend is running and the API URL is correct.');
      } else {
        setError(err?.message || 'Failed to submit analysis');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box sx={{ p: 3, maxWidth: 720, mx: 'auto' }}>
      <Typography variant="h5" gutterBottom>
        Financial Analysis
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Ask a question about gold, commodities, or market data. The system will gather evidence and generate a cited analysis.
      </Typography>

      <Paper sx={{ p: 2, mb: 2 }}>
        <TextField
          fullWidth
          multiline
          rows={3}
          label="Analysis query"
          placeholder="What is the recent gold price trend? How has it changed over the past month?"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          sx={{ mb: 2 }}
        />
        <FormGroup row sx={{ mb: 2 }}>
          <FormControlLabel
            control={<Checkbox checked={sources.gold} onChange={handleSourceChange('gold')} size="small" />}
            label="Gold"
          />
          <FormControlLabel
            control={<Checkbox checked={sources.edgar} onChange={handleSourceChange('edgar')} size="small" />}
            label="EDGAR"
          />
          <FormControlLabel
            control={<Checkbox checked={sources.fred} onChange={handleSourceChange('fred')} size="small" />}
            label="FRED"
          />
        </FormGroup>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
          <TextField
            size="small"
            type="date"
            label="From"
            value={dateStart}
            onChange={(e) => setDateStart(e.target.value)}
            InputLabelProps={{ shrink: true }}
            sx={{ width: 140 }}
          />
          <TextField
            size="small"
            type="date"
            label="To"
            value={dateEnd}
            onChange={(e) => setDateEnd(e.target.value)}
            InputLabelProps={{ shrink: true }}
            sx={{ width: 140 }}
          />
          <Button
            variant="contained"
            onClick={handleSubmit}
            disabled={!query.trim() || !hasSource || submitting}
          >
            {submitting ? 'Submitting…' : 'Submit Analysis'}
          </Button>
        </Box>
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Paper sx={{ p: 2 }}>
        <Stepper activeStep={0} sx={{ mb: 2 }}>
          {PHASES.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>
        <Typography variant="body2" color="text.secondary">
          Submit a query to start. You will be redirected to the result page where progress is shown.
        </Typography>
      </Paper>
    </Box>
  );
}
