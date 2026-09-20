/**
 * Modal workspace — Research / Narrative / Reduction (v11).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Link as RouterLink, useParams, useSearchParams } from 'react-router-dom';
import {
  Button,
  Stack,
  TextField,
  Typography,
  Chip,
  List,
  ListItem,
  ListItemText,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import { PageShell, UiCard, LoadingState } from '@/components/ui';
import { editorialApi, type ModalKey } from '@/services/api/editorial';
import { unwrapData } from '@/services/api/editorialUnwrap';
import { useDomain } from '@/contexts/DomainContext';
import { statusLabel } from '@/utils/statusLabel';

const MODAL_META: Record<ModalKey, { title: string; subtitle: string }> = {
  research: {
    title: 'Research',
    subtitle:
      'Chase claims into facts, connect literature/appraisals, then route to Reduction (or Editor when both passes settle)',
  },
  narrative: {
    title: 'Narrative',
    subtitle:
      'Assemble events, places, and actors onto the package; route to Reduction (or Editor when both passes settle)',
  },
  reduction: {
    title: 'Reduction',
    subtitle:
      'Uncouple unrelated, weak, or geo/entity-mismatched members from this package (sources kept), then route back for another research/narrative round',
  },
  editor: {
    title: 'Editor',
    subtitle: 'Longform news stories',
  },
};

const LINK_TYPES = [
  'supports',
  'contradicts',
  'same_event',
  'near_in_time',
  'same_place',
  'movement',
  'caused_by',
  'corroborates',
  'derived_from',
];

/** Status that places a package in this modal's operator queue. */
const QUEUE_STATUS: Partial<Record<ModalKey, string>> = {
  research: 'in_research',
  narrative: 'in_narrative',
  reduction: 'in_reduction',
};

export default function ModalWorkspacePage({ modal }: { modal: ModalKey }) {
  const { domain: routeDomain } = useParams<{ domain: string }>();
  const { domain: domainKey } = useDomain();
  const dk = routeDomain || domainKey;
  const meta = MODAL_META[modal];
  const queueStatus = QUEUE_STATUS[modal];
  const [params, setParams] = useSearchParams();
  const packageIdParam = params.get('package');
  const [packageId, setPackageId] = useState<number | null>(
    packageIdParam ? Number(packageIdParam) : null
  );
  const [q, setQ] = useState('');
  const [hits, setHits] = useState<Record<string, unknown>[]>([]);
  const [pkg, setPkg] = useState<Record<string, unknown> | null>(null);
  const [queue, setQueue] = useState<Record<string, unknown>[]>([]);
  const [thinClosed, setThinClosed] = useState<Record<string, unknown>[]>([]);
  const [handoffs, setHandoffs] = useState<Record<string, unknown>[]>([]);
  const [queueLoading, setQueueLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState('');
  const [fromMember, setFromMember] = useState('');
  const [toMember, setToMember] = useState('');
  const [linkType, setLinkType] = useState('supports');
  const [reductionRunning, setReductionRunning] = useState(false);
  const [reductionResult, setReductionResult] = useState<Record<string, unknown> | null>(
    null
  );
  const [narrativeRunning, setNarrativeRunning] = useState(false);
  const [narrativeResult, setNarrativeResult] = useState<Record<string, unknown> | null>(
    null
  );
  const [researchRunning, setResearchRunning] = useState(false);
  const [researchResult, setResearchResult] = useState<Record<string, unknown> | null>(
    null
  );

  const loadPackage = useCallback(async (id: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await editorialApi.getPackage(id);
      setPkg(unwrapData<Record<string, unknown>>(res));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load package');
      setPkg(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadQueue = useCallback(async () => {
    if (!queueStatus) return;
    setQueueLoading(true);
    try {
      const [p, thin, h] = await Promise.all([
        editorialApi.listPackages({ status: queueStatus, limit: 40 }),
        editorialApi.listPackages({ status: 'closed_thin', limit: 20 }),
        editorialApi.listHandoffs({ target_modal: modal, status: 'open' }),
      ]);
      setQueue(unwrapData<{ packages?: Record<string, unknown>[] }>(p)?.packages || []);
      setThinClosed(
        unwrapData<{ packages?: Record<string, unknown>[] }>(thin)?.packages || []
      );
      setHandoffs(unwrapData<{ handoffs?: Record<string, unknown>[] }>(h)?.handoffs || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load queue');
    } finally {
      setQueueLoading(false);
    }
  }, [queueStatus, modal]);

  useEffect(() => {
    if (packageId) loadPackage(packageId);
  }, [packageId, loadPackage]);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  const openPackage = (id: number) => {
    setPackageId(id);
    setParams({ package: String(id) });
  };

  const createPackage = async () => {
    setLoading(true);
    setError(null);
    try {
      const queueStatusForModal =
        modal === 'research'
          ? 'in_research'
          : modal === 'narrative'
            ? 'in_narrative'
            : modal === 'reduction'
              ? 'in_reduction'
              : 'draft';
      const res = await editorialApi.createPackage({
        working_title: `${meta.title} package`,
        primary_modal: modal,
        domain_keys: [dk],
        status: queueStatusForModal,
      });
      const data = unwrapData<{ id?: number }>(res);
      const id = Number(data?.id);
      if (!id) throw new Error('No package id returned');
      setPackageId(id);
      setParams({ package: String(id) });
      await loadPackage(id);
      await loadQueue();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Create failed');
    } finally {
      setLoading(false);
    }
  };

  const runSearch = async () => {
    if (q.trim().length < 2) return;
    setLoading(true);
    setError(null);
    try {
      const res = await editorialApi.search({ modal, q: q.trim() });
      const data = unwrapData<{ hits?: Record<string, unknown>[] }>(res);
      setHits(Array.isArray(data?.hits) ? data.hits : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  };

  const attachHit = async (hit: Record<string, unknown>) => {
    if (!packageId) {
      setError('Create or open a package first');
      return;
    }
    setLoading(true);
    try {
      await editorialApi.attach(packageId, { modal, hits: [hit] });
      await loadPackage(packageId);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Attach failed');
    } finally {
      setLoading(false);
    }
  };

  const members = (pkg?.members as Record<string, unknown>[]) || [];
  const links = (pkg?.links as Record<string, unknown>[]) || [];
  const activeMembers = members.filter(m => m.status === 'active');

  return (
    <PageShell
      title={meta.title}
      subtitle={meta.subtitle}
      breadcrumbs={[{ label: 'Desk' }, { label: meta.title }]}
    >
      {error && (
        <Alert severity='error' sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      <Stack direction='row' spacing={1} sx={{ mb: 2 }} alignItems='center' flexWrap='wrap'>
        <Button variant='contained' onClick={createPackage} disabled={loading}>
          New package
        </Button>
        <TextField
          size='small'
          label='Package ID'
          value={packageId ?? ''}
          onChange={e => {
            const v = e.target.value.trim();
            setPackageId(v ? Number(v) : null);
            if (v) setParams({ package: v });
          }}
          sx={{ width: 120 }}
        />
        {packageId ? (
          <Button
            component={RouterLink}
            to={`/${dk}/editor/packages/${packageId}`}
            size='small'
          >
            Open in Editor
          </Button>
        ) : null}
        {pkg ? (
          <Chip
            label={`status: ${String(pkg.status)}`}
            size='small'
            color={String(pkg.status) === 'closed_thin' ? 'warning' : 'default'}
          />
        ) : null}
        {queueStatus ? (
          <Button size='small' variant='text' onClick={() => void loadQueue()} disabled={queueLoading}>
            Refresh queue
          </Button>
        ) : null}
      </Stack>

      {queueStatus ? (
        <UiCard title={`${meta.title} queue (${queue.length})`} sx={{ mb: 2 }}>
          {queueLoading && !queue.length ? <LoadingState /> : null}
          <List dense>
            {queue.map(row => {
              const id = Number(row.id);
              const selected = packageId === id;
              return (
                <ListItem
                  key={String(id)}
                  selected={selected}
                  secondaryAction={
                    <Button size='small' onClick={() => openPackage(id)}>
                      {selected ? 'Working' : 'Open'}
                    </Button>
                  }
                >
                  <ListItemText
                    primary={String(row.working_title || `Package ${id}`)}
                    secondary={
                      <Stack direction='row' spacing={1} component='span' alignItems='center'>
                        <Chip size='small' label={`#${id}`} />
                        <Chip
                          size='small'
                          label={String(row.status)}
                          color={
                            String(row.status) === 'closed_thin' ? 'warning' : 'default'
                          }
                        />
                        {Array.isArray(row.domain_keys) && row.domain_keys.length ? (
                          <Chip
                            size='small'
                            variant='outlined'
                            label={(row.domain_keys as string[]).join(', ')}
                          />
                        ) : null}
                        {row.presentation_kind ? (
                          <Chip
                            size='small'
                            variant='outlined'
                            label={String(row.presentation_kind)}
                          />
                        ) : null}
                        {row.updated_at ? (
                          <Typography variant='caption' color='text.secondary' component='span'>
                            {String(row.updated_at)}
                          </Typography>
                        ) : null}
                      </Stack>
                    }
                  />
                </ListItem>
              );
            })}
            {!queue.length && !queueLoading ? (
              <Typography color='text.secondary' sx={{ p: 2 }}>
                No packages in {meta.title} queue
              </Typography>
            ) : null}
          </List>
          {(() => {
            const queuedIds = new Set(queue.map(r => Number(r.id)));
            const extra = handoffs.filter(h => {
              const pid = Number(h.package_id);
              return pid > 0 && !queuedIds.has(pid);
            });
            if (!extra.length) return null;
            return (
              <>
                <Typography variant='subtitle2' sx={{ mt: 1, mb: 0.5 }}>
                  Open handoffs (not yet in status queue)
                </Typography>
                <List dense>
                  {extra.map(h => {
                    const pid = Number(h.package_id);
                    return (
                      <ListItem
                        key={String(h.id)}
                        secondaryAction={
                          <Button size='small' onClick={() => openPackage(pid)}>
                            Open
                          </Button>
                        }
                      >
                        <ListItemText
                          primary={`${h.reason_code} · ${h.working_title || `package ${pid}`}`}
                          secondary={`${h.source_modal} → ${modal} · ${h.package_status || '—'}`}
                        />
                      </ListItem>
                    );
                  })}
                </List>
              </>
            );
          })()}
        </UiCard>
      ) : null}

      {queueStatus && thinClosed.length > 0 ? (
        <UiCard
          title={`Thin closed (${thinClosed.length}) — not in ${meta.title} queue`}
          sx={{ mb: 2 }}
        >
          <Typography variant='body2' color='text.secondary' sx={{ mb: 1, px: 1 }}>
            These packages were closed before publish because the evidence was too thin. They are not in the active queue.
          </Typography>
          <List dense>
            {thinClosed.map(row => {
              const id = Number(row.id);
              const selected = packageId === id;
              return (
                <ListItem
                  key={`thin-${id}`}
                  selected={selected}
                  secondaryAction={
                    <Button size='small' onClick={() => openPackage(id)}>
                      {selected ? 'Working' : 'Open'}
                    </Button>
                  }
                >
                  <ListItemText
                    primary={String(row.working_title || `Package ${id}`)}
                    secondary={
                      <Stack direction='row' spacing={1} component='span' alignItems='center'>
                        <Chip size='small' label={`#${id}`} />
                        <Chip size='small' color='warning' label={statusLabel('closed_thin')} />
                        {Array.isArray(row.domain_keys) && row.domain_keys.length ? (
                          <Chip
                            size='small'
                            variant='outlined'
                            label={(row.domain_keys as string[]).join(', ')}
                          />
                        ) : null}
                      </Stack>
                    }
                  />
                </ListItem>
              );
            })}
          </List>
        </UiCard>
      ) : null}

      <UiCard title='Cross-domain search' sx={{ mb: 2 }}>
        <Stack direction='row' spacing={1} sx={{ mb: 1 }}>
          <TextField
            size='small'
            fullWidth
            label='Search'
            value={q}
            onChange={e => setQ(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') runSearch();
            }}
          />
          <Button variant='outlined' onClick={runSearch} disabled={loading}>
            Search
          </Button>
        </Stack>
        {loading && !hits.length ? <LoadingState /> : null}
        <List dense>
          {hits.map(hit => (
            <ListItem
              key={`${hit.member_type}-${hit.member_id}-${hit.role}`}
              secondaryAction={
                <Button size='small' onClick={() => attachHit(hit)}>
                  Attach
                </Button>
              }
            >
              <ListItemText
                primary={String(hit.label || '')}
                secondary={`${hit.member_family}/${hit.member_type} · ${hit.domain_key || '—'}`}
              />
            </ListItem>
          ))}
        </List>
      </UiCard>

      {pkg ? (
        <>
          <UiCard title={`Package members (${members.length})`} sx={{ mb: 2 }}>
            <List dense>
              {members.map(m => (
                <ListItem
                  key={String(m.id)}
                  secondaryAction={
                    modal === 'reduction' && m.status === 'active' ? (
                      <Stack direction='row' spacing={0.5}>
                        <Button
                          size='small'
                          color='warning'
                          onClick={async () => {
                            await editorialApi.setMemberStatus(packageId!, Number(m.id), {
                              status: 'quarantined',
                              rationale: note || 'reduction quarantine',
                            });
                            await loadPackage(packageId!);
                          }}
                        >
                          Quarantine
                        </Button>
                        <Button
                          size='small'
                          color='error'
                          onClick={async () => {
                            await editorialApi.setMemberStatus(packageId!, Number(m.id), {
                              status: 'removed',
                              rationale: note || 'uncouple from package',
                            });
                            await loadPackage(packageId!);
                          }}
                        >
                          Uncouple
                        </Button>
                      </Stack>
                    ) : (
                      <Chip size='small' label={String(m.status)} />
                    )
                  }
                >
                  <ListItemText
                    primary={String(m.display_label || `${m.member_type} #${m.member_id}`)}
                    secondary={`#${m.id} · ${m.member_family}/${m.member_type} · ${m.role} · ${m.domain_key || ''}`}
                  />
                </ListItem>
              ))}
            </List>

            {(modal === 'research' || modal === 'narrative') && activeMembers.length >= 2 ? (
              <Stack direction='row' spacing={1} sx={{ mt: 2 }} alignItems='center' flexWrap='wrap'>
                <FormControl size='small' sx={{ minWidth: 120 }}>
                  <InputLabel>From</InputLabel>
                  <Select
                    label='From'
                    value={fromMember}
                    onChange={e => setFromMember(e.target.value)}
                  >
                    {activeMembers.map(m => (
                      <MenuItem key={String(m.id)} value={String(m.id)}>
                        #{String(m.id)} {String(m.display_label || m.member_type).slice(0, 40)}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControl size='small' sx={{ minWidth: 120 }}>
                  <InputLabel>To</InputLabel>
                  <Select
                    label='To'
                    value={toMember}
                    onChange={e => setToMember(e.target.value)}
                  >
                    {activeMembers.map(m => (
                      <MenuItem key={String(m.id)} value={String(m.id)}>
                        #{String(m.id)} {String(m.display_label || m.member_type).slice(0, 40)}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControl size='small' sx={{ minWidth: 140 }}>
                  <InputLabel>Link</InputLabel>
                  <Select
                    label='Link'
                    value={linkType}
                    onChange={e => setLinkType(e.target.value)}
                  >
                    {LINK_TYPES.map(t => (
                      <MenuItem key={t} value={t}>
                        {t}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <Button
                  variant='outlined'
                  disabled={!fromMember || !toMember || fromMember === toMember}
                  onClick={async () => {
                    await editorialApi.addLink(packageId!, {
                      from_member_id: Number(fromMember),
                      to_member_id: Number(toMember),
                      link_type: linkType,
                      modal,
                    });
                    await loadPackage(packageId!);
                  }}
                >
                  Add link
                </Button>
              </Stack>
            ) : null}

            {modal === 'research' ? (
              <Stack spacing={1} sx={{ mt: 1 }}>
                {pkg?.readiness ? (
                  <Stack direction='row' spacing={1} flexWrap='wrap'>
                    <Chip
                      size='small'
                      color={
                        (pkg.readiness as Record<string, unknown>).research_brief_ready
                          ? 'success'
                          : 'default'
                      }
                      label={`research_brief_ready=${String(
                        Boolean(
                          (pkg.readiness as Record<string, unknown>).research_brief_ready
                        )
                      )}`}
                    />
                    <Chip
                      size='small'
                      color={
                        (pkg.readiness as Record<string, unknown>).hybrid_ready
                          ? 'success'
                          : 'default'
                      }
                      label={`hybrid_ready=${String(
                        Boolean((pkg.readiness as Record<string, unknown>).hybrid_ready)
                      )}`}
                    />
                  </Stack>
                ) : null}
                <Stack direction='row' spacing={1} alignItems='center' flexWrap='wrap'>
                  <Button
                    variant='contained'
                    disabled={!packageId || researchRunning}
                    onClick={async () => {
                      if (!packageId) return;
                      setResearchRunning(true);
                      setResearchResult(null);
                      setError(null);
                      try {
                        const res = await editorialApi.runResearch(packageId, {
                          dry_run: false,
                        });
                        const data = unwrapData<Record<string, unknown>>(res) || {};
                        setResearchResult(data);
                        await loadPackage(packageId);
                        await loadQueue();
                      } catch (e) {
                        setError(
                          e instanceof Error ? e.message : 'Research pass failed'
                        );
                      } finally {
                        setResearchRunning(false);
                      }
                    }}
                  >
                    {researchRunning ? 'Running research…' : 'Run research pass'}
                  </Button>
                  <Button
                    variant='outlined'
                    onClick={async () => {
                      await editorialApi.patchPackage(packageId!, {
                        presentation_kind: 'research_brief',
                        modal: 'research',
                      });
                      await loadPackage(packageId!);
                    }}
                  >
                    Propose research_brief
                  </Button>
                  <Button
                    variant='outlined'
                    color='warning'
                    onClick={async () => {
                      await editorialApi.markReady(packageId!, {
                        from_modal: 'research',
                        rationale: note || 'operator override → editor',
                      });
                      await loadPackage(packageId!);
                      await loadQueue();
                    }}
                  >
                    Override → Editor
                  </Button>
                </Stack>
                {researchResult ? (
                  <Alert severity={researchResult.skipped ? 'info' : 'success'}>
                    <Typography variant='body2'>
                      {researchResult.skipped
                        ? `Skipped: ${String(researchResult.reason || '')}`
                        : researchResult.insufficient_evidence
                          ? `Insufficient evidence: ${(
                              (researchResult.gaps as string[]) || []
                            ).join('; ') || 'no core claim'}`
                          : String(
                              researchResult.summary_stub || 'Research pass complete'
                            )}
                    </Typography>
                    {!researchResult.skipped ? (
                      <Typography variant='caption' component='div' sx={{ mt: 0.5 }}>
                        attached={String(
                          (researchResult.counts as Record<string, unknown>)
                            ?.attached ?? 0
                        )}
                        {' · '}
                        links={String(
                          (researchResult.counts as Record<string, unknown>)
                            ?.links_added ?? 0
                        )}
                        {' · '}
                        changed={String(researchResult.changed ?? 0)}
                        {researchResult.route_target
                          ? ` · routed → ${String(researchResult.route_target)}`
                          : ''}
                        {researchResult.used_fallback ? ' · deterministic fallback' : ''}
                      </Typography>
                    ) : null}
                  </Alert>
                ) : null}
              </Stack>
            ) : null}
            {modal === 'narrative' ? (
              <Stack spacing={1} sx={{ mt: 1 }}>
                {pkg?.readiness ? (
                  <Stack direction='row' spacing={1} flexWrap='wrap'>
                    <Chip
                      size='small'
                      color={
                        (pkg.readiness as Record<string, unknown>).event_narrative_ready
                          ? 'success'
                          : 'default'
                      }
                      label={`event_narrative_ready=${String(
                        Boolean(
                          (pkg.readiness as Record<string, unknown>).event_narrative_ready
                        )
                      )}`}
                    />
                    <Chip
                      size='small'
                      color={
                        (pkg.readiness as Record<string, unknown>).hybrid_ready
                          ? 'success'
                          : 'default'
                      }
                      label={`hybrid_ready=${String(
                        Boolean((pkg.readiness as Record<string, unknown>).hybrid_ready)
                      )}`}
                    />
                  </Stack>
                ) : null}
                <Stack direction='row' spacing={1} alignItems='center' flexWrap='wrap'>
                  <Button
                    variant='contained'
                    disabled={!packageId || narrativeRunning}
                    onClick={async () => {
                      if (!packageId) return;
                      setNarrativeRunning(true);
                      setNarrativeResult(null);
                      setError(null);
                      try {
                        const res = await editorialApi.runNarrative(packageId, {
                          dry_run: false,
                        });
                        const data = unwrapData<Record<string, unknown>>(res) || {};
                        setNarrativeResult(data);
                        await loadPackage(packageId);
                        await loadQueue();
                      } catch (e) {
                        setError(
                          e instanceof Error ? e.message : 'Narrative pass failed'
                        );
                      } finally {
                        setNarrativeRunning(false);
                      }
                    }}
                  >
                    {narrativeRunning ? 'Running narrative…' : 'Run narrative pass'}
                  </Button>
                  <Button
                    variant='outlined'
                    onClick={async () => {
                      await editorialApi.patchPackage(packageId!, {
                        presentation_kind: 'event_narrative',
                        modal: 'narrative',
                      });
                      await loadPackage(packageId!);
                    }}
                  >
                    Propose event_narrative
                  </Button>
                  <Button
                    variant='outlined'
                    color='warning'
                    onClick={async () => {
                      await editorialApi.markReady(packageId!, {
                        from_modal: 'narrative',
                        rationale: note || 'operator override → editor',
                      });
                      await loadPackage(packageId!);
                      await loadQueue();
                    }}
                  >
                    Override → Editor
                  </Button>
                </Stack>
                {narrativeResult ? (
                  <Alert severity={narrativeResult.skipped ? 'info' : 'success'}>
                    <Typography variant='body2'>
                      {narrativeResult.skipped
                        ? `Skipped: ${String(narrativeResult.reason || '')}`
                        : narrativeResult.insufficient_evidence
                          ? `Insufficient evidence: ${(
                              (narrativeResult.gaps as string[]) || []
                            ).join('; ') || 'no anchor'}`
                          : String(
                              narrativeResult.summary_stub || 'Narrative pass complete'
                            )}
                    </Typography>
                    {!narrativeResult.skipped ? (
                      <Typography variant='caption' component='div' sx={{ mt: 0.5 }}>
                        attached={String(
                          (narrativeResult.counts as Record<string, unknown>)
                            ?.attached ?? 0
                        )}
                        {' · '}
                        links={String(
                          (narrativeResult.counts as Record<string, unknown>)
                            ?.links_added ?? 0
                        )}
                        {' · '}
                        changed={String(narrativeResult.changed ?? 0)}
                        {narrativeResult.route_target
                          ? ` · routed → ${String(narrativeResult.route_target)}`
                          : ''}
                        {narrativeResult.used_fallback ? ' · deterministic fallback' : ''}
                      </Typography>
                    ) : null}
                  </Alert>
                ) : null}
              </Stack>
            ) : null}
            {modal === 'reduction' ? (
              <Stack spacing={1} sx={{ mt: 1 }}>
                <Stack direction='row' spacing={1} alignItems='center' flexWrap='wrap'>
                  <Button
                    variant='contained'
                    disabled={!packageId || reductionRunning}
                    onClick={async () => {
                      if (!packageId) return;
                      setReductionRunning(true);
                      setReductionResult(null);
                      setError(null);
                      try {
                        const res = await editorialApi.runReduction(packageId, {
                          dry_run: false,
                        });
                        const data = unwrapData<Record<string, unknown>>(res) || {};
                        setReductionResult(data);
                        await loadPackage(packageId);
                        await loadQueue();
                      } catch (e) {
                        setError(
                          e instanceof Error ? e.message : 'Reduction pass failed'
                        );
                      } finally {
                        setReductionRunning(false);
                      }
                    }}
                  >
                    {reductionRunning ? 'Running reduction…' : 'Run reduction pass'}
                  </Button>
                  <TextField
                    size='small'
                    label='Rationale'
                    value={note}
                    onChange={e => setNote(e.target.value)}
                  />
                  <Button
                    variant='contained'
                    color='success'
                    onClick={async () => {
                      await editorialApi.reduction(packageId!, {
                        clear: true,
                        rationale: note || 'cleared',
                      });
                      await loadPackage(packageId!);
                      await loadQueue();
                    }}
                  >
                    Clear → Editor
                  </Button>
                  <Button
                    variant='outlined'
                    color='error'
                    onClick={async () => {
                      await editorialApi.reduction(packageId!, {
                        clear: false,
                        rationale: note || 'blocked',
                      });
                      await loadPackage(packageId!);
                      await loadQueue();
                    }}
                  >
                    Block
                  </Button>
                </Stack>
                {reductionResult ? (
                  <Alert severity={reductionResult.skipped ? 'info' : 'success'}>
                    <Typography variant='body2'>
                      {reductionResult.skipped
                        ? `Skipped: ${String(reductionResult.reason || '')}`
                        : String(reductionResult.summary || 'Reduction pass complete')}
                    </Typography>
                    {!reductionResult.skipped ? (
                      <Typography variant='caption' component='div' sx={{ mt: 0.5 }}>
                        uncoupled={String(
                          (reductionResult.counts as Record<string, unknown>)?.removed ??
                            0
                        )}
                        {' · '}
                        quarantined={String(
                          (reductionResult.counts as Record<string, unknown>)
                            ?.quarantined ?? 0
                        )}
                        {' · '}
                        links dropped={String(
                          (reductionResult.counts as Record<string, unknown>)?.unlinked ??
                            0
                        )}
                        {' (sources kept)'}
                        {reductionResult.route_target
                          ? ` · routed → ${String(reductionResult.route_target)}`
                          : reductionResult.converged
                            ? ' · converged (stays in Reduction)'
                            : ''}
                        {reductionResult.used_fallback ? ' · deterministic fallback' : ''}
                      </Typography>
                    ) : null}
                  </Alert>
                ) : null}
              </Stack>
            ) : null}
          </UiCard>

          <UiCard title={`Links (${links.length})`}>
            <List dense>
              {links.map(l => (
                <ListItem
                  key={String(l.id)}
                  secondaryAction={
                    modal === 'reduction' && l.status === 'active' ? (
                      <Button
                        size='small'
                        color='error'
                        onClick={async () => {
                          await editorialApi.setLinkStatus(packageId!, Number(l.id), {
                            status: 'removed',
                            rationale: note || 'uncouple package link',
                          });
                          await loadPackage(packageId!);
                        }}
                      >
                        Uncouple
                      </Button>
                    ) : (
                      <Chip size='small' label={String(l.status)} />
                    )
                  }
                >
                  <ListItemText
                    primary={`${l.link_type}: ${l.from_member_id} → ${l.to_member_id}`}
                    secondary={`${l.inference_stage}`}
                  />
                </ListItem>
              ))}
            </List>
          </UiCard>
        </>
      ) : (
        <Typography color='text.secondary'>No package open.</Typography>
      )}
    </PageShell>
  );
}
