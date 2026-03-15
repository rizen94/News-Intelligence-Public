/**
 * Processed documents (Phase 3 T3.1 / Phase 4).
 * List intelligence.processed_documents; add document or run ingest from config.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  Card,
  CardContent,
  Skeleton,
  Typography,
  Link as MuiLink,
  Alert,
  Snackbar,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
} from '@mui/material';
import Add from '@mui/icons-material/Add';
import Refresh from '@mui/icons-material/Refresh';
import ArrowBack from '@mui/icons-material/ArrowBack';
import { contextCentricApi, type ProcessedDocument } from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';

const emptyAddForm = { source_url: '', title: '', source_type: '', source_name: '', document_type: '', publication_date: '' };

export default function ProcessedDocumentsPage() {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const [items, setItems] = useState<ProcessedDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [ingesting, setIngesting] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [addForm, setAddForm] = useState(emptyAddForm);
  const [addSubmitting, setAddSubmitting] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [message, setMessage] = useState<{ text: string; severity: 'success' | 'error' | 'info' } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await contextCentricApi.getProcessedDocuments({ limit: 100 }).catch(() => ({ items: [] }));
      setItems(res?.items ?? []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleIngestFromConfig = async () => {
    setIngesting(true);
    try {
      const res = await contextCentricApi.ingestProcessedDocumentsFromConfig();
      setMessage({
        text: `Inserted ${res.inserted} document(s).${res.errors?.length ? ` Errors: ${res.errors.slice(0, 3).join('; ')}` : ''}`,
        severity: res.errors?.length && res.inserted === 0 ? 'error' : 'success',
      });
      await load();
    } catch (e) {
      setMessage({ text: (e as Error)?.message ?? 'Ingest failed', severity: 'error' });
    } finally {
      setIngesting(false);
    }
  };

  const handleAddSubmit = async () => {
    const url = addForm.source_url.trim();
    if (!url) {
      setAddError('URL is required');
      return;
    }
    setAddSubmitting(true);
    setAddError(null);
    try {
      const res = await contextCentricApi.createProcessedDocument({
        source_url: url,
        title: addForm.title.trim() || undefined,
        source_type: addForm.source_type.trim() || undefined,
        source_name: addForm.source_name.trim() || undefined,
        document_type: addForm.document_type.trim() || undefined,
        publication_date: addForm.publication_date.trim() || undefined,
      });
      if (res?.document_id) {
        setAddOpen(false);
        setAddForm(emptyAddForm);
        setMessage({ text: `Document #${res.document_id} added.`, severity: 'success' });
        await load();
      } else {
        setAddError(res?.error ?? 'Create failed');
      }
    } catch (e) {
      setAddError((e as Error)?.message ?? 'Create failed');
    } finally {
      setAddSubmitting(false);
    }
  };

  return (
    <Box>
      <Button startIcon={<ArrowBack />} onClick={() => navigate(`/${domain}/investigate`)} sx={{ mb: 2 }}>
        Back to Investigate
      </Button>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h5" sx={{ fontWeight: 600 }}>
          Processed documents
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button variant="outlined" size="small" startIcon={<Refresh />} onClick={load} disabled={loading}>
            Refresh
          </Button>
          <Button variant="outlined" size="small" startIcon={<Add />} onClick={() => { setAddOpen(true); setAddError(null); }}>
            Add document
          </Button>
          <Button
            variant="contained"
            size="small"
            startIcon={<Add />}
            onClick={handleIngestFromConfig}
            disabled={ingesting}
          >
            {ingesting ? 'Ingesting…' : 'Ingest from config'}
          </Button>
        </Box>
      </Box>
      <Dialog open={addOpen} onClose={() => !addSubmitting && setAddOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add document</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              label="URL"
              value={addForm.source_url}
              onChange={(e) => setAddForm((f) => ({ ...f, source_url: e.target.value }))}
              placeholder="https://..."
              required
              fullWidth
              size="small"
            />
            <TextField label="Title" value={addForm.title} onChange={(e) => setAddForm((f) => ({ ...f, title: e.target.value }))} fullWidth size="small" />
            <TextField label="Source type" value={addForm.source_type} onChange={(e) => setAddForm((f) => ({ ...f, source_type: e.target.value }))} fullWidth size="small" placeholder="e.g. government, think_tank" />
            <TextField label="Source name" value={addForm.source_name} onChange={(e) => setAddForm((f) => ({ ...f, source_name: e.target.value }))} fullWidth size="small" />
            <TextField label="Document type" value={addForm.document_type} onChange={(e) => setAddForm((f) => ({ ...f, document_type: e.target.value }))} fullWidth size="small" placeholder="e.g. report, analysis" />
            <TextField label="Publication date" type="date" value={addForm.publication_date} onChange={(e) => setAddForm((f) => ({ ...f, publication_date: e.target.value }))} InputLabelProps={{ shrink: true }} fullWidth size="small" />
            {addError && <Typography color="error" variant="body2">{addError}</Typography>}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddOpen(false)} disabled={addSubmitting}>Cancel</Button>
          <Button variant="contained" onClick={handleAddSubmit} disabled={addSubmitting}>{addSubmitting ? 'Adding…' : 'Add'}</Button>
        </DialogActions>
      </Dialog>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        Documents ingested via API or <code>document_sources.ingest_urls</code>. Add URLs in orchestrator_governance.yaml then run Ingest from config.
      </Typography>
      {loading ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} variant="rectangular" height={72} sx={{ borderRadius: 1 }} />
          ))}
        </Box>
      ) : items.length === 0 ? (
        <Card variant="outlined">
          <CardContent>
            <Typography color="text.secondary">
              No processed documents yet. Use <strong>Ingest from config</strong> after adding URLs to{' '}
              <code>document_sources.ingest_urls</code>, or add documents via the API (POST /api/processed_documents).
            </Typography>
          </CardContent>
        </Card>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {items.map((doc) => (
            <Card key={doc.id} variant="outlined">
              <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                  {doc.title || doc.source_url || `Document #${doc.id}`}
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5, flexWrap: 'wrap' }}>
                  {doc.source_type && (
                    <Typography variant="caption" color="text.secondary">
                      {doc.source_type}
                    </Typography>
                  )}
                  {doc.publication_date && (
                    <Typography variant="caption" color="text.disabled">
                      {new Date(doc.publication_date).toLocaleDateString()}
                    </Typography>
                  )}
                  {doc.source_url && (
                    <MuiLink href={doc.source_url} target="_blank" rel="noopener" variant="caption">
                      Link
                    </MuiLink>
                  )}
                </Box>
              </CardContent>
            </Card>
          ))}
        </Box>
      )}
      <Snackbar
        open={!!message}
        autoHideDuration={6000}
        onClose={() => setMessage(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity={message?.severity ?? 'info'} onClose={() => setMessage(null)}>
          {message?.text}
        </Alert>
      </Snackbar>
    </Box>
  );
}
