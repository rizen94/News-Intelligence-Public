/**
 * Single package review — research/narrative rails, links, decisions, composer, audit.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Button,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
  List,
  ListItem,
  ListItemText,
  Grid,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { PageShell, UiCard, LoadingState } from '@/components/ui';
import { editorialApi } from '@/services/api/editorial';
import { unwrapData } from '@/services/api/editorialUnwrap';
import NewsStoryReader, { type NewsStoryLike } from '@/components/Editorial/NewsStoryReader';
import { statusLabel } from '@/utils/statusLabel';

type MemberFilter = 'active' | 'quarantined' | 'all';

export default function PackageDetailPage() {
  const { packageId, domain } = useParams<{ packageId: string; domain: string }>();
  const id = Number(packageId);
  const dk = domain || 'politics';
  const [pkg, setPkg] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [kind, setKind] = useState('unset');
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [storyId, setStoryId] = useState<number | null>(null);
  const [story, setStory] = useState<NewsStoryLike | null>(null);
  const [citeMsg, setCiteMsg] = useState<string | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [memberFilter, setMemberFilter] = useState<MemberFilter>('active');
  const [decisionModal, setDecisionModal] = useState('all');
  const [reworkTarget, setReworkTarget] = useState('research');
  const [audit, setAudit] = useState<Record<string, unknown> | null>(null);
  const bodyRef = useRef<HTMLTextAreaElement | null>(null);
  const bodyDirtyRef = useRef(false);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const res = await editorialApi.getPackage(id);
      const data = unwrapData<Record<string, unknown>>(res);
      setPkg(data);
      setKind(String(data?.presentation_kind || 'unset'));
      setTitle(String(data?.working_title || ''));
      const storiesRes = await editorialApi.listStories({ package_id: id, limit: 5 });
      const stories = unwrapData<{ stories?: Record<string, unknown>[] }>(storiesRes)?.stories || [];
      const preferred =
        stories.find(s => s.status === 'published') ||
        stories.find(s => s.status === 'draft') ||
        stories[0];
      if (preferred?.id) {
        const sid = Number(preferred.id);
        setStoryId(sid);
        const fullRes = await editorialApi.getStory(sid);
        const full = unwrapData<NewsStoryLike>(fullRes);
        setStory(full);
        if (!bodyDirtyRef.current) {
          if (full?.body_md) setBody(String(full.body_md));
          else if (String(data?.summary_stub || '').trim()) {
            setBody(String(data.summary_stub));
          }
          if (full?.title) setTitle(String(full.title));
        }
      } else {
        setStoryId(null);
        setStory(null);
        if (!bodyDirtyRef.current) {
          const stub = String(data?.summary_stub || '').trim();
          if (stub) setBody(stub);
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const members = (pkg?.members as Record<string, unknown>[]) || [];
  const filtered = useMemo(() => {
    if (memberFilter === 'all') return members;
    return members.filter(m => m.status === memberFilter);
  }, [members, memberFilter]);
  const research = filtered.filter(m => m.member_family === 'research');
  const narrative = filtered.filter(m => m.member_family === 'narrative');
  const activeCount = members.filter(m => m.status === 'active').length;
  const links = (pkg?.links as Record<string, unknown>[]) || [];
  const decisions = ((pkg?.decisions as Record<string, unknown>[]) || []).filter(
    d => decisionModal === 'all' || d.modal === decisionModal
  );
  const readiness = (pkg?.readiness as Record<string, unknown>) || {};

  const insertCite = (memberRowId: number) => {
    const marker = `[@m${memberRowId}]`;
    const el = bodyRef.current;
    setBody(prev => {
      let next: string;
      if (el && typeof el.selectionStart === 'number') {
        const start = el.selectionStart;
        const end = el.selectionEnd;
        const padL = start > 0 && !/\s$/.test(prev.slice(0, start)) ? ' ' : '';
        const padR = end < prev.length && !/^\s/.test(prev.slice(end)) ? ' ' : '';
        next = `${prev.slice(0, start)}${padL}${marker}${padR}${prev.slice(end)}`;
        requestAnimationFrame(() => {
          const pos = start + padL.length + marker.length;
          el.focus();
          el.setSelectionRange(pos, pos);
        });
      } else {
        next = `${prev}${prev && !prev.endsWith(' ') ? ' ' : ''}${marker}`;
        requestAnimationFrame(() => {
          if (!bodyRef.current) return;
          bodyRef.current.focus();
          const pos = bodyRef.current.value.length;
          bodyRef.current.setSelectionRange(pos, pos);
        });
      }
      return next;
    });
    bodyDirtyRef.current = true;
    setCiteMsg(`Inserted ${marker} into body — Save draft before Publish`);
  };

  const restoreMember = async (memberRowId: number) => {
    await editorialApi.setMemberStatus(id, memberRowId, {
      status: 'active',
      modal: 'editor',
      rationale: 'editor restore for citation',
    });
    setCiteMsg(`Restored member #${memberRowId} to active — Cite is available`);
    setMemberFilter('active');
    await load();
  };

  const renderMember = (m: Record<string, unknown>) => (
    <ListItem
      key={String(m.id)}
      sx={{ pr: 12, alignItems: 'flex-start' }}
      secondaryAction={
        m.status === 'active' ? (
          <Button
            size='small'
            type='button'
            onClick={e => {
              e.preventDefault();
              e.stopPropagation();
              insertCite(Number(m.id));
            }}
          >
            Cite
          </Button>
        ) : (
          <Stack direction='row' spacing={0.5} alignItems='center'>
            <Chip size='small' label={String(m.status)} color='warning' />
            <Button
              size='small'
              type='button'
              onClick={e => {
                e.preventDefault();
                e.stopPropagation();
                void restoreMember(Number(m.id));
              }}
            >
              Restore
            </Button>
          </Stack>
        )
      }
    >
      <ListItemText
        primary={String(m.display_label || `${m.member_type} #${m.member_id}`)}
        secondary={`#${m.id} · ${m.role} · ${m.status}`}
        primaryTypographyProps={{ noWrap: true, title: String(m.display_label || '') }}
      />
    </ListItem>
  );

  if (loading && !pkg) return <LoadingState />;
  if (!pkg) {
    return (
      <PageShell title='Package'>
        <Alert severity='error'>{error || 'Not found'}</Alert>
      </PageShell>
    );
  }

  return (
    <PageShell
      title={String(pkg.working_title || `Package ${id}`)}
      subtitle={`status=${statusLabel(String(pkg.status))} · domains=${((pkg.domain_keys as string[]) || []).join(', ')}${
        String(pkg.status) === 'closed_thin' ? ' · closed before publish (too thin)' : ''
      }`}
      breadcrumbs={[
        { label: 'Editor', to: `/${dk}/editor` },
        { label: `Package ${id}` },
      ]}
    >
      {error && (
        <Alert severity='error' sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {citeMsg && (
        <Alert severity='info' sx={{ mb: 2 }} onClose={() => setCiteMsg(null)}>
          {citeMsg}
        </Alert>
      )}
      {activeCount === 0 && (
        <Alert severity='warning' sx={{ mb: 2 }}>
          No active members — Cite is unavailable until you Restore a source (switch filter to All)
          or attach new evidence. Publish needs [@mMEMBER_ROW_ID] against an active member.
        </Alert>
      )}

      <Stack direction='row' spacing={1} sx={{ mb: 2 }} alignItems='center' flexWrap='wrap'>
        <FormControl size='small' sx={{ minWidth: 180 }}>
          <InputLabel>Presentation</InputLabel>
          <Select
            label='Presentation'
            value={kind}
            onChange={async e => {
              const v = e.target.value;
              setKind(v);
              await editorialApi.patchPackage(id, {
                presentation_kind: v,
                modal: 'editor',
              });
              await load();
            }}
          >
            <MenuItem value='unset'>unset</MenuItem>
            <MenuItem value='research_brief'>research_brief</MenuItem>
            <MenuItem value='event_narrative'>event_narrative</MenuItem>
            <MenuItem value='hybrid'>hybrid</MenuItem>
          </Select>
        </FormControl>
        <Chip label={`research: ${String(!!readiness.research_brief_ready)}`} size='small' />
        <Chip label={`narrative: ${String(!!readiness.event_narrative_ready)}`} size='small' />
        <Chip label={`hybrid: ${String(!!readiness.hybrid_ready)}`} size='small' />
        <Chip
          label={`cite coverage: ${String(readiness.citation_coverage ?? 0)}`}
          size='small'
        />
        <Chip
          label={`reduction_cleared: ${String(!!readiness.reduction_cleared)}`}
          size='small'
        />
        <Chip
          label={`quarantined: ${String(readiness.contested_or_quarantined_count ?? 0)}`}
          size='small'
        />
        <Chip label={`active members: ${activeCount}`} size='small' />
        {storyId ? (
          <Button
            component={RouterLink}
            to={`/${dk}/editor/stories/${storyId}`}
            size='small'
            variant='contained'
          >
            Open published story
          </Button>
        ) : null}
        <ToggleButtonGroup
          size='small'
          exclusive
          value={memberFilter}
          onChange={(_, v) => v && setMemberFilter(v)}
        >
          <ToggleButton value='active'>Active</ToggleButton>
          <ToggleButton value='quarantined'>Quarantined</ToggleButton>
          <ToggleButton value='all'>All</ToggleButton>
        </ToggleButtonGroup>
        <FormControl size='small' sx={{ minWidth: 140 }}>
          <InputLabel>Rework</InputLabel>
          <Select
            label='Rework'
            value={reworkTarget}
            onChange={e => setReworkTarget(e.target.value)}
          >
            <MenuItem value='research'>research</MenuItem>
            <MenuItem value='narrative'>narrative</MenuItem>
            <MenuItem value='reduction'>reduction</MenuItem>
          </Select>
        </FormControl>
        <Button
          size='small'
          variant='outlined'
          onClick={async () => {
            await editorialApi.rework(id, {
              target_modal: reworkTarget,
              note: `rework → ${reworkTarget}`,
            });
            setCiteMsg(`Rework requested → ${reworkTarget}`);
            await load();
          }}
        >
          Request rework
        </Button>
      </Stack>

      {story?.status === 'published' && story.body_md ? (
        <UiCard title='Published news story' sx={{ mb: 2 }}>
          <Stack direction='row' justifyContent='flex-end' sx={{ mb: 1 }}>
            <Button
              component={RouterLink}
              to={`/${dk}/editor/stories/${story.id}`}
              size='small'
            >
              Full page
            </Button>
          </Stack>
          <NewsStoryReader story={story} variant='compact' />
        </UiCard>
      ) : null}

      <Grid container spacing={2}>
        <Grid item xs={12} md={4}>
          <UiCard title='Research rail'>
            <List dense>
              {research.length === 0 ? (
                <ListItem>
                  <ListItemText
                    primary={
                      memberFilter === 'active'
                        ? 'No active research members'
                        : 'No research members in this filter'
                    }
                    secondary={
                      memberFilter === 'active'
                        ? 'Switch to All and Restore a source, then Cite'
                        : undefined
                    }
                  />
                </ListItem>
              ) : (
                research.map(m => renderMember(m))
              )}
            </List>
          </UiCard>
        </Grid>
        <Grid item xs={12} md={4}>
          <UiCard title='Narrative rail'>
            <List dense>
              {narrative.length === 0 ? (
                <ListItem>
                  <ListItemText
                    primary={
                      memberFilter === 'active'
                        ? 'No active narrative members'
                        : 'No narrative members in this filter'
                    }
                  />
                </ListItem>
              ) : (
                narrative.map(m => renderMember(m))
              )}
            </List>
          </UiCard>
        </Grid>
        <Grid item xs={12} md={4}>
          <UiCard title='Connections'>
            <List dense>
              {links.map(l => (
                <ListItem key={String(l.id)}>
                  <ListItemText
                    primary={`${l.link_type}: ${l.from_member_id} → ${l.to_member_id}`}
                    secondary={`${l.inference_stage} · ${l.status}`}
                  />
                </ListItem>
              ))}
            </List>
          </UiCard>
        </Grid>
        <Grid item xs={12} md={6}>
          <UiCard title='Decision log'>
            <FormControl size='small' sx={{ mb: 1, minWidth: 140 }}>
              <InputLabel>Modal</InputLabel>
              <Select
                label='Modal'
                value={decisionModal}
                onChange={e => setDecisionModal(e.target.value)}
              >
                <MenuItem value='all'>all</MenuItem>
                <MenuItem value='research'>research</MenuItem>
                <MenuItem value='narrative'>narrative</MenuItem>
                <MenuItem value='reduction'>reduction</MenuItem>
                <MenuItem value='editor'>editor</MenuItem>
              </Select>
            </FormControl>
            <List dense sx={{ maxHeight: 280, overflow: 'auto' }}>
              {decisions.map(d => (
                <ListItem key={String(d.id)}>
                  <ListItemText
                    primary={`${d.action} (${d.modal || '—'})`}
                    secondary={`${d.at} · ${d.rationale || ''}`}
                  />
                </ListItem>
              ))}
            </List>
          </UiCard>
        </Grid>
        <Grid item xs={12} md={6}>
          <Accordion
            defaultExpanded={story?.status !== 'published'}
            disableGutters
            sx={{ border: 1, borderColor: 'divider', borderRadius: 2, '&:before': { display: 'none' } }}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant='subtitle1' sx={{ fontWeight: 600 }}>
                {story?.status === 'published' ? 'Manuscript editor' : 'Composer'}
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant='body2' color='text.secondary' sx={{ mb: 1 }}>
                Save draft for manual edits. Publish assembles a detailed final report from
                linked package sources (with [@m] citations), then citation-gates and publishes.
              </Typography>
              <TextField
                size='small'
                fullWidth
                label='Story title'
                value={title}
                onChange={e => {
                  bodyDirtyRef.current = true;
                  setTitle(e.target.value);
                }}
                sx={{ mb: 1 }}
              />
              <TextField
                fullWidth
                multiline
                minRows={8}
                label='Body (markdown)'
                value={body}
                inputRef={bodyRef}
                onChange={e => {
                  bodyDirtyRef.current = true;
                  setBody(e.target.value);
                }}
                sx={{ mb: 1 }}
                InputProps={{
                  sx: { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 13 },
                }}
              />
              <Stack direction='row' spacing={1} flexWrap='wrap'>
                <Button
                  variant='outlined'
                  onClick={async () => {
                    const res = await editorialApi.draftStory({
                      package_id: id,
                      title,
                      body_md: body,
                      presentation_kind: kind,
                      story_id: storyId,
                    });
                    const data = unwrapData<{
                      story?: Record<string, unknown>;
                      citation_check?: Record<string, unknown>;
                    }>(res);
                    if (data?.story?.id) setStoryId(Number(data.story.id));
                    bodyDirtyRef.current = false;
                    setCiteMsg(
                      data?.citation_check?.ok
                        ? 'Draft saved; citations OK'
                        : `Draft saved with refusals: ${JSON.stringify(data?.citation_check?.refused || [])}`
                    );
                    await load();
                  }}
                >
                  Save draft
                </Button>
                <Button
                  variant='contained'
                  disabled={!storyId || publishing}
                  onClick={async () => {
                    if (!storyId) return;
                    setPublishing(true);
                    setCiteMsg('Assembling final report from linked sources…');
                    try {
                      const res = await editorialApi.publishStory(storyId);
                      const payload = (res as { data?: Record<string, unknown> })?.data;
                      const inner = unwrapData<Record<string, unknown>>(res);
                      if (payload?.success === false || inner?.blocked) {
                        const reason = String(inner?.block_reason || '');
                        const check = (inner?.citation_check || {}) as {
                          refused?: Array<{ reason?: string }>;
                        };
                        const reasons = (check.refused || [])
                          .map(r => r.reason)
                          .filter(Boolean)
                          .join(', ');
                        setCiteMsg(
                          reasons
                            ? `Publish blocked — ${reasons}`
                            : reason
                              ? `Publish blocked — ${reason}`
                              : 'Publish blocked — citation_refused / citation_gap'
                        );
                      } else {
                        const assemble = (inner?.assemble || {}) as {
                          body_len?: number;
                          used_fallback?: boolean;
                        };
                        setCiteMsg(
                          assemble?.body_len
                            ? `Published final report (${assemble.body_len} chars${
                                assemble.used_fallback ? ', extractive fallback' : ''
                              })`
                            : 'Published — open the news story reader above'
                        );
                      }
                      bodyDirtyRef.current = false;
                      await load();
                    } catch (e) {
                      setCiteMsg(
                        e instanceof Error ? e.message : 'Publish / assemble failed'
                      );
                    } finally {
                      setPublishing(false);
                    }
                  }}
                >
                  {publishing ? 'Assembling…' : 'Publish final report'}
                </Button>
                <Button
                  size='small'
                  disabled={!storyId}
                  onClick={async () => {
                    if (!storyId) return;
                    const res = await editorialApi.storyAudit(storyId);
                    setAudit(unwrapData<Record<string, unknown>>(res));
                  }}
                >
                  Load story audit
                </Button>
              </Stack>
              {audit ? (
                <Typography
                  component='pre'
                  variant='caption'
                  sx={{ mt: 1, maxHeight: 200, overflow: 'auto', display: 'block' }}
                >
                  {JSON.stringify(audit, null, 2)}
                </Typography>
              ) : null}
            </AccordionDetails>
          </Accordion>
        </Grid>
      </Grid>
    </PageShell>
  );
}
