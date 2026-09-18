import React from 'react';
import { Tabs, Tab, Box } from '@mui/material';

export type UiTabItem = { id: string; label: string };

export function UiTabs({
  tabs,
  value,
  onChange,
  children,
}: {
  tabs: UiTabItem[];
  value: string;
  onChange: (id: string) => void;
  children: React.ReactNode;
}) {
  return (
    <Box>
      <Tabs
        value={value}
        onChange={(_, v) => onChange(v)}
        sx={{ mb: 2, borderBottom: 1, borderColor: 'divider' }}
      >
        {tabs.map(t => (
          <Tab key={t.id} value={t.id} label={t.label} />
        ))}
      </Tabs>
      {children}
    </Box>
  );
}
