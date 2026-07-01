import React from 'react';
import { Chip, type ChipProps } from '@mui/material';

export function UiBadge({ label, ...props }: { label: string } & ChipProps) {
  return <Chip label={label} size='small' variant='outlined' {...props} />;
}
