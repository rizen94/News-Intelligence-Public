/**
 * Operator control: create/attach article or event to an editorial package.
 */
import React, { useState } from 'react';
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { editorialApi, type ModalKey } from '@/services/api/editorial';
import { unwrapData } from '@/services/api/editorialUnwrap';

export type AddToPackageHit = {
  member_family: 'research' | 'narrative';
  member_type: string;
  member_id: number;
  domain_key: string;
  role?: string;
  label?: string;
  provenance?: Record<string, unknown>;
};

type Props = {
  domainKey: string;
  hit: AddToPackageHit;
  preferredModal?: ModalKey;
  label?: string;
};

export function AddToPackageButton({
  domainKey,
  hit,
  preferredModal,
  label = 'Add to package',
}: Props) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [packageId, setPackageId] = useState('');
  const [modal, setModal] = useState<ModalKey>(
    preferredModal ||
      (hit.member_family === 'research' ? 'research' : 'narrative')
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (createNew: boolean) => {
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        modal,
        hits: [
          {
            ...hit,
            provenance: {
              label: hit.label,
              ...(hit.provenance || {}),
            },
          },
        ],
        domain_keys: [domainKey],
        working_title: hit.label || `Package · ${hit.member_type} ${hit.member_id}`,
      };
      if (!createNew && packageId.trim()) {
        body.package_id = Number(packageId.trim());
      }
      const res = await editorialApi.fromSelection(body);
      const data = unwrapData<{ id?: number }>(res);
      const id = Number(data?.id);
      if (!id) throw new Error('No package id returned');
      setOpen(false);
      navigate(`/${domainKey}/editor/packages/${id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Attach failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Button size='small' variant='outlined' onClick={() => setOpen(true)}>
        {label}
      </Button>
      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth='sm'>
        <DialogTitle>Add to editorial package</DialogTitle>
        <DialogContent>
          <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>
            {hit.member_family}/{hit.member_type} #{hit.member_id}
            {hit.label ? ` — ${hit.label}` : ''}
          </Typography>
          <Stack spacing={2}>
            <FormControl size='small' fullWidth>
              <InputLabel>Modal</InputLabel>
              <Select
                label='Modal'
                value={modal}
                onChange={e => setModal(e.target.value as ModalKey)}
              >
                <MenuItem value='research'>Research</MenuItem>
                <MenuItem value='narrative'>Narrative</MenuItem>
                <MenuItem value='reduction'>Reduction</MenuItem>
                <MenuItem value='editor'>Editor</MenuItem>
              </Select>
            </FormControl>
            <TextField
              size='small'
              label='Existing package ID (optional)'
              value={packageId}
              onChange={e => setPackageId(e.target.value)}
            />
            {error ? (
              <Typography color='error' variant='body2'>
                {error}
              </Typography>
            ) : null}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)} disabled={busy}>
            Cancel
          </Button>
          <Button
            onClick={() => submit(false)}
            disabled={busy || !packageId.trim()}
          >
            Attach to existing
          </Button>
          <Button variant='contained' onClick={() => submit(true)} disabled={busy}>
            Create new package
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
