import React from 'react';
import { Card, CardContent, CardHeader, type CardProps } from '@mui/material';

export function UiCard({
  title,
  subheader,
  children,
  ...props
}: CardProps & { title?: string; subheader?: string; children: React.ReactNode }) {
  return (
    <Card variant='outlined' sx={{ borderRadius: 2, ...props.sx }} {...props}>
      {(title || subheader) && <CardHeader title={title} subheader={subheader} />}
      <CardContent>{children}</CardContent>
    </Card>
  );
}
