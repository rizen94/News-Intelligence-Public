/**
 * Entity profiles list (Investigate section).
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardContent, Typography, List, ListItemButton, ListItemText, Skeleton, Box, Button, Alert } from '@mui/material';
import { contextCentricApi, type EntityProfile } from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';
import { getCurrentApiUrl } from '@/config/apiConfig';

function displayName(p: EntityProfile): string {
  const meta = p.metadata as Record<string, unknown> | null;
  return (meta?.canonical_name as string) || `Entity #${p.id}`;
}

export default function EntitiesListPage() {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const [entities, setEntities] = useState<EntityProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  const loadEntities = () => {
    contextCentricApi.getEntityProfiles({ domain_key: domain, limit: 50, brief: true })
      .then((res) => setEntities(res?.items ?? []))
      .catch(() => setEntities([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    setLoading(true);
    loadEntities();
  }, [domain]);

  const handleSyncEntities = async () => {
    setSyncMessage(null);
    setSyncLoading(true);
    try {
      const res = await contextCentricApi.syncEntityProfiles(domain);
      if (res.success && res.created_by_domain) {
        const total = Object.values(res.created_by_domain).reduce((a, b) => a + (b > 0 ? b : 0), 0);
        setSyncMessage(total > 0 ? `Synced: ${total} new entity profile(s).` : 'No new entities to sync (entity_canonical may be empty).');
        if (total > 0) {
          setLoading(true);
          loadEntities();
        }
      } else {
        setSyncMessage(res.error ?? 'Sync failed.');
      }
    } finally {
      setSyncLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader title="Entity profiles" subheader={domain} />
      <CardContent>
        {syncMessage && (
          <Alert
            severity={syncMessage.startsWith('Synced') ? 'success' : syncMessage.toLowerCase().includes('404') ? 'warning' : 'info'}
            sx={{ mb: 2 }}
            onClose={() => setSyncMessage(null)}
          >
            {syncMessage}
          </Alert>
        )}
        {loading ? (
          <Skeleton variant="rectangular" height={300} />
        ) : entities.length === 0 ? (
          <Box>
            <Typography color="text.secondary" paragraph>
              No entity profiles yet. Run sync to copy from entity_canonical (populated by article entity extraction).
            </Typography>
            {syncMessage?.toLowerCase().includes('404') && (
              <Alert severity="warning" sx={{ mb: 2 }}>
                Context-centric API not found (404). Use server root as API base: <code>VITE_API_URL=http://localhost:8000</code> in <code>.env</code> (then restart), or leave unset for the dev proxy. Reload and try Sync again.
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
          <List dense>
            {entities.map((p) => (
              <ListItemButton key={p.id} onClick={() => navigate(`/${domain}/investigate/entities/${p.id}`)}>
                <ListItemText primary={displayName(p)} secondary={p.domain_key} primaryTypographyProps={{ noWrap: true }} />
              </ListItemButton>
            ))}
          </List>
        )}
      </CardContent>
    </Card>
  );
}
