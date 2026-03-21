/**
 * Task Trace Viewer — spans, decisions, LLM interactions for a finance orchestrator task
 */
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableRow,
  TableHead,
  CircularProgress,
  Button,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { financeAnalysisApi } from '../../services/api/financeAnalysis';
import { getCurrentDomain } from '../../utils/domainHelper';

export default function TaskTraceViewer() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const domain = getCurrentDomain();
  const [trace, setTrace] = useState<{
    spans: Array<Record<string, unknown>>;
    decisions: Array<Record<string, unknown>>;
    llm_interactions: Array<Record<string, unknown>>;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!taskId) return;
    financeAnalysisApi
      .getTaskTrace(taskId, domain)
      .then(
        (res: {
          success?: boolean;
          spans?: [];
          decisions?: [];
          llm_interactions?: [];
        }) => {
          if (res?.success) {
            setTrace({
              spans: res.spans || [],
              decisions: res.decisions || [],
              llm_interactions: res.llm_interactions || [],
            });
          } else {
            setError('Trace not found');
          }
        }
      )
      .catch(e => setError(e?.message || 'Failed to load trace'))
      .finally(() => setLoading(false));
  }, [taskId, domain]);

  if (loading) {
    return (
      <Box
        p={3}
        display='flex'
        justifyContent='center'
        alignItems='center'
        minHeight={200}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (error || !trace) {
    return (
      <Box p={3}>
        <Typography color='error'>{error || 'Trace not found'}</Typography>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate(-1)}
          sx={{ mt: 2 }}
        >
          Back
        </Button>
      </Box>
    );
  }

  return (
    <Box p={3}>
      <Button
        startIcon={<ArrowBackIcon />}
        onClick={() => navigate(-1)}
        sx={{ mb: 2 }}
      >
        Back
      </Button>
      <Typography variant='h5' gutterBottom>
        Task Trace: {taskId}
      </Typography>
      <Box display='flex' gap={1} mb={2}>
        <Chip
          label={`${trace.spans.length} spans`}
          color='primary'
          size='small'
        />
        <Chip
          label={`${trace.decisions.length} decisions`}
          color='secondary'
          size='small'
        />
        <Chip
          label={`${trace.llm_interactions.length} LLM calls`}
          color='info'
          size='small'
        />
      </Box>

      {trace.spans.length > 0 && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant='h6' gutterBottom>
              Spans
            </Typography>
            <Table size='small'>
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Duration</TableCell>
                  <TableCell>Status</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {trace.spans.map((s, i) => (
                  <TableRow key={i}>
                    <TableCell>{String(s.name || '-')}</TableCell>
                    <TableCell>{String(s.span_type || '-')}</TableCell>
                    <TableCell>
                      {Number(s.duration_ms ?? 0).toFixed(0)} ms
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={String(s.status || 'unknown')}
                        size='small'
                        color={s.status === 'success' ? 'success' : 'error'}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {trace.decisions.length > 0 && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant='h6' gutterBottom>
              Orchestrator Decisions
            </Typography>
            {trace.decisions.map((d, i) => (
              <Accordion key={i}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography>
                    {String(d.decision_point)} → {String(d.chosen_option)}
                  </Typography>
                  {d.outcome_status && (
                    <Chip
                      label={String(d.outcome_status)}
                      size='small'
                      sx={{ ml: 1 }}
                      color={
                        d.outcome_status === 'success' ? 'success' : 'default'
                      }
                    />
                  )}
                </AccordionSummary>
                <AccordionDetails>
                  <Typography variant='body2' color='text.secondary'>
                    {String(d.rationale)}
                  </Typography>
                  {d.available_options && (
                    <Typography
                      variant='caption'
                      display='block'
                      sx={{ mt: 1 }}
                    >
                      Options: {(d.available_options as string[]).join(', ')}
                    </Typography>
                  )}
                </AccordionDetails>
              </Accordion>
            ))}
          </CardContent>
        </Card>
      )}

      {trace.llm_interactions.length > 0 && (
        <Card>
          <CardContent>
            <Typography variant='h6' gutterBottom>
              LLM Interactions
            </Typography>
            <Table size='small'>
              <TableHead>
                <TableRow>
                  <TableCell>Phase</TableCell>
                  <TableCell>Model</TableCell>
                  <TableCell>Latency</TableCell>
                  <TableCell>Tokens (in/out)</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {trace.llm_interactions.map((llm, i) => (
                  <TableRow key={i}>
                    <TableCell>{String(llm.phase || '-')}</TableCell>
                    <TableCell>{String(llm.model || '-')}</TableCell>
                    <TableCell>
                      {Number(llm.latency_ms ?? 0).toFixed(0)} ms
                    </TableCell>
                    <TableCell>
                      {String(llm.input_token_count ?? '-')} /{' '}
                      {String(llm.output_token_count ?? '-')}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {trace.spans.length === 0 &&
        trace.decisions.length === 0 &&
        trace.llm_interactions.length === 0 && (
          <Typography color='text.secondary'>
            No trace data for this task yet.
          </Typography>
        )}
    </Box>
  );
}
