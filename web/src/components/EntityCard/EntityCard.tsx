/**
 * EntityCard — compact, expanded, or popover display for storyline/report entities.
 * Shows name, type icon, description (Wikipedia background); links to profile or dossier.
 */
import React, { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Card,
  CardContent,
  Typography,
  Chip,
  Box,
  Popover,
  Link,
  alpha,
} from '@mui/material';
import Person from '@mui/icons-material/Person';
import Business from '@mui/icons-material/Business';
import Place from '@mui/icons-material/Place';
import Event from '@mui/icons-material/Event';
import Category from '@mui/icons-material/Category';

export interface EntityCardEntity {
  canonical_entity_id: number;
  name: string;
  type: string;
  description?: string | null;
  mention_count?: number;
  has_profile?: boolean;
  has_dossier?: boolean;
  profile_id?: number | null;
  role_in_story?: string;
}

const TYPE_ICONS: Record<string, React.ReactNode> = {
  person: <Person fontSize="small" />,
  organization: <Business fontSize="small" />,
  location: <Place fontSize="small" />,
  place: <Place fontSize="small" />,
  event: <Event fontSize="small" />,
  subject: <Category fontSize="small" />,
};

function getTypeIcon(type: string) {
  const key = (type || 'subject').toLowerCase();
  return TYPE_ICONS[key] ?? TYPE_ICONS.subject;
}

export type EntityCardMode = 'compact' | 'expanded' | 'popover';

export interface EntityCardProps {
  entity: EntityCardEntity;
  mode?: EntityCardMode;
  /** For popover: anchor element (e.g. inline text). If not set, popover is not used. */
  popoverAnchor?: React.ReactNode;
  domain?: string;
}

export default function EntityCard({ entity, mode = 'compact', popoverAnchor, domain: domainProp }: EntityCardProps) {
  const navigate = useNavigate();
  const { domain: routeDomain } = useParams<{ domain: string }>();
  const domain = domainProp ?? routeDomain ?? 'politics';

  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const openPopover = Boolean(anchorEl);

  const profileId = entity.profile_id ?? null;
  const canonicalId = entity.canonical_entity_id;
  const description = entity.description?.trim() ?? '';
  const descShort = description.length > 100 ? description.slice(0, 100) + '…' : description;

  const handleClick = (e: React.MouseEvent) => {
    if (mode === 'popover' && popoverAnchor === undefined) {
      setAnchorEl(e.currentTarget as HTMLElement);
      return;
    }
    if (profileId != null) {
      navigate(`/${domain}/investigate/entities/${profileId}`);
    } else if (entity.has_dossier) {
      navigate(`/${domain}/investigate/entities/${canonicalId}/dossier`);
    }
  };

  const handleClosePopover = () => setAnchorEl(null);

  const content = (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap' }}>
      <Chip
        size="small"
        icon={<Box sx={{ display: 'flex', alignItems: 'center' }}>{getTypeIcon(entity.type)}</Box>}
        label={entity.name}
        onClick={mode === 'compact' ? handleClick : undefined}
        sx={{
          cursor: (profileId != null || entity.has_dossier) ? 'pointer' : 'default',
          '&:hover': (profileId != null || entity.has_dossier) ? { bgcolor: alpha('#1565c0', 0.12) } : {},
        }}
      />
      {mode === 'compact' && descShort && (
        <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 280 }} noWrap>
          {descShort}
        </Typography>
      )}
    </Box>
  );

  const expandedContent = (
    <Card variant="outlined" sx={{ minWidth: 260, maxWidth: 360 }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <Chip
            size="small"
            icon={<Box sx={{ display: 'flex', alignItems: 'center' }}>{getTypeIcon(entity.type)}</Box>}
            label={entity.name}
          />
          {entity.mention_count != null && entity.mention_count > 0 && (
            <Typography variant="caption" color="text.secondary">
              {entity.mention_count} mentions
            </Typography>
          )}
        </Box>
        {entity.role_in_story && (
          <Typography variant="body2" sx={{ mb: 1 }} color="text.secondary">
            {entity.role_in_story}
          </Typography>
        )}
        {description && (
          <Typography variant="body2" sx={{ mb: 1.5 }}>
            {description}
          </Typography>
        )}
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {profileId != null && (
            <Link
              component="button"
              variant="body2"
              onClick={() => navigate(`/${domain}/investigate/entities/${profileId}`)}
              sx={{ cursor: 'pointer' }}
            >
              View full profile
            </Link>
          )}
          {entity.has_dossier && (
            <Link
              component="button"
              variant="body2"
              onClick={() => navigate(`/${domain}/investigate/entities/${canonicalId}/dossier`)}
              sx={{ cursor: 'pointer' }}
            >
              View dossier
            </Link>
          )}
        </Box>
      </CardContent>
    </Card>
  );

  if (mode === 'popover') {
    const anchor = popoverAnchor ?? (
      <Typography
        component="span"
        sx={{ cursor: (profileId != null || entity.has_dossier) ? 'pointer' : 'default', textDecoration: 'underline', textDecorationStyle: 'dotted' }}
        onClick={(e) => setAnchorEl(e.currentTarget as HTMLElement)}
      >
        {entity.name}
      </Typography>
    );
    return (
      <>
        {anchor}
        <Popover
          open={openPopover}
          anchorEl={anchorEl}
          onClose={handleClosePopover}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
          transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        >
          <Box sx={{ p: 1.5 }}>
            {expandedContent}
          </Box>
        </Popover>
      </>
    );
  }

  if (mode === 'expanded') {
    return expandedContent;
  }

  return (
    <Card variant="outlined" sx={{ display: 'inline-flex', cursor: (profileId != null || entity.has_dossier) ? 'pointer' : 'default' }} onClick={mode === 'compact' ? handleClick : undefined}>
      <CardContent sx={{ py: 0.5, px: 1, '&:last-child': { pb: 0.5 } }}>
        {content}
      </CardContent>
    </Card>
  );
}
