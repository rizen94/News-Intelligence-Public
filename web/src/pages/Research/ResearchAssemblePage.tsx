/**
 * Research Assemble — NL idea → LLM interpret → package via API.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Divider,
  FormControlLabel,
  Link,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import ScienceIcon from '@mui/icons-material/Science';
import { PageShell } from '@/components/ui/PageShell';
import { useDomainRoute } from '@/hooks/useDomainRoute';
import {
  researchAssembleApi,
  type IntakeBriefHighlight,
  type ResearchAssembleResult,
  type ResearchInterpretBrief,
} from '@/services/api/researchAssemble';

function errMessage(err: unknown): string {
  if (err && typeof err === 'object') {
    const ax = err as {
      code?: string;
      response?: { data?: { detail?: string | { msg?: string }[]; message?: string } };
      message?: string;
    };
    const detail = ax.response?.data?.detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
    const message = ax.response?.data?.message;
    if (typeof message === 'string' && message.trim()) return message;
    if (ax.code === 'ECONNABORTED' || /timeout/i.test(ax.message || '')) {
      return 'Request timed out — interpret/assemble can take up to ~3 minutes while the model runs.';
    }
    if (ax.message) return ax.message;
  }
  return 'Request failed';
}

function asText(value: unknown): string {
  if (value == null) return '';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (typeof value === 'object') {
    const o = value as Record<string, unknown>;
    for (const k of ['name', 'label', 'title', 'text', 'quote']) {
      const v = o[k];
      if (typeof v === 'string' && v.trim()) return v.trim();
    }
  }
  return '';
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    const one = asText(value);
    return one ? [one] : [];
  }
  const out: string[] = [];
  for (const item of value) {
    const s = asText(item);
    if (s) out.push(s);
  }
  return out;
}

function entityLabels(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const out: string[] = [];
  for (const item of value) {
    if (typeof item === 'string' && item.trim()) {
      out.push(item.trim());
      continue;
    }
    if (item && typeof item === 'object') {
      const o = item as Record<string, unknown>;
      const name = asText(o.name);
      if (!name) continue;
      const role = asText(o.role);
      out.push(role ? `${name} (${role})` : name);
    }
  }
  return out;
}

function asBrief(value: unknown): ResearchInterpretBrief | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const o = value as ResearchInterpretBrief;
  if (!o.working_title && !o.research_question && !o.search_queries) return null;
  return o;
}

function sectionLines(value: unknown): string[] {
  return asStringList(value);
}

export default function ResearchAssemblePage() {
  const { domain } = useDomainRoute();
  const navigate = useNavigate();
  const [idea, setIdea] = useState('');
  const [interpretOn, setInterpretOn] = useState(true);
  const [runSpine, setRunSpine] = useState(false);
  const [busy, setBusy] = useState<'idle' | 'interpret' | 'assemble'>('idle');
  const [error, setError] = useState<string | null>(null);
  const [brief, setBrief] = useState<ResearchInterpretBrief | null>(null);
  const [result, setResult] = useState<ResearchAssembleResult | null>(null);
  const [highlights, setHighlights] = useState<IntakeBriefHighlight[]>([]);
  const [intakeLoading, setIntakeLoading] = useState(false);

  const loadIntake = useCallback(async () => {
    if (!domain) return;
    setIntakeLoading(true);
    try {
      const briefRes = await researchAssembleApi.intakeBrief({
        domain_key: domain,
        hours: 72,
        limit: 10,
      });
      const raw = briefRes.highlights;
      setHighlights(Array.isArray(raw) ? raw : []);
    } catch {
      setHighlights([]);
    } finally {
      setIntakeLoading(false);
    }
  }, [domain]);

  useEffect(() => {
    void loadIntake();
  }, [loadIntake]);

  const onInterpret = async () => {
    if (!idea.trim() || !domain) return;
    setBusy('interpret');
    setError(null);
    setResult(null);
    try {
      const data = await researchAssembleApi.interpret({
        idea: idea.trim(),
        domain_key: domain,
      });
      if (data.ok === false) {
        setError(data.error || 'Interpret failed');
        return;
      }
      setBrief(data);
    } catch (e) {
      setError(errMessage(e));
    } finally {
      setBusy('idle');
    }
  };

  const onAssemble = async () => {
    if (!idea.trim() || !domain) return;
    setBusy('assemble');
    setError(null);
    try {
      const data = await researchAssembleApi.assemble({
        idea: idea.trim(),
        domain_key: domain,
        interpret: interpretOn,
        run_spine: runSpine,
      });
      if (data.ok === false) {
        setError(data.error || 'Assemble failed');
        return;
      }
      // Normalize before setState so a stale/partial payload cannot crash render.
      const normalized: ResearchAssembleResult = {
        ...data,
        working_title: asText(data.working_title),
        research_question: asText(data.research_question),
        status: asText(data.status) || data.status,
        draft_sections: Object.fromEntries(
          Object.entries(data.draft_sections || {}).map(([k, v]) => [k, asStringList(v)])
        ),
      };
      setResult(normalized);
      const fromAssemble = asBrief(data.interpret);
      if (fromAssemble) setBrief(fromAssemble);

      // Hand off to the readable draft (story reader), else package workspace.
      const storyId = normalized.story_id != null ? Number(normalized.story_id) : NaN;
      const pkgId = normalized.package_id != null ? Number(normalized.package_id) : NaN;
      if (Number.isFinite(storyId) && storyId > 0) {
        navigate(`/${domain}/editor/stories/${storyId}`, {
          replace: false,
          state: { fromAssemble: true, package_id: pkgId || null },
        });
        return;
      }
      if (Number.isFinite(pkgId) && pkgId > 0) {
        navigate(`/${domain}/editor/packages/${pkgId}`, {
          replace: false,
          state: { fromAssemble: true, brief_md: asText(normalized.brief_md) },
        });
      }
    } catch (e) {
      setError(errMessage(e));
    } finally {
      setBusy('idle');
    }
  };

  const storyHref =
    result?.story_id != null ? `/${domain}/editor/stories/${result.story_id}` : null;
  const packageHref = result?.package_id
    ? `/${domain}/editor/packages/${result.package_id}`
    : null;

  const entityChips = entityLabels(brief?.entities);
  const queryLines = asStringList(brief?.search_queries);
  const assumptionLines = asStringList(brief?.key_assumptions);

  // Belt-and-suspenders: never let API objects reach MUI Chip/Typography.
  const safeEntityChips = entityChips.map(s => String(s));
  const safeQueryLines = queryLines.map(s => String(s));
  const safeAssumptionLines = assumptionLines.map(s => String(s));

  return (
    <PageShell
      title='Research assemble'
      subtitle='Idea → package + readable draft. After Assemble succeeds you land on the draft story reader; use Open package for sources and publish.'
    >
      <Stack spacing={2.5} sx={{ maxWidth: 900 }}>
        {error && (
          <Alert severity='error' onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Paper variant='outlined' sx={{ p: 2.5 }}>
          <Typography variant='subtitle2' color='text.secondary' sx={{ mb: 1 }}>
            Domain: {domain}
          </Typography>
          <TextField
            label='Story idea'
            placeholder='e.g. China selling Treasuries and buying gold — what does that mean for USD?'
            value={idea}
            onChange={e => setIdea(e.target.value)}
            fullWidth
            multiline
            minRows={3}
            disabled={busy !== 'idle'}
          />
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={1}
            sx={{ mt: 1.5 }}
            alignItems='flex-start'
          >
            <FormControlLabel
              control={
                <Checkbox
                  checked={interpretOn}
                  onChange={e => setInterpretOn(e.target.checked)}
                  disabled={busy !== 'idle'}
                />
              }
              label='LLM interpret before retrieve'
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={runSpine}
                  onChange={e => setRunSpine(e.target.checked)}
                  disabled={busy !== 'idle'}
                />
              }
              label='Run spine (slower)'
            />
          </Stack>
          <Stack direction='row' spacing={1.5} sx={{ mt: 2 }} flexWrap='wrap' useFlexGap>
            <Button
              variant='outlined'
              startIcon={
                busy === 'interpret' ? <CircularProgress size={16} /> : <AutoFixHighIcon />
              }
              onClick={() => void onInterpret()}
              disabled={busy !== 'idle' || idea.trim().length < 8}
            >
              Interpret only
            </Button>
            <Button
              variant='contained'
              startIcon={
                busy === 'assemble' ? (
                  <CircularProgress size={16} color='inherit' />
                ) : (
                  <ScienceIcon />
                )
              }
              onClick={() => void onAssemble()}
              disabled={busy !== 'idle' || idea.trim().length < 8}
            >
              Assemble package
            </Button>
          </Stack>
          {busy !== 'idle' && (
            <Typography variant='body2' color='text.secondary' sx={{ mt: 1.5 }}>
              {busy === 'interpret'
                ? 'Asking the model to expand the idea…'
                : 'Assembling package (retrieve + attach)… this can take up to a few minutes.'}
            </Typography>
          )}
        </Paper>

        <Paper variant='outlined' sx={{ p: 2.5 }}>
          <Stack direction='row' justifyContent='space-between' alignItems='center' sx={{ mb: 1 }}>
            <Typography variant='h6'>72h intake seeds</Typography>
            <Button size='small' onClick={() => void loadIntake()} disabled={intakeLoading}>
              Refresh
            </Button>
          </Stack>
          <Typography variant='body2' color='text.secondary' sx={{ mb: 1.5 }}>
            Click a highlight to seed the idea box.
          </Typography>
          {intakeLoading && <CircularProgress size={20} />}
          {!intakeLoading && highlights.length === 0 && (
            <Typography variant='body2' color='text.secondary'>
              No highlights for this domain window.
            </Typography>
          )}
          <Stack direction='row' flexWrap='wrap' useFlexGap spacing={1}>
            {highlights.map(h => {
              const label =
                asText(h.title) ||
                asText(h.assemble_hint) ||
                `${asText(h.kind) || 'item'}: ${asText(h.id)}`;
              return (
                <Chip
                  key={`${asText(h.kind) || 'h'}-${asText(h.id)}-${label.slice(0, 40)}`}
                  label={label}
                  onClick={() =>
                    setIdea(asText(h.assemble_hint) || asText(h.title) || `Research: ${label}`)
                  }
                  variant='outlined'
                  sx={{ maxWidth: '100%' }}
                />
              );
            })}
          </Stack>
        </Paper>

        {brief && (
          <Paper variant='outlined' sx={{ p: 2.5 }}>
            <Typography variant='h6' sx={{ mb: 1 }}>
              Interpret brief
            </Typography>
            <Typography variant='subtitle1' fontWeight={600}>
              {asText(brief.working_title) || 'Untitled'}
            </Typography>
            <Typography variant='body1' sx={{ mt: 1, mb: 1.5 }}>
              {asText(brief.research_question)}
            </Typography>
            {brief.source ? (
              <Typography variant='caption' color='text.secondary' display='block' sx={{ mb: 1 }}>
                Source: {asText(brief.source)}
              </Typography>
            ) : null}
            <Typography variant='caption' color='text.secondary'>
              Entities
            </Typography>
            <Stack direction='row' flexWrap='wrap' useFlexGap spacing={0.75} sx={{ mb: 1.5, mt: 0.5 }}>
              {safeEntityChips.map(e => (
                <Chip key={e} size='small' label={e} />
              ))}
            </Stack>
            <Typography variant='caption' color='text.secondary'>
              Search queries
            </Typography>
            <Box component='ul' sx={{ mt: 0.5, pl: 2.5, mb: 1 }}>
              {safeQueryLines.map(q => (
                <li key={q}>
                  <Typography variant='body2'>{q}</Typography>
                </li>
              ))}
            </Box>
            {safeAssumptionLines.length > 0 && (
              <>
                <Typography variant='caption' color='text.secondary'>
                  Assumptions
                </Typography>
                <Box component='ul' sx={{ mt: 0.5, pl: 2.5, mb: 0 }}>
                  {safeAssumptionLines.map(a => (
                    <li key={a}>
                      <Typography variant='body2'>{a}</Typography>
                    </li>
                  ))}
                </Box>
              </>
            )}
          </Paper>
        )}

        {result && (
          <Paper variant='outlined' sx={{ p: 2.5 }}>
            <Typography variant='h6' sx={{ mb: 1 }}>
              Package
            </Typography>
            <Typography variant='subtitle1' fontWeight={600}>
              {asText(result.working_title) || 'Draft package'}
            </Typography>
            {asText(result.research_question) ? (
              <Typography variant='body2' color='text.secondary' sx={{ mt: 0.5, mb: 1 }}>
                {asText(result.research_question)}
              </Typography>
            ) : null}
            <Stack direction='row' spacing={2} sx={{ mt: 1, mb: 1.5 }} flexWrap='wrap' useFlexGap>
              {storyHref && (
                <Link component={RouterLink} to={storyHref}>
                  Open readable draft
                </Link>
              )}
              {packageHref && (
                <Link component={RouterLink} to={packageHref}>
                  Open package (sources / publish)
                </Link>
              )}
            </Stack>
            <Stack direction='row' flexWrap='wrap' useFlexGap spacing={1} sx={{ mb: 1.5 }}>
              <Chip size='small' label={`Members: ${result.member_count ?? 0}`} />
              <Chip size='small' label={`Claimish: ${result.claimish_count ?? 0}`} />
              {result.status && (
                <Chip size='small' variant='outlined' label={asText(result.status)} />
              )}
              {result.package_id != null && (
                <Chip size='small' variant='outlined' label={`#${result.package_id}`} />
              )}
            </Stack>
            <Divider sx={{ my: 1.5 }} />
            <Typography variant='subtitle2' sx={{ mb: 1 }}>
              Draft sections
            </Typography>
            {Object.keys(result.draft_sections || {}).length === 0 && (
              <Typography variant='body2' color='text.secondary'>
                No draft sections returned.
              </Typography>
            )}
            {Object.entries(result.draft_sections || {}).map(([key, text]) => {
              const lines = sectionLines(text);
              return (
                <Box key={key} sx={{ mb: 2 }}>
                  <Typography
                    variant='caption'
                    color='text.secondary'
                    sx={{ textTransform: 'uppercase' }}
                  >
                    {key.replace(/_/g, ' ')}
                  </Typography>
                  {lines.length === 0 ? (
                    <Typography variant='body2' sx={{ mt: 0.5 }}>
                      —
                    </Typography>
                  ) : (
                    <Box component='ul' sx={{ mt: 0.5, pl: 2.5, mb: 0 }}>
                      {lines.map((line, idx) => (
                        <li key={`${key}-${idx}-${line.slice(0, 48)}`}>
                          <Typography variant='body2'>{line}</Typography>
                        </li>
                      ))}
                    </Box>
                  )}
                </Box>
              );
            })}
          </Paper>
        )}
      </Stack>
    </PageShell>
  );
}
