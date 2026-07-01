/** FtM identity spine bridge + cache detail from NRI entity_bridge API. */
import React from 'react';
import { Alert, Box, Button, Stack, Typography } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import type { NriEntityBridge } from '@/services/api/contextCentric';
import { UiBadge, UiCard } from '@/components/ui';
import { useDomain } from '@/contexts/DomainContext';

export function FtmBridgePanel({ bridge }: { bridge: NriEntityBridge }) {
  const { domain } = useDomain();
  const anchors = bridge.anchors ?? {};
  const anchorEntries = Object.entries(anchors);
  const qaStatus = bridge.qa_status ?? 'unknown';
  const qaTone =
    qaStatus === 'ok' ? 'success' : qaStatus === 'suspect' ? 'warning' : 'error';

  return (
    <UiCard title='FollowTheMoney identity' subheader='NRI entity bridge + cache'>
      {qaStatus !== 'ok' && (
        <Alert severity={qaStatus === 'mismatch' ? 'error' : 'warning'} sx={{ mb: 1.5 }}>
          FtM link {qaStatus}: NI name &ldquo;{bridge.ni_canonical_name ?? '—'}&rdquo; vs spine
          &ldquo;{bridge.caption ?? '—'}&rdquo;
          {bridge.name_similarity != null && ` (similarity ${(bridge.name_similarity * 100).toFixed(0)}%)`}.
          Do not trust bridge_score alone for identity quality.
        </Alert>
      )}
      <Stack direction='row' spacing={1} flexWrap='wrap' useFlexGap sx={{ mb: 1.5 }}>
        <UiBadge label={bridge.ftm_id} color='primary' />
        {bridge.caption && <UiBadge label={bridge.caption} />}
        {bridge.schema_name && <UiBadge label={bridge.schema_name} />}
        {bridge.dataset && <UiBadge label={bridge.dataset} color='secondary' />}
        <UiBadge label={`QA ${qaStatus}`} color={qaTone === 'success' ? 'success' : qaTone === 'warning' ? 'warning' : 'error'} />
        {bridge.name_similarity != null && (
          <UiBadge label={`name ${(bridge.name_similarity * 100).toFixed(0)}%`} />
        )}
        {bridge.bridge_score != null && (
          <UiBadge label={`match ${bridge.bridge_score.toFixed(3)}`} />
        )}
      </Stack>
      {(bridge.qa_flags?.length ?? 0) > 0 && (
        <Typography variant='caption' color='text.secondary' display='block' sx={{ mb: 1 }}>
          Flags: {bridge.qa_flags?.join(', ')}
        </Typography>
      )}
      {bridge.bridged_at && (
        <Typography variant='caption' color='text.secondary' display='block' sx={{ mb: 1 }}>
          Bridged {new Date(bridge.bridged_at).toLocaleString()}
        </Typography>
      )}
      {anchorEntries.length > 0 && (
        <Box>
          <Typography variant='subtitle2' gutterBottom>
            Anchors
          </Typography>
          <Stack spacing={0.5}>
            {anchorEntries.map(([k, v]) => (
              <Typography key={k} variant='body2'>
                <strong>{k}:</strong> {v}
              </Typography>
            ))}
          </Stack>
        </Box>
      )}
      <Button
        size='small'
        component={RouterLink}
        to={`/${domain}/investigate/entity-resolution`}
        sx={{ mt: 1.5 }}
      >
        Resolution queue
      </Button>
    </UiCard>
  );
}
