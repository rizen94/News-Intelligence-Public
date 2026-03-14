/**
 * Finance Analysis — Query input, date range, source toggles, progress stepper.
 * Shows recent analyses so you can reopen a task after reload or navigation.
 */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  TextField,
  Stepper,
  Step,
  StepLabel,
  Alert,
  Paper,
  Typography,
  FormGroup,
  FormControlLabel,
  Checkbox,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableRow,
  TableHead,
} from '@mui/material';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import apiService from '../../services/apiService';
import { format, subMonths } from 'date-fns';

const PHASES = ['Planning', 'Data Collection', 'Synthesis', 'Verification', 'Revision', 'Complete'];

function getTopicFromSources(sources: Record<string, boolean>): string {
  const { gold, silver, platinum, edgar, fred } = sources;
  if (platinum && !gold && !silver && !edgar && !fred) return 'platinum';
  if (silver && !gold && !platinum && !edgar && !fred) return 'silver';
  if (fred && !gold && !edgar && !silver && !platinum) return 'fred';
  if (edgar && !gold && !fred && !silver && !platinum) return 'edgar';
  if (gold && edgar && !fred) return 'all';
  if (platinum) return 'platinum';
  if (silver) return 'silver';
  return 'gold';
}

type TaskSummary = {
  task_id: string;
  task_type: string;
  status: string;
  phase: string;
  created_at: string;
  updated_at: string;
};

type ResearchTopicSummary = {
  id: number;
  name: string;
  query: string;
  topic: string;
  last_refined_at: string | null;
  last_refined_task_id: string | null;
  updated_at: string;
};

export default function FinancialAnalysis() {
  const navigate = useNavigate();
  const { domain, getDomainPath } = useDomainRoute();
  const [query, setQuery] = useState('');
  const [sources, setSources] = useState({ gold: true, silver: false, platinum: false, edgar: false, fred: false });
  const [dateStart, setDateStart] = useState(() => format(subMonths(new Date(), 24), 'yyyy-MM-dd'));
  const [dateEnd, setDateEnd] = useState(() => format(new Date(), 'yyyy-MM-dd'));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recentTasks, setRecentTasks] = useState<TaskSummary[]>([]);
  const [recentLoading, setRecentLoading] = useState(false);
  const [researchTopics, setResearchTopics] = useState<ResearchTopicSummary[]>([]);
  const [researchTopicsLoading, setResearchTopicsLoading] = useState(false);
  const [refiningId, setRefiningId] = useState<number | null>(null);

  useEffect(() => {
    if (!domain) return;
    setRecentLoading(true);
    apiService
      .listFinanceTasks({ task_type: 'analysis', limit: 15 }, domain)
      .then((res: { data?: { tasks?: TaskSummary[] } }) => {
        setRecentTasks(res?.data?.tasks ?? []);
      })
      .catch(() => setRecentTasks([]))
      .finally(() => setRecentLoading(false));
  }, [domain]);

  useEffect(() => {
    if (!domain) return;
    setResearchTopicsLoading(true);
    apiService
      .listFinanceResearchTopics({ limit: 30 }, domain)
      .then((res: { data?: { topics?: ResearchTopicSummary[] } }) => {
        setResearchTopics(res?.data?.topics ?? []);
      })
      .catch(() => setResearchTopics([]))
      .finally(() => setResearchTopicsLoading(false));
  }, [domain]);

  const topic = getTopicFromSources(sources);
  const hasSource = sources.gold || sources.silver || sources.platinum || sources.edgar || sources.fred;

  const handleRefineTopic = async (topicId: number) => {
    if (!domain) return;
    setRefiningId(topicId);
    try {
      const res = await apiService.refineFinanceResearchTopic(topicId, domain) as { data?: { task_id?: string } };
      const taskId = res?.data?.task_id;
      if (taskId) navigate(getDomainPath(`/analysis/${taskId}`));
    } catch {
      setRefiningId(null);
    } finally {
      setRefiningId(null);
    }
  };

  const handleSourceChange = (k: keyof typeof sources) => (_: unknown, checked: boolean) => {
    setSources((s) => {
      const next = { ...s, [k]: checked };
      if (!next.gold && !next.silver && !next.platinum && !next.edgar && !next.fred) next.gold = true;
      return next;
    });
  };

  const handleSubmit = async () => {
    if (!query.trim()) return;
    setError(null);
    setSubmitting(true);
    try {
      // Always send date range: default last 2 years so all sources (RSS, news, Wikipedia, SEC, FRED) are consulted
      const endDate = dateEnd || format(new Date(), 'yyyy-MM-dd');
      const startDate = dateStart || format(subMonths(new Date(endDate), 24), 'yyyy-MM-dd');
      const date_range = { start: startDate, end: endDate };
      const res = await apiService.submitFinanceAnalysis(query, { topic, date_range, wait: false }, domain);
      const id = (res as { data?: { task_id?: string } })?.data?.task_id;
      if (id) {
        setRecentTasks((prev) => [{ task_id: id, task_type: 'analysis', status: 'queued', phase: 'planning', created_at: new Date().toISOString(), updated_at: new Date().toISOString() }, ...prev.slice(0, 14)]);
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
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Pick a commodity and ask your question. Every analysis uses all sources: RSS news, historic news, Wikipedia, SEC filings, and economic data (default: last 2 years). You can narrow the period below if you want.
      </Typography>
      <Alert severity="info" sx={{ mb: 2 }}>
        After you run an analysis, you’re taken to the result page. When it’s ready, you’ll see the full report with sources. You can return here anytime and open any run from <strong>Your recent analyses</strong> below.
      </Alert>

      <Paper sx={{ p: 2, mb: 2 }}>
        <TextField
          fullWidth
          multiline
          rows={3}
          label="Your question"
          placeholder="e.g. What drove the platinum price drop in 2023? How has gold performed over the past year?"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          sx={{ mb: 2 }}
        />
        <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>
          Commodity (all sources are used every time)
        </Typography>
        <FormGroup row sx={{ mb: 2 }}>
          <FormControlLabel
            control={<Checkbox checked={sources.gold} onChange={handleSourceChange('gold')} size="small" />}
            label="Gold"
          />
          <FormControlLabel
            control={<Checkbox checked={sources.silver} onChange={handleSourceChange('silver')} size="small" />}
            label="Silver"
          />
          <FormControlLabel
            control={<Checkbox checked={sources.platinum} onChange={handleSourceChange('platinum')} size="small" />}
            label="Platinum"
          />
          <FormControlLabel
            control={<Checkbox checked={sources.edgar} onChange={handleSourceChange('edgar')} size="small" />}
            label="SEC filings"
          />
          <FormControlLabel
            control={<Checkbox checked={sources.fred} onChange={handleSourceChange('fred')} size="small" />}
            label="Economic data"
          />
        </FormGroup>
        <Typography variant="caption" display="block" color="text.secondary" sx={{ mb: 1 }}>
          Optional: narrow the time period (default is last 2 years).
        </Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center', mb: 2 }}>
          <TextField
            size="small"
            type="date"
            label="Start date"
            value={dateStart}
            onChange={(e) => setDateStart(e.target.value)}
            InputLabelProps={{ shrink: true }}
            sx={{ width: 160 }}
          />
          <TextField
            size="small"
            type="date"
            label="End date"
            value={dateEnd}
            onChange={(e) => setDateEnd(e.target.value)}
            InputLabelProps={{ shrink: true }}
            sx={{ width: 160 }}
          />
        </Box>

        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={!query.trim() || !hasSource || submitting}
        >
          {submitting ? 'Running…' : 'Run analysis'}
        </Button>
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Paper sx={{ p: 2, mb: 2 }}>
        <Stepper activeStep={0} sx={{ mb: 2 }}>
          {PHASES.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>
        <Typography variant="body2" color="text.secondary">
          Click &quot;Run analysis&quot; to start. You’ll be taken to the result page where progress is shown.
        </Typography>
      </Paper>

      <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>
        Research topics
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Topics saved from analyses. Use <strong>Refine</strong> to re-run research and update with new data.
      </Typography>
      <Paper sx={{ overflow: 'hidden', mb: 2 }}>
        {researchTopicsLoading ? (
          <Box sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">Loading…</Typography>
          </Box>
        ) : researchTopics.length === 0 ? (
          <Box sx={{ p: 2 }}>
            <Typography variant="body2" color="text.secondary">
              No research topics yet. Run an analysis, then use &quot;Save as topic&quot; on the result page.
            </Typography>
          </Box>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Query</TableCell>
                <TableCell>Last refined</TableCell>
                <TableCell align="right">Action</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {researchTopics.map((t) => (
                <TableRow key={t.id}>
                  <TableCell sx={{ fontWeight: 500 }}>{t.name}</TableCell>
                  <TableCell sx={{ color: 'text.secondary', fontSize: '0.875rem', maxWidth: 280 }} title={t.query}>
                    {t.query.length > 60 ? `${t.query.slice(0, 60)}…` : t.query}
                  </TableCell>
                  <TableCell sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>
                    {t.last_refined_at ? format(new Date(t.last_refined_at), 'MMM d, yyyy') : '—'}
                  </TableCell>
                  <TableCell align="right">
                    <Button
                      size="small"
                      disabled={refiningId === t.id}
                      onClick={() => handleRefineTopic(t.id)}
                    >
                      {refiningId === t.id ? 'Starting…' : 'Refine'}
                    </Button>
                    {t.last_refined_task_id && (
                      <Button
                        size="small"
                        sx={{ ml: 0.5 }}
                        onClick={() => navigate(getDomainPath(`/analysis/${t.last_refined_task_id}`))}
                      >
                        View result
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Paper>

      <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>
        Your recent analyses
      </Typography>
      <Paper sx={{ overflow: 'hidden' }}>
        {recentLoading ? (
          <Box sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">Loading…</Typography>
          </Box>
        ) : recentTasks.length === 0 ? (
          <Box sx={{ p: 2 }}>
            <Typography variant="body2" color="text.secondary">No analyses yet. Run one using the form above.</Typography>
          </Box>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>When</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Action</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {recentTasks.map((t) => (
                <TableRow key={t.task_id}>
                  <TableCell sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>
                    {t.created_at ? format(new Date(t.created_at), 'MMM d, yyyy · h:mm a') : '—'}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={t.status === 'complete' ? 'Done' : t.status === 'failed' ? 'Failed' : t.phase || t.status}
                      size="small"
                      color={t.status === 'complete' ? 'success' : t.status === 'failed' ? 'error' : 'default'}
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell align="right">
                    <Button
                      size="small"
                      onClick={() => navigate(getDomainPath(`/analysis/${t.task_id}`))}
                    >
                      View result
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Paper>
    </Box>
  );
}
