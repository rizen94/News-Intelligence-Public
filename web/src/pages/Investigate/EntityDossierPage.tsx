/**
 * Entity Dossier — biographic intelligence view of a recurring entity.
 * Shows: narrative summary, positions/stances, article timeline, relationships, patterns.
 * Data: /api/synthesis/entity/{id} + /api/entity_profiles
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Alert,
  Avatar,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  LinearProgress,
  Link as MuiLink,
  Paper,
  Skeleton,
  Stack,
  Tab,
  Tabs,
  Tooltip,
  Typography,
} from '@mui/material';
import ArrowBack from '@mui/icons-material/ArrowBack';
import Person from '@mui/icons-material/Person';
import Business from '@mui/icons-material/Business';
import Article from '@mui/icons-material/Article';
import TrendingUp from '@mui/icons-material/TrendingUp';
import Hub from '@mui/icons-material/Hub';
import Refresh from '@mui/icons-material/Refresh';
import AutoAwesome from '@mui/icons-material/AutoAwesome';
import {
  contextCentricApi,
  type EntitySynthesis,
  type EntityProfile,
} from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';
import { isValidDomain, type DomainKey } from '@/utils/domainHelper';
import ProvenancePanel, { entityDossierProvenanceRows } from '@/components/ProvenancePanel/ProvenancePanel';

function entityIcon(type: string) {
  switch (type) {
    case 'person': return <Person />;
    case 'organization': return <Business />;
    default: return <Person />;
  }
}

function entityColor(type: string): string {
  switch (type) {
    case 'person': return '#1976d2';
    case 'organization': return '#9c27b0';
    case 'subject': return '#2e7d32';
    default: return '#757575';
  }
}

function confidenceBar(confidence: number | null) {
  if (confidence == null) return null;
  const pct = Math.round(confidence * 100);
  const color = pct >= 70 ? 'success' : pct >= 40 ? 'warning' : 'error';
  return (
    <Tooltip title={`${pct}% confidence`}>
      <LinearProgress variant="determinate" value={pct} color={color} sx={{ width: 60, height: 6, borderRadius: 3 }} />
    </Tooltip>
  );
}

export default function EntityDossierPage() {
  const { domain, entityId } = useParams<{ domain: string; entityId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { domain: domainFromContext } = useDomain();
  // Use domain from URL so the entity is always fetched for the domain in the route (fixes "not found in domain" when context was a different domain)
  const domainKey: DomainKey =
    domain && isValidDomain(domain) ? (domain as DomainKey) : domainFromContext;
  const [synthesis, setSynthesis] = useState<EntitySynthesis | null>(null);
  const [profile, setProfile] = useState<EntityProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [compiling, setCompiling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState(0);

  const nameFromUrl = searchParams.get('name') ?? '';
  const isByName = entityId === 'by-name' && nameFromUrl.trim().length > 0;
  const numId = !isByName && entityId ? parseInt(entityId, 10) : NaN;
  const resolvedId = Number.isNaN(numId) ? null : numId;

  const load = useCallback(async () => {
    if (resolvedId == null || !domainKey) return;
    setLoading(true);
    setError(null);
    try {
      const data = await contextCentricApi.getEntitySynthesis(resolvedId, domainKey) as EntitySynthesis & { success?: boolean; error?: string };
      if (data && (data as { success?: boolean }).success === false) {
        setError((data as { error?: string }).error ?? 'Entity not found in this domain.');
        setSynthesis(null);
      } else {
        setSynthesis(data);
        const profiles = await contextCentricApi.getEntityProfiles({ domain_key: domainKey, limit: 200, brief: false });
        const match = (profiles?.items ?? []).find(
          (p) => p.canonical_entity_id === resolvedId && p.domain_key === domainKey,
        );
        setProfile(match ?? null);
      }
    } catch (e) {
      setError((e as Error)?.message ?? 'Failed to load entity data');
    } finally {
      setLoading(false);
    }
  }, [resolvedId, domainKey]);

  // Resolve by name/alias to main entity, then redirect to canonical id
  useEffect(() => {
    if (!isByName || !domainKey) return;
    let cancelled = false;
    contextCentricApi
      .resolveEntity({ domain_key: domainKey, entity_name: nameFromUrl.trim() })
      .then((res) => {
        if (cancelled) return;
        const match = res?.match ?? res?.candidates?.[0];
        const canonicalId = match?.canonical_entity_id ?? (match as { id?: number })?.id;
        if (canonicalId != null) {
          navigate(`/${domain}/investigate/entities/${canonicalId}/dossier`, { replace: true });
        } else {
          setError(`No entity found for "${nameFromUrl}"`);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError((e as Error)?.message ?? 'Failed to resolve entity by name');
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, [isByName, domainKey, nameFromUrl, domain, navigate]);

  useEffect(() => {
    if (resolvedId != null) load();
  }, [load, resolvedId]);

  const handleCompile = async () => {
    if (resolvedId == null || !domainKey) return;
    setCompiling(true);
    try {
      await contextCentricApi.compileEntityDossier(domainKey, resolvedId);
      await load();
    } catch (e) {
      setError((e as Error)?.message ?? 'Compilation failed');
    } finally {
      setCompiling(false);
    }
  };

  if (!domain) return null;

  const entity = synthesis?.entity;
  const dossier = synthesis?.dossier;
  const narrative = (dossier?.metadata?.narrative_summary as string) ?? null;
  const articles = synthesis?.articles ?? [];
  const positions = synthesis?.positions ?? [];
  const relationships = synthesis?.relationships ?? [];
  const profileSections = profile?.sections;
  const stats = synthesis?.statistics;

  return (
    <Box sx={{ maxWidth: 960, mx: 'auto' }}>
      <Button startIcon={<ArrowBack />} onClick={() => navigate(`/${domain}/investigate/entities`)} sx={{ mb: 2 }}>
        Back to Entities
      </Button>

      {loading ? (
        <Box>
          <Skeleton variant="rectangular" height={120} sx={{ borderRadius: 2, mb: 2 }} />
          <Skeleton variant="rectangular" height={300} sx={{ borderRadius: 2 }} />
        </Box>
      ) : error ? (
        <Alert severity="error">{error}</Alert>
      ) : !entity ? (
        <Alert severity="warning">Entity not found in this domain.</Alert>
      ) : (
        <>
          <ProvenancePanel
            title="Dossier provenance"
            subtitle="How this view is grounded in the corpus"
            rows={entityDossierProvenanceRows(synthesis, dossier ?? null, domainKey, resolvedId ?? entity.id)}
          />
          {/* Header card */}
          <Paper elevation={2} sx={{ p: 3, mb: 3, borderLeft: `4px solid ${entityColor(entity.entity_type)}` }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Avatar sx={{ bgcolor: entityColor(entity.entity_type), width: 56, height: 56 }}>
                {entityIcon(entity.entity_type)}
              </Avatar>
              <Box sx={{ flex: 1 }}>
                <Typography variant="h4" sx={{ fontWeight: 700 }}>
                  {entity.canonical_name}
                </Typography>
                <Stack direction="row" spacing={1} sx={{ mt: 0.5, alignItems: 'center' }}>
                  <Chip label={entity.entity_type} size="small" color="primary" variant="outlined" />
                  <Chip label={domainKey} size="small" variant="outlined" />
                  {entity.aliases?.length > 0 && (
                    <Typography variant="caption" color="text.secondary">
                      aka {entity.aliases.slice(0, 3).join(', ')}
                    </Typography>
                  )}
                </Stack>
                {stats && (
                  <Stack direction="row" spacing={2} sx={{ mt: 1 }}>
                    <Typography variant="body2" color="text.secondary">
                      <Article sx={{ fontSize: 14, verticalAlign: 'middle', mr: 0.3 }} />
                      {stats.article_count} articles
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      <TrendingUp sx={{ fontSize: 14, verticalAlign: 'middle', mr: 0.3 }} />
                      {stats.position_count} positions
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      <Hub sx={{ fontSize: 14, verticalAlign: 'middle', mr: 0.3 }} />
                      {stats.relationship_count} relationships
                    </Typography>
                  </Stack>
                )}
              </Box>
              <Stack spacing={1}>
                <Button size="small" startIcon={<Refresh />} onClick={load} variant="outlined">Refresh</Button>
                <Button size="small" startIcon={<AutoAwesome />} onClick={handleCompile} disabled={compiling} variant="contained">
                  {compiling ? 'Compiling…' : stats?.has_dossier ? 'Recompile' : 'Build Dossier'}
                </Button>
              </Stack>
            </Box>
          </Paper>

          {/* Narrative summary */}
          {narrative && (
            <Card variant="outlined" sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="overline" color="text.secondary">Intelligence Summary</Typography>
                <Typography variant="body1" sx={{ mt: 1, lineHeight: 1.8, whiteSpace: 'pre-wrap' }}>
                  {narrative}
                </Typography>
              </CardContent>
            </Card>
          )}

          {/* Profile sections (Wikipedia-style) */}
          {profileSections && (
            <Card variant="outlined" sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="overline" color="text.secondary">Profile</Typography>
                {Array.isArray(profileSections)
                  ? (profileSections as { title?: string; content?: string }[]).map((s, i) => (
                      <Box key={i} sx={{ mt: 1.5 }}>
                        {s.title && <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>{s.title}</Typography>}
                        {s.content && <Typography variant="body2" sx={{ lineHeight: 1.7 }}>{s.content}</Typography>}
                      </Box>
                    ))
                  : Object.entries(profileSections as Record<string, unknown>).map(([key, val]) => (
                      <Box key={key} sx={{ mt: 1.5 }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>{key}</Typography>
                        <Typography variant="body2">{typeof val === 'string' ? val : JSON.stringify(val)}</Typography>
                      </Box>
                    ))}
              </CardContent>
            </Card>
          )}

          {/* Tabbed sections */}
          <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
            <Tab label={`Positions (${positions.length})`} />
            <Tab label={`Articles (${articles.length})`} />
            <Tab label={`Relationships (${relationships.length})`} />
            {dossier?.patterns && (dossier.patterns as { count?: number }).count ? (
              <Tab label={`Patterns (${(dossier.patterns as { count?: number }).count})`} />
            ) : (
              <Tab label="Patterns" disabled />
            )}
          </Tabs>

          {/* Positions tab */}
          {tab === 0 && (
            <Box>
              {positions.length === 0 ? (
                <Typography color="text.secondary" sx={{ py: 2 }}>No positions tracked yet. Entity position tracking runs automatically.</Typography>
              ) : (
                <Stack spacing={1.5}>
                  {positions.map((p, i) => (
                    <Paper key={i} variant="outlined" sx={{ p: 2 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Chip label={p.topic} size="small" color="info" variant="outlined" />
                        {confidenceBar(p.confidence)}
                      </Box>
                      <Typography variant="body1" sx={{ mt: 1, fontStyle: 'italic' }}>
                        &ldquo;{p.position}&rdquo;
                      </Typography>
                    </Paper>
                  ))}
                </Stack>
              )}
            </Box>
          )}

          {/* Articles tab */}
          {tab === 1 && (
            <Box>
              {articles.length === 0 ? (
                <Typography color="text.secondary" sx={{ py: 2 }}>No articles found for this entity.</Typography>
              ) : (
                <Stack spacing={1}>
                  {articles.map((a) => (
                    <Paper key={a.id} variant="outlined" sx={{ p: 2 }}>
                      <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>{a.title}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {a.published_at ? new Date(a.published_at).toLocaleDateString() : 'Date unknown'}
                      </Typography>
                      {a.summary && (
                        <Typography variant="body2" sx={{ mt: 0.5, color: 'text.secondary' }}>
                          {a.summary.slice(0, 300)}{a.summary.length > 300 ? '…' : ''}
                        </Typography>
                      )}
                    </Paper>
                  ))}
                </Stack>
              )}
            </Box>
          )}

          {/* Relationships tab */}
          {tab === 2 && (
            <Box>
              {relationships.length === 0 ? (
                <Typography color="text.secondary" sx={{ py: 2 }}>No relationships mapped yet.</Typography>
              ) : (
                <Stack spacing={1}>
                  {relationships.map((r, i) => (
                    <Paper key={i} variant="outlined" sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Chip label={r.relationship_type} size="small" color="secondary" variant="outlined" />
                      <Typography variant="body2">
                        {r.source_domain}:{r.source_entity_id} → {r.target_domain}:{r.target_entity_id}
                      </Typography>
                      {confidenceBar(r.confidence)}
                    </Paper>
                  ))}
                </Stack>
              )}
            </Box>
          )}

          {/* Patterns tab */}
          {tab === 3 && dossier?.patterns && (
            <Box>
              {((dossier.patterns as { discoveries?: unknown[] }).discoveries ?? []).length === 0 ? (
                <Typography color="text.secondary" sx={{ py: 2 }}>No patterns detected.</Typography>
              ) : (
                <Stack spacing={1}>
                  {((dossier.patterns as { discoveries?: { id: number; pattern_type: string; confidence: number | null; data: Record<string, unknown> }[] }).discoveries ?? []).map((pat) => (
                    <Paper key={pat.id} variant="outlined" sx={{ p: 2 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Chip label={pat.pattern_type} size="small" variant="outlined" />
                        {confidenceBar(pat.confidence)}
                      </Box>
                      <Typography variant="body2" sx={{ mt: 0.5 }}>
                        {(pat.data?.description as string) || (pat.data?.summary as string) || JSON.stringify(pat.data).slice(0, 200)}
                      </Typography>
                    </Paper>
                  ))}
                </Stack>
              )}
            </Box>
          )}
        </>
      )}
    </Box>
  );
}
