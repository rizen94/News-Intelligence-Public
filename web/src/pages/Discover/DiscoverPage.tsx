/**
 * Discover — Latest contexts, entity browser (paginated for audits).
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  CardHeader,
  CardContent,
  CardActionArea,
  Typography,
  Tabs,
  Tab,
  Box,
  Skeleton,
  Button,
  Alert,
  Chip,
  List,
  ListItemButton,
  ListItemText,
  Pagination,
} from '@mui/material';
import { contextCentricApi, type Context, type EntityProfile } from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';
import { getCurrentApiUrl } from '@/config/apiConfig';

function displayName(p: EntityProfile): string {
  const meta = p.metadata as Record<string, unknown> | null;
  return (meta?.canonical_name as string) || `Entity #${p.id}`;
}

function stripHtml(html: string): string {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  return (doc.body.textContent || '').trim();
}

function cleanSnippet(raw: string, maxLen: number): string {
  const text = /<[a-z][\s\S]*?>/i.test(raw) ? stripHtml(raw) : raw;
  return text.length > maxLen ? text.slice(0, maxLen) + '…' : text;
}

const PAGE_SIZE = 24;

export default function DiscoverPage() {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const [tab, setTab] = useState(0);

  const [contexts, setContexts] = useState<Context[]>([]);
  const [contextTotal, setContextTotal] = useState(0);
  const [contextPage, setContextPage] = useState(1);
  const [contextsLoading, setContextsLoading] = useState(true);

  const [entities, setEntities] = useState<EntityProfile[]>([]);
  const [entityTotal, setEntityTotal] = useState(0);
  const [entityPage, setEntityPage] = useState(1);
  const [entitiesLoading, setEntitiesLoading] = useState(true);

  const [syncLoading, setSyncLoading] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [contextSyncLoading, setContextSyncLoading] = useState(false);
  const [contextSyncMessage, setContextSyncMessage] = useState<string | null>(null);
  const [entityError, setEntityError] = useState<string | null>(null);

  useEffect(() => {
    setContextPage(1);
    setEntityPage(1);
    setContextTotal(0);
    setEntityTotal(0);
  }, [domain]);

  const loadContexts = useCallback(async () => {
    setContextsLoading(true);
    try {
      const offset = (contextPage - 1) * PAGE_SIZE;
      const ctxRes = await contextCentricApi
        .getContexts({ domain_key: domain, limit: PAGE_SIZE, offset, brief: true })
        .catch(() => ({ items: [] as Context[], total: 0 }));
      setContexts(ctxRes?.items ?? []);
      setContextTotal(typeof ctxRes?.total === 'number' ? ctxRes.total : (ctxRes?.items ?? []).length);
    } finally {
      setContextsLoading(false);
    }
  }, [domain, contextPage]);

  const loadEntities = useCallback(async () => {
    setEntitiesLoading(true);
    setEntityError(null);
    try {
      const offset = (entityPage - 1) * PAGE_SIZE;
      const entRes = await contextCentricApi.getEntityProfiles({
        domain_key: domain,
        limit: PAGE_SIZE,
        offset,
        brief: true,
      });
      setEntities(entRes?.items ?? []);
      setEntityTotal(typeof entRes?.total === 'number' ? entRes.total : (entRes?.items ?? []).length);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setEntityError(detail ?? (err as Error)?.message ?? 'Request failed');
      setEntities([]);
      setEntityTotal(0);
    } finally {
      setEntitiesLoading(false);
    }
  }, [domain, entityPage]);

  useEffect(() => {
    if (tab !== 0) return;
    void loadContexts();
  }, [tab, loadContexts]);

  useEffect(() => {
    if (tab !== 1) return;
    void loadEntities();
  }, [tab, loadEntities]);

  const contextPageCount = Math.max(1, Math.ceil(contextTotal / PAGE_SIZE) || 1);
  const entityPageCount = Math.max(1, Math.ceil(entityTotal / PAGE_SIZE) || 1);

  const handleSyncEntities = async () => {
    setSyncMessage(null);
    setSyncLoading(true);
    try {
      const res = await contextCentricApi.syncEntityProfiles(domain);
      if (res.success && res.created_by_domain) {
        const total = Object.values(res.created_by_domain).reduce((a, b) => a + (b > 0 ? b : 0), 0);
        setSyncMessage(
          total > 0
            ? `Synced: ${total} new entity profile(s) for ${domain}.`
            : 'No new entities to sync (entity_canonical may be empty).',
        );
        if (total > 0) await loadEntities();
      } else {
        setSyncMessage(res.error ?? 'Sync failed.');
      }
    } finally {
      setSyncLoading(false);
    }
  };

  const handleSyncContexts = async () => {
    setContextSyncMessage(null);
    setContextSyncLoading(true);
    try {
      const res = await contextCentricApi.syncContexts(domain, 500);
      if (res.success && res.contexts_created_by_domain) {
        const created = res.contexts_created_by_domain[domain] ?? 0;
        setContextSyncMessage(
          created > 0
            ? `Created ${created} context(s) for ${domain}.`
            : 'No new contexts (all articles may already have contexts, or there are no articles for this domain).',
        );
        if (created > 0) {
          setContextPage(1);
          await loadContexts();
        }
      } else {
        setContextSyncMessage(res.error ?? 'Sync failed.');
      }
    } finally {
      setContextSyncLoading(false);
    }
  };

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2, fontWeight: 600 }}>
        Discover
      </Typography>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab label="Latest contexts" />
        <Tab label="Entity browser" />
      </Tabs>
      {tab === 0 && (
        <Box>
          {contextsLoading ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} variant="rectangular" height={120} sx={{ borderRadius: 1 }} />
              ))}
            </Box>
          ) : contexts.length === 0 ? (
            <Card variant="outlined">
              <CardContent>
                <Typography color="text.secondary" sx={{ mb: 2 }}>
                  No contexts yet for {domain}. Politics and finance use the same pipeline; contexts come from
                  articles in this domain.
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  {domain === 'finance'
                    ? 'Finance needs RSS feeds in the Finance domain (e.g. SEC, Federal Reserve, Treasury). Add feeds under Monitor or via API (POST /api/finance/rss_feeds), run collection, then use "Sync contexts" below to backfill from existing finance articles.'
                    : `Add RSS feeds for this domain, run collection (e.g. Monitor → trigger collection), then use "Sync contexts" to backfill from existing articles.`}
                </Typography>
                <Button variant="outlined" size="small" onClick={handleSyncContexts} disabled={contextSyncLoading}>
                  {contextSyncLoading ? 'Syncing…' : 'Sync contexts for this domain'}
                </Button>
                {contextSyncMessage && (
                  <Alert severity="info" sx={{ mt: 2 }} onClose={() => setContextSyncMessage(null)}>
                    {contextSyncMessage}
                  </Alert>
                )}
              </CardContent>
            </Card>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Showing {(contextPage - 1) * PAGE_SIZE + 1}–
                {Math.min(contextPage * PAGE_SIZE, contextTotal)} of {contextTotal} contexts
              </Typography>
              {contexts.map((c) => {
                const snippet = c.content ? cleanSnippet(c.content, 280) : null;
                const date = c.created_at
                  ? new Date(c.created_at).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })
                  : null;
                return (
                  <Card key={c.id} variant="outlined">
                    <CardActionArea onClick={() => navigate(`/${domain}/discover/contexts/${c.id}`)}>
                      <CardContent sx={{ pb: '12px !important' }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                          <Typography variant="subtitle1" sx={{ fontWeight: 600, flex: 1 }}>
                            {c.title || '(No title)'}
                          </Typography>
                          <Chip label={c.source_type} size="small" variant="outlined" />
                        </Box>
                        {snippet && (
                          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, lineHeight: 1.5 }}>
                            {snippet}
                          </Typography>
                        )}
                        {date && (
                          <Typography variant="caption" color="text.disabled" sx={{ mt: 1, display: 'block' }}>
                            {date}
                          </Typography>
                        )}
                      </CardContent>
                    </CardActionArea>
                  </Card>
                );
              })}
              {contextPageCount > 1 && (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
                  <Pagination
                    count={contextPageCount}
                    page={contextPage}
                    onChange={(_, p) => setContextPage(p)}
                    color="primary"
                    showFirstButton
                    showLastButton
                  />
                </Box>
              )}
            </Box>
          )}
        </Box>
      )}
      {tab === 1 && (
        <Card>
          <CardHeader title="Entity browser" subheader={`Domain: ${domain}`} />
          <CardContent>
            {entityError && (
              <Alert severity="error" sx={{ mb: 2 }} onClose={() => setEntityError(null)}>
                {entityError}
              </Alert>
            )}
            {syncMessage && (
              <Alert
                severity={syncMessage.startsWith('Synced') ? 'success' : 'info'}
                sx={{ mb: 2 }}
                onClose={() => setSyncMessage(null)}
              >
                {syncMessage}
              </Alert>
            )}
            {entitiesLoading ? (
              <Skeleton variant="rectangular" height={300} />
            ) : entities.length === 0 ? (
              <Box>
                <Typography color="text.secondary" paragraph>
                  No entity profiles yet. Entities are created from <strong>entity_canonical</strong> (filled by
                  article entity extraction). Run sync to copy them into the intelligence layer.
                </Typography>
                {syncMessage?.toLowerCase().includes('404') && (
                  <Alert severity="warning" sx={{ mb: 2 }}>
                    Context-centric API not found (404). Use the <strong>server root</strong> as API base:{' '}
                    <code>http://localhost:8000</code> (or your backend host). In <code>.env</code> set{' '}
                    <code>VITE_API_URL=http://localhost:8000</code> then restart the dev server; or leave it unset to
                    use the Vite proxy. Reload and try Sync again.
                  </Alert>
                )}
                <Typography variant="caption" display="block" color="text.secondary" sx={{ mb: 1 }}>
                  API base: {getCurrentApiUrl() || '(dev proxy → localhost:8000)'}
                </Typography>
                <Button variant="outlined" onClick={handleSyncEntities} disabled={syncLoading}>
                  {syncLoading ? 'Syncing…' : 'Sync entities for this domain'}
                </Button>
              </Box>
            ) : (
              <>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  Showing {(entityPage - 1) * PAGE_SIZE + 1}–{Math.min(entityPage * PAGE_SIZE, entityTotal)} of{' '}
                  {entityTotal} profiles
                </Typography>
                <List dense>
                  {entities.map((p) => (
                    <ListItemButton key={p.id} onClick={() => navigate(`/${domain}/investigate/entities/${p.id}`)}>
                      <ListItemText
                        primary={displayName(p)}
                        secondary={p.domain_key}
                        primaryTypographyProps={{ noWrap: true }}
                      />
                    </ListItemButton>
                  ))}
                </List>
                {entityPageCount > 1 && (
                  <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
                    <Pagination
                      count={entityPageCount}
                      page={entityPage}
                      onChange={(_, p) => setEntityPage(p)}
                      color="primary"
                      showFirstButton
                      showLastButton
                    />
                  </Box>
                )}
                <Button variant="outlined" size="small" sx={{ mt: 1 }} onClick={handleSyncEntities} disabled={syncLoading}>
                  {syncLoading ? 'Syncing…' : 'Sync new entities'}
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
