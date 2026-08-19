/**
 * Editor home — Alerts + Packages + Stories (v11).
 */
import React, { useEffect, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';
import {
  Button,
  Stack,
  Typography,
  List,
  ListItem,
  ListItemText,
  Chip,
  Tabs,
  Tab,
  Alert,
} from '@mui/material';
import { PageShell, UiCard, LoadingState } from '@/components/ui';
import { editorialApi } from '@/services/api/editorial';
import { unwrapData } from '@/services/api/editorialUnwrap';
import { useDomain } from '@/contexts/DomainContext';
import { statusLabel } from '@/utils/statusLabel';

export default function EditorHomePage() {
  const { domain: routeDomain } = useParams<{ domain: string }>();
  const { domain: domainKey } = useDomain();
  const dk = routeDomain || domainKey;
  const [tab, setTab] = useState(0);
  const [alerts, setAlerts] = useState<Record<string, unknown>[]>([]);
  const [packages, setPackages] = useState<Record<string, unknown>[]>([]);
  const [pkgFilter, setPkgFilter] = useState<'all' | 'closed_thin' | 'active'>('all');
  const [stories, setStories] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = async () => {
    setLoading(true);
    try {
      const [a, p, s] = await Promise.all([
        editorialApi.editorAlerts(),
        editorialApi.listPackages({ limit: 40 }),
        editorialApi.listStories({ limit: 40 }),
      ]);
      setAlerts(unwrapData<{ alerts?: Record<string, unknown>[] }>(a)?.alerts || []);
      setPackages(unwrapData<{ packages?: Record<string, unknown>[] }>(p)?.packages || []);
      setStories(unwrapData<{ stories?: Record<string, unknown>[] }>(s)?.stories || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Load failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void reload();
  }, []);

  return (
    <PageShell
      title='Editor'
      subtitle='Alerts, editorial packages, and published news stories'
      breadcrumbs={[{ label: 'Desk' }, { label: 'Editor' }]}
    >
      {error && (
        <Alert severity='error' sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab label={`Alerts (${alerts.length})`} />
        <Tab label={`Packages (${packages.length})`} />
        <Tab label={`Stories (${stories.length})`} />
      </Tabs>
      {loading ? <LoadingState /> : null}
      {tab === 0 && (
        <UiCard title='Inbox'>
          <List dense>
            {alerts.map(a => (
              <ListItem
                key={String(a.id)}
                secondaryAction={
                  <Stack direction='row' spacing={0.5}>
                    {a.package_id ? (
                      <Button
                        component={RouterLink}
                        to={`/${dk}/editor/packages/${a.package_id}`}
                        size='small'
                      >
                        Open
                      </Button>
                    ) : null}
                    <Button
                      size='small'
                      onClick={async () => {
                        await editorialApi.patchHandoff(Number(a.id), { status: 'accepted' });
                        await reload();
                      }}
                    >
                      Accept
                    </Button>
                    <Button
                      size='small'
                      onClick={async () => {
                        await editorialApi.patchHandoff(Number(a.id), { status: 'dismissed' });
                        await reload();
                      }}
                    >
                      Dismiss
                    </Button>
                  </Stack>
                }
              >
                <ListItemText
                  primary={`${a.reason_code} · ${a.working_title || `package ${a.package_id}`}`}
                  secondary={`${a.source_modal} → editor · ${a.created_at}`}
                />
              </ListItem>
            ))}
            {!alerts.length && !loading ? (
              <Typography color='text.secondary' sx={{ p: 2 }}>
                No open alerts.
              </Typography>
            ) : null}
          </List>
        </UiCard>
      )}
      {tab === 1 && (
        <UiCard title='Packages'>
          <Stack direction='row' spacing={1} sx={{ mb: 1 }} flexWrap='wrap'>
            <Button
              size='small'
              variant={pkgFilter === 'all' ? 'contained' : 'outlined'}
              onClick={() => setPkgFilter('all')}
            >
              All
            </Button>
            <Button
              size='small'
              variant={pkgFilter === 'active' ? 'contained' : 'outlined'}
              onClick={() => setPkgFilter('active')}
            >
              Active queues
            </Button>
            <Button
              size='small'
              color='warning'
              variant={pkgFilter === 'closed_thin' ? 'contained' : 'outlined'}
              onClick={() => setPkgFilter('closed_thin')}
            >
              Thin closed
            </Button>
            <Button
              size='small'
              variant='contained'
              onClick={async () => {
                const res = await editorialApi.createPackage({
                  working_title: 'Editor draft package',
                  primary_modal: 'editor',
                  domain_keys: [dk],
                });
                const data = unwrapData<{ id?: number }>(res);
                if (data?.id) {
                  window.location.href = `/${dk}/editor/packages/${data.id}`;
                }
              }}
            >
              New package
            </Button>
          </Stack>
          <List dense>
            {packages
              .filter(p => {
                const st = String(p.status || '');
                if (pkgFilter === 'closed_thin') return st === 'closed_thin';
                if (pkgFilter === 'active') {
                  return [
                    'in_research',
                    'in_narrative',
                    'in_reduction',
                    'ready_for_editor',
                    'draft',
                  ].includes(st);
                }
                return true;
              })
              .map(p => (
              <ListItem
                key={String(p.id)}
                secondaryAction={
                  <Button
                    component={RouterLink}
                    to={`/${dk}/editor/packages/${p.id}`}
                    size='small'
                  >
                    Review
                  </Button>
                }
              >
                <ListItemText
                  primary={String(p.working_title || `Package ${p.id}`)}
                  secondary={
                    <Stack direction='row' spacing={1} component='span'>
                      <Chip
                        size='small'
                        label={statusLabel(String(p.status))}
                        color={
                          String(p.status) === 'closed_thin' ? 'warning' : 'default'
                        }
                      />
                      <Chip size='small' label={String(p.presentation_kind)} />
                    </Stack>
                  }
                />
              </ListItem>
            ))}
          </List>
        </UiCard>
      )}
      {tab === 2 && (
        <UiCard title='News stories'>
          <List dense>
            {stories.map(s => (
              <ListItem
                key={String(s.id)}
                secondaryAction={
                  <Stack direction='row' spacing={0.5}>
                    <Button
                      component={RouterLink}
                      to={`/${dk}/editor/stories/${s.id}`}
                      size='small'
                      variant='contained'
                    >
                      Read
                    </Button>
                    {s.package_id ? (
                      <Button
                        component={RouterLink}
                        to={`/${dk}/editor/packages/${s.package_id}`}
                        size='small'
                      >
                        Package
                      </Button>
                    ) : null}
                  </Stack>
                }
              >
                <ListItemText
                  primary={String(s.title || `Story ${s.id}`)}
                  secondary={`#${s.id} · status=${s.status} · package=${s.package_id} · ${s.package_title || ''}`}
                />
              </ListItem>
            ))}
            {!stories.length && !loading ? (
              <Typography color='text.secondary' sx={{ p: 2 }}>
                No news stories yet.
              </Typography>
            ) : null}
          </List>
        </UiCard>
      )}
    </PageShell>
  );
}
