/**
 * Dedicated knowledge_profile reader (research subject standing report).
 */
import React, { useEffect, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';
import { Alert, Button, Stack } from '@mui/material';
import { PageShell, UiCard, LoadingState } from '@/components/ui';
import { editorialApi } from '@/services/api/editorial';
import { unwrapData } from '@/services/api/editorialUnwrap';
import KnowledgeProfileReader, {
  type KnowledgeProfileLike,
} from '@/components/Editorial/KnowledgeProfileReader';

export default function KnowledgeProfilePage() {
  const { entityId, domain, profileId } = useParams<{
    entityId?: string;
    domain: string;
    profileId?: string;
  }>();
  const dk = domain || 'medicine';
  const eid = entityId ? Number(entityId) : null;
  const pid = profileId ? Number(profileId) : null;
  const [profile, setProfile] = useState<KnowledgeProfileLike | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        let res;
        if (pid) {
          res = await editorialApi.getKnowledgeProfile(pid);
        } else if (eid) {
          res = await editorialApi.getKnowledgeProfileByEntity(dk, eid);
        } else {
          throw new Error('entityId or profileId required');
        }
        const data = unwrapData<KnowledgeProfileLike>(res);
        if (!cancelled) setProfile(data);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load profile');
          setProfile(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [dk, eid, pid]);

  const ensureAndMerge = async () => {
    if (!eid) return;
    setBusy(true);
    setError(null);
    try {
      await editorialApi.ensureKnowledgeProfile({
        domain_key: dk,
        canonical_entity_id: eid,
        refresh_package: true,
      });
      const pkgRes = await editorialApi.fromEntity({
        domain_key: dk,
        canonical_entity_id: eid,
        refresh_members: true,
      });
      const pkg = unwrapData<{ id?: number; package_id?: number }>(pkgRes);
      const packageId = Number(pkg.id || pkg.package_id);
      if (packageId) {
        await editorialApi.mergeKnowledgeProfileFromPackage({ package_id: packageId });
      }
      const refreshed = await editorialApi.getKnowledgeProfileByEntity(dk, eid);
      setProfile(unwrapData<KnowledgeProfileLike>(refreshed));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Merge failed');
    } finally {
      setBusy(false);
    }
  };

  if (loading && !profile) return <LoadingState />;
  if (!profile) {
    return (
      <PageShell title='Knowledge profile'>
        <Alert severity='error' sx={{ mb: 2 }}>
          {error || 'Not found'}
        </Alert>
        {eid ? (
          <Button variant='contained' onClick={ensureAndMerge} disabled={busy}>
            Ensure package & merge
          </Button>
        ) : null}
      </PageShell>
    );
  }

  return (
    <PageShell
      title={String(profile.title || `Profile ${profile.id}`)}
      subtitle={
        profile.status === 'published'
          ? 'Published knowledge profile'
          : `Standing research profile · status=${profile.status}`
      }
      breadcrumbs={[
        { label: 'Research subject', to: `/${dk}/research/subjects` },
        { label: profile.title || `Entity ${eid || ''}` },
      ]}
    >
      {error ? (
        <Alert severity='error' sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}
      <Stack direction='row' spacing={1} sx={{ mb: 2 }} flexWrap='wrap'>
        {eid ? (
          <Button
            component={RouterLink}
            to={`/${dk}/research/subjects?entity=${encodeURIComponent(String(profile.title || ''))}`}
            size='small'
            variant='outlined'
          >
            Subject ledger
          </Button>
        ) : null}
        {profile.package_id ? (
          <Button
            component={RouterLink}
            to={`/${dk}/editor/packages/${profile.package_id}`}
            size='small'
            variant='outlined'
          >
            Open package #{String(profile.package_id)}
          </Button>
        ) : null}
        {eid ? (
          <Button size='small' variant='contained' onClick={ensureAndMerge} disabled={busy}>
            Refresh & merge
          </Button>
        ) : null}
      </Stack>
      <UiCard>
        <KnowledgeProfileReader profile={profile} variant='full' />
      </UiCard>
    </PageShell>
  );
}
