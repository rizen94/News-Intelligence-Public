/**
 * Entity profile detail — single entity with sections and metadata.
 */
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardContent, Typography, Button, Box, Skeleton } from '@mui/material';
import ArrowBack from '@mui/icons-material/ArrowBack';
import { contextCentricApi, type EntityProfile } from '@/services/api/contextCentric';
import OrchestratorTagsEditor from '@/components/shared/OrchestratorTagsEditor/OrchestratorTagsEditor';

function displayName(p: EntityProfile): string {
  const meta = p.metadata as Record<string, unknown> | null;
  return (meta?.canonical_name as string) || `Entity #${p.id}`;
}

export default function EntityDetailPage() {
  const { domain, id } = useParams<{ domain: string; id: string }>();
  const navigate = useNavigate();
  const [profile, setProfile] = useState<EntityProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    const numId = parseInt(id, 10);
    if (Number.isNaN(numId)) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    contextCentricApi.getEntityProfile(numId)
      .then((p) => { if (!cancelled) setProfile(p); })
      .catch(() => { if (!cancelled) setProfile(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [id]);

  if (!domain) return null;

  return (
    <Box>
      <Button startIcon={<ArrowBack />} onClick={() => navigate(`/${domain}/investigate/entities`)} sx={{ mb: 2 }}>
        Back
      </Button>
      {loading ? (
        <Skeleton variant="rectangular" height={200} />
      ) : !profile ? (
        <Typography color="text.secondary">Entity not found.</Typography>
      ) : (
        <Card>
          <CardHeader title={displayName(profile)} subheader={profile.domain_key} />
          <CardContent>
            <Box sx={{ mb: 2 }}>
              <OrchestratorTagsEditor
                tags={Array.isArray(profile.metadata?.orchestrator_tags) ? (profile.metadata.orchestrator_tags as string[]) : []}
                onSave={async (tags) => {
                  const updated = await contextCentricApi.updateEntityProfile(profile.id, { orchestrator_tags: tags });
                  setProfile(updated);
                }}
              />
            </Box>
            {profile.relationships_summary && (
              <Typography variant="body2" paragraph>{profile.relationships_summary}</Typography>
            )}
            {profile.sections != null && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2">Sections</Typography>
                {Array.isArray(profile.sections)
                  ? (profile.sections as { title?: string; content?: string }[]).map((s, i) => (
                      <Box key={i} sx={{ mt: 1 }}>
                        {s.title && <Typography variant="caption" color="text.secondary">{s.title}</Typography>}
                        {s.content && <Typography variant="body2">{s.content}</Typography>}
                      </Box>
                    ))
                  : Object.entries(profile.sections as Record<string, unknown>).map(([key, val]) => (
                      <Box key={key} sx={{ mt: 1 }}>
                        <Typography variant="caption" color="text.secondary">{key}</Typography>
                        <Typography variant="body2">{typeof val === 'string' ? val : JSON.stringify(val)}</Typography>
                      </Box>
                    ))}
              </Box>
            )}
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
