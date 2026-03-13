/**
 * Finance Analysis Result — Polling view with progress stepper and cited output
 */
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Alert,
  CircularProgress,
  Paper,
  Typography,
  Stepper,
  Step,
  StepLabel,
  Chip,
  Tooltip,
  Drawer,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  IconButton,
  Button,
  Switch,
  FormControlLabel,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import TimelineIcon from '@mui/icons-material/Timeline';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import apiService from '../../services/apiService';
import type { FinancialAnalysisResult, EvidenceIndexEntry } from '../../types/finance';

const PHASE_ORDER = ['planning', 'fetching', 'synthesizing', 'verifying', 'revising', 'complete'];

function buildRefToIndex(provenance: EvidenceIndexEntry[]): Record<string, number> {
  const map: Record<string, number> = {};
  provenance.forEach((e, i) => {
    if (e.ref_id && !(e.ref_id in map)) map[e.ref_id] = i + 1;
  });
  return map;
}

function formatCitationText(entry: EvidenceIndexEntry): string {
  return `${entry.source}: ${String(entry.value)}${entry.unit ? ' ' + entry.unit : ''} (${entry.date})`;
}

const EVIDENCE_ID_PREFIX = 'evidence-';

function CitationMarker({
  refId,
  provenance,
  onScrollToEvidence,
  onHover,
  onLeave,
  children,
}: {
  refId: string;
  provenance: EvidenceIndexEntry[];
  onScrollToEvidence?: (refId: string) => void;
  onHover?: (refId: string) => void;
  onLeave?: () => void;
  children: React.ReactNode;
}) {
  const entry = provenance.find((e) => e.ref_id === refId);
  const title = entry ? formatCitationText(entry) : refId;
  const handleClick = () => {
    if (onScrollToEvidence) {
      onScrollToEvidence(refId);
    } else {
      const el = document.getElementById(`${EVIDENCE_ID_PREFIX}${refId}`);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  };
  return (
    <Tooltip title={title} placement="top" arrow>
      <sup
        onClick={handleClick}
        onKeyDown={(e) => e.key === 'Enter' && handleClick()}
        onMouseEnter={() => onHover?.(refId)}
        onMouseLeave={() => onLeave?.()}
        onFocus={() => onHover?.(refId)}
        onBlur={() => onLeave?.()}
        style={{
          cursor: 'pointer',
          color: 'var(--mui-palette-primary-main)',
          fontWeight: 600,
          marginLeft: 2,
        }}
        role="button"
        tabIndex={0}
        aria-label={`Citation ${refId}, click to scroll to evidence`}
      >
        [{children}]
      </sup>
    </Tooltip>
  );
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function AnalysisWithCitations({
  text,
  provenance,
  claims,
  claimHighlight,
  onScrollToEvidence,
  onCitationHover,
  onCitationLeave,
}: {
  text: string;
  provenance: EvidenceIndexEntry[];
  claims?: Array<{ claim_text: string; verdict: string }>;
  claimHighlight?: boolean;
  onScrollToEvidence?: (refId: string) => void;
  onCitationHover?: (refId: string) => void;
  onCitationLeave?: () => void;
}) {
  const refToIndex = buildRefToIndex(provenance);
  let processed = text.replace(/REF-(\d+)/gi, (m) => {
    const idx = refToIndex[m] ?? m;
    return `[${idx}](citation:${m})`;
  });
  if (claimHighlight && claims?.length) {
    for (const c of claims) {
      const escaped = escapeRegex(c.claim_text);
      if (escaped) {
        processed = processed.replace(new RegExp(escaped, 'g'), `[$&](claim:${c.verdict})`);
      }
    }
  }
  const verdictColor: Record<string, string> = {
    verified: 'rgba(46, 125, 50, 0.25)',
    unsupported: 'rgba(237, 108, 2, 0.25)',
    contradicted: 'rgba(211, 47, 47, 0.25)',
    fabricated: 'rgba(211, 47, 47, 0.35)',
  };
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({ href, children }) => {
          if (href?.startsWith('citation:')) {
            const refId = href.slice(9);
            return (
              <CitationMarker
                refId={refId}
                provenance={provenance}
                onScrollToEvidence={onScrollToEvidence}
                onHover={onCitationHover}
                onLeave={onCitationLeave}
              >
                {children}
              </CitationMarker>
            );
          }
          if (href?.startsWith('claim:')) {
            const verdict = href.slice(6);
            const bg = verdictColor[verdict] || 'transparent';
            return (
              <mark
                style={{
                  backgroundColor: bg,
                  padding: '0 2px',
                  borderRadius: 2,
                  textDecoration: verdict === 'verified' ? 'underline' : 'none',
                  textDecorationColor: verdict === 'verified' ? 'rgb(46, 125, 50)' : 'inherit',
                }}
              >
                {children}
              </mark>
            );
          }
          return <a href={href}>{children}</a>;
        },
      }}
    >
      {processed}
    </ReactMarkdown>
  );
}

function ConfidenceBadge({ score }: { score: number }) {
  const color = score >= 0.8 ? 'success' : score >= 0.5 ? 'warning' : 'error';
  return (
    <Chip
      label={`${(score * 100).toFixed(0)}% confidence`}
      color={color}
      size="small"
      sx={{ mr: 1 }}
    />
  );
}

function groupBySource(provenance: EvidenceIndexEntry[]): Record<string, EvidenceIndexEntry[]> {
  const out: Record<string, EvidenceIndexEntry[]> = {};
  for (const e of provenance) {
    const src = e.source || 'unknown';
    if (!out[src]) out[src] = [];
    out[src].push(e);
  }
  return out;
}

const DRAWER_WIDTH = 340;

export default function FinancialAnalysisResult() {
  const { taskId } = useParams<{ taskId: string }>();
  const { domain } = useDomainRoute();
  const navigate = useNavigate();
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up('md'));
  const [data, setData] = useState<FinancialAnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredRefId, setHoveredRefId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [claimHighlight, setClaimHighlight] = useState(true);
  const [ledgerEntries, setLedgerEntries] = useState<Array<{ source_id?: string; evidence_data?: { status?: string; error?: string }; created_at?: string }>>([]);

  useEffect(() => {
    if (!taskId || !domain) return;
    let cancelled = false;

    const poll = async () => {
      try {
        const [res, ledgerRes] = await Promise.all([
          apiService.getFinanceTaskResult(taskId, domain),
          apiService.getFinanceTaskLedger(taskId, domain).catch(() => ({ data: { entries: [] } })),
        ]);
        if (cancelled) return;
        const d = res?.data;
        if (d?.status) {
          setData({
            task_id: taskId,
            status: d.status.status,
            phase: d.status.phase,
            ...d.result,
          });
        }
        const entries = ledgerRes?.data?.entries || [];
        setLedgerEntries(entries);
        const st = d?.status?.status;
        if (st === 'complete' || st === 'failed') {
          setLoading(false);
          return;
        }
      } catch (err: any) {
        if (!cancelled) {
          const status = err?.response?.status;
          const detail = err?.response?.data?.detail;
          if (status === 503 && detail) {
            setError(`Backend: ${detail}`);
          } else if (status != null && detail) {
            setError(`Request failed (${status}): ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`);
          } else if (err?.message === 'Network Error' || !err?.response) {
            setError('Cannot reach API. Check that the backend is running and the API URL (e.g. proxy or VITE_API_URL) is correct.');
          } else {
            setError(err?.message || 'Failed to fetch result');
          }
          setLoading(false);
        }
        return;
      }
      setTimeout(poll, 2000);
    };

    poll();
    return () => {
      cancelled = true;
    };
  }, [taskId, domain]);

  const phaseIndex = data?.phase
    ? Math.max(0, PHASE_ORDER.indexOf(data.phase))
    : 0;
  const output = (data?.output || data) as Record<string, unknown> | undefined;
  const text = (output?.response ?? output?.analysis_text ?? '') as string;
  const confidence = data?.confidence ?? data?.confidence_score ?? 0;
  const provenance = data?.provenance || data?.evidence_index || [];
  const verification = data?.verification as
    | { claims?: Array<{ claim_text: string; verdict: string }> }
    | undefined;
  const claims = verification?.claims;

  const handleScrollToEvidence = (refId: string) => {
    if (!isDesktop) setDrawerOpen(true);
    setTimeout(() => {
      const el = document.getElementById(`${EVIDENCE_ID_PREFIX}${refId}`);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, isDesktop ? 0 : 150);
  };

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  const evidenceBySource = groupBySource(provenance);

  const evidenceDrawer = provenance.length > 0 && (
    <Drawer
      variant={isDesktop ? 'permanent' : 'temporary'}
      anchor="right"
      open={isDesktop || drawerOpen}
      onClose={() => setDrawerOpen(false)}
      sx={{
        '& .MuiDrawer-paper': {
          width: DRAWER_WIDTH,
          mt: { xs: 7, md: 8 },
          height: { xs: 'calc(100% - 56px)', md: 'calc(100% - 64px)' },
          boxSizing: 'border-box',
        },
      }}
    >
      <Box sx={{ p: 2, overflow: 'auto', height: '100%' }}>
        <Typography variant="subtitle1" fontWeight={600} gutterBottom>
          Evidence ({provenance.length})
        </Typography>
        {Object.entries(evidenceBySource).map(([source, entries]) => (
          <Accordion key={source} defaultExpanded disableGutters sx={{ boxShadow: 'none', '&:before': { display: 'none' } }}>
            <AccordionSummary sx={{ minHeight: 40, '& .MuiAccordionSummary-content': { my: 0.5 } }}>
              <Typography variant="body2" fontWeight={500}>
                {source}
              </Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ pt: 0 }}>
              {entries.map((e, i) => (
                <Typography
                  key={e.ref_id || i}
                  id={e.ref_id ? `${EVIDENCE_ID_PREFIX}${e.ref_id}` : undefined}
                  variant="body2"
                  sx={{
                    mb: 0.75,
                    px: 0.5,
                    py: 0.5,
                    borderRadius: 1,
                    scrollMarginTop: 8,
                    scrollMarginBottom: 8,
                    bgcolor: hoveredRefId === e.ref_id ? 'action.hover' : 'transparent',
                    transition: 'background-color 0.15s',
                  }}
                >
                  {e.ref_id}: {String(e.value)} {e.unit || ''} ({e.date})
                </Typography>
              ))}
            </AccordionDetails>
          </Accordion>
        ))}
      </Box>
    </Drawer>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100%' }}>
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          maxWidth: 900,
          mx: 'auto',
          width: '100%',
          mr: isDesktop && provenance.length > 0 ? `${DRAWER_WIDTH}px` : 0,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <Typography variant="h5" gutterBottom sx={{ mb: 0 }}>
            Analysis Result
          </Typography>
          {!isDesktop && provenance.length > 0 && (
            <IconButton
              color="primary"
              onClick={() => setDrawerOpen(true)}
              aria-label="Open evidence sidebar"
              size="small"
            >
              <MenuBookIcon />
            </IconButton>
          )}
        </Box>
        {taskId && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <Typography variant="body2" color="text.secondary">
              Task: {taskId}
            </Typography>
            <Button
              size="small"
              startIcon={<TimelineIcon />}
              onClick={() => navigate(`/${domain}/trace/${taskId}`)}
            >
              View Trace
            </Button>
          </Box>
        )}

        {loading && (
          <Box sx={{ mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: ledgerEntries.length ? 2 : 0 }}>
              <CircularProgress size={24} />
              <Typography variant="body2">Processing…</Typography>
            </Box>
            {ledgerEntries.length > 0 && (
              <Paper variant="outlined" sx={{ p: 1.5, maxHeight: 120, overflow: 'auto' }}>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                  Activity
                </Typography>
                {ledgerEntries.slice(0, 10).map((e, i) => (
                  <Typography key={i} variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem', py: 0.25 }}>
                    {e.source_id || '?'}: {e.evidence_data?.status || '—'} {e.created_at ? new Date(e.created_at).toLocaleTimeString() : ''}
                  </Typography>
                ))}
              </Paper>
            )}
          </Box>
        )}

        <Stepper activeStep={phaseIndex} sx={{ mb: 3 }}>
          {PHASE_ORDER.map((p) => (
            <Step key={p}>
              <StepLabel>{p.charAt(0).toUpperCase() + p.slice(1)}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {!loading && data?.status === 'complete' && (
          <>
            <Box sx={{ mb: 2 }}>
              <ConfidenceBadge score={confidence} />
              {confidence >= 0.8 && (
                <Alert severity="success" sx={{ mt: 1 }}>
                  Analysis complete. High confidence.
                </Alert>
              )}
              {confidence >= 0.5 && confidence < 0.8 && (
                <Alert severity="warning" sx={{ mt: 1 }}>
                  Partial confidence. Some claims may need verification.
                </Alert>
              )}
              {confidence < 0.5 && (
                <Alert severity="error" sx={{ mt: 1 }}>
                  Low confidence. Review evidence carefully.
                </Alert>
              )}
            </Box>

            {text && (
              <Paper sx={{ p: 2, mb: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Analysis
                  </Typography>
                  {claims && claims.length > 0 && (
                    <FormControlLabel
                      control={
                        <Switch
                          checked={claimHighlight}
                          onChange={(_, v) => setClaimHighlight(v)}
                          size="small"
                        />
                      }
                      label="Highlight claims"
                    />
                  )}
                </Box>
                <AnalysisWithCitations
                  text={text}
                  provenance={provenance}
                  claims={claims}
                  claimHighlight={claimHighlight}
                  onScrollToEvidence={handleScrollToEvidence}
                  onCitationHover={setHoveredRefId}
                  onCitationLeave={() => setHoveredRefId(null)}
                />
              </Paper>
            )}
          </>
        )}

        {!loading && data?.status === 'failed' && (
          <Alert severity="error">
            Analysis failed. {data?.warnings?.join(' ') || 'Unknown error.'}
          </Alert>
        )}
      </Box>

      {evidenceDrawer}
    </Box>
  );
}
