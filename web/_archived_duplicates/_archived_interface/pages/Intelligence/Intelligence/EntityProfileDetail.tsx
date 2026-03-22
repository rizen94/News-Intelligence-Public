/**
 * Entity Profile detail — Phase 4.1 context-centric.
 * Wikipedia-style layout: sections, relationships summary, metadata.
 */
import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Box,
  Typography,
  Paper,
  Alert,
  Button,
  CircularProgress,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Divider,
} from '@mui/material';
import ArrowBack as ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ExpandMore as ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import Person as PersonIcon from '@mui/icons-material/Person';
import { useDomainRoute } from '../../hooks/useDomainRoute';
import { contextCentricApi, type EntityProfile } from '../../services/api/contextCentric';
import Logger from '../../utils/logger';

function displayName(profile: EntityProfile): string {
  const meta = profile.metadata as Record<string, unknown> | null;
  if (meta && typeof meta.canonical_name === 'string') return meta.canonical_name;
  if (profile.canonical_entity_id != null) return `Entity #${profile.canonical_entity_id}`;
  return `Profile #${profile.id}`;
}

const EntityProfileDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { getDomainPath } = useDomainRoute();
  const [profile, setProfile] = useState<EntityProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    const numId = parseInt(id, 10);
    if (Number.isNaN(numId)) {
      setError('Invalid profile ID');
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    contextCentricApi
      .getEntityProfile(numId)
      .then(setProfile)
      .catch((e) => {
        Logger.apiError('Entity profile load failed', e as Error);
        setError((e as Error).message ?? 'Failed to load profile');
        setProfile(null);
      })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error || !profile) {
    return (
      <Box>
        <Button startIcon={<ArrowBackIcon />} component={Link} to={getDomainPath('/intelligence/entity-profiles')}>
          Back to Entity Profiles
        </Button>
        <Alert severity="error" sx={{ mt: 2 }}>
          {error ?? 'Profile not found'}
        </Alert>
      </Box>
    );
  }

  const sections = profile.sections && typeof profile.sections === 'object' ? profile.sections as Record<string, unknown> : {};
  const sectionEntries = Object.entries(sections).filter(([, v]) => v != null && v !== '');

  return (
    <Box>
      <Button startIcon={<ArrowBackIcon />} component={Link} to={getDomainPath('/intelligence/entity-profiles')}>
        Back to Entity Profiles
      </Button>

      <Paper sx={{ mt: 2, p: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <PersonIcon color="action" />
          <Typography variant="h4" component="h1">
            {displayName(profile)}
          </Typography>
          <Chip label={profile.domain_key} size="small" variant="outlined" sx={{ ml: 1 }} />
          {profile.canonical_entity_id != null && (
            <Chip label={`Canonical #${profile.canonical_entity_id}`} size="small" variant="outlined" />
          )}
        </Box>
        {profile.compilation_date && (
          <Typography variant="body2" color="text.secondary">
            Last compiled: {new Date(profile.compilation_date).toLocaleString()}
          </Typography>
        )}

        {profile.relationships_summary && (
          <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              Relationships summary
            </Typography>
            <Typography variant="body1" component="div" sx={{ whiteSpace: 'pre-wrap' }}>
              {profile.relationships_summary}
            </Typography>
          </>
        )}

        {sectionEntries.length > 0 && (
          <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              Profile sections
            </Typography>
            {sectionEntries.map(([title, content]) => (
              <Accordion key={title} defaultExpanded={sectionEntries.length <= 3}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="subtitle1" sx={{ textTransform: 'capitalize' }}>
                    {title.replace(/_/g, ' ')}
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Typography variant="body2" component="div" sx={{ whiteSpace: 'pre-wrap' }}>
                    {typeof content === 'string' ? content : JSON.stringify(content, null, 2)}
                  </Typography>
                </AccordionDetails>
              </Accordion>
            ))}
          </>
        )}

        {profile.metadata && Object.keys(profile.metadata).length > 0 && (
          <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              Metadata
            </Typography>
            <Paper variant="outlined" sx={{ p: 2, bgcolor: 'grey.50' }}>
              <Typography variant="body2" component="pre" sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                {JSON.stringify(profile.metadata, null, 2)}
              </Typography>
            </Paper>
          </>
        )}

        {!profile.relationships_summary && sectionEntries.length === 0 && !(profile.metadata && Object.keys(profile.metadata).length > 0) && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            No sections or relationships compiled yet. Profiles are built by the entity_profile_build task.
          </Typography>
        )}
      </Paper>
    </Box>
  );
};

export default EntityProfileDetail;
