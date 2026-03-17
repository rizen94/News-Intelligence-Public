/**
 * Processed document detail — original PDF link and extractions side by side.
 * Route: /:domain/investigate/documents/:documentId
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Box,
  Button,
  Card,
  CardContent,
  Skeleton,
  Typography,
  Link as MuiLink,
  Alert,
  Divider,
  Chip,
  Paper,
} from '@mui/material';
import ArrowBack from '@mui/icons-material/ArrowBack';
import OpenInNew from '@mui/icons-material/OpenInNew';
import PictureAsPdf from '@mui/icons-material/PictureAsPdf';
import { contextCentricApi } from '@/services/api/contextCentric';
import { useDomain } from '@/contexts/DomainContext';

type Section = { title?: string; content?: string; heading?: string; text?: string };
type Finding = { finding?: string; summary?: string; text?: string };
type Entity = string | { name?: string; type?: string };

export default function ProcessedDocumentDetailPage() {
  const { domain } = useDomain();
  const navigate = useNavigate();
  const { documentId } = useParams<{ documentId: string }>();
  const id = documentId ? parseInt(documentId, 10) : NaN;
  const [doc, setDoc] = useState<{
    id: number;
    title: string | null;
    source_url: string | null;
    source_type: string | null;
    source_name: string | null;
    publication_date: string | null;
    authors?: string[];
    document_type: string | null;
    extracted_sections?: Section[] | null;
    key_findings?: Finding[] | null;
    entities_mentioned?: Entity[] | null;
    citations?: unknown;
    metadata?: Record<string, unknown>;
    created_at?: string | null;
    updated_at?: string | null;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id || isNaN(id)) {
      setError('Invalid document ID');
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await contextCentricApi.getProcessedDocument(id);
      setDoc(data as typeof doc);
    } catch (e) {
      setError((e as Error)?.message ?? 'Failed to load document');
      setDoc(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <Box>
        <Skeleton variant="rectangular" height={40} sx={{ mb: 2, borderRadius: 1 }} />
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <Skeleton variant="rectangular" width="100%" height={400} sx={{ borderRadius: 1 }} />
          <Skeleton variant="rectangular" width="100%" height={400} sx={{ borderRadius: 1 }} />
        </Box>
      </Box>
    );
  }

  if (error || !doc) {
    return (
      <Box>
        <Button startIcon={<ArrowBack />} onClick={() => navigate(`/${domain}/investigate/documents`)} sx={{ mb: 2 }}>
          Back to documents
        </Button>
        <Alert severity="error">{error ?? 'Document not found'}</Alert>
      </Box>
    );
  }

  const sections: Section[] = Array.isArray(doc.extracted_sections) ? doc.extracted_sections : [];
  const findings: Finding[] = Array.isArray(doc.key_findings) ? doc.key_findings : [];
  const entities: Entity[] = Array.isArray(doc.entities_mentioned) ? doc.entities_mentioned : [];

  return (
    <Box>
      <Button startIcon={<ArrowBack />} onClick={() => navigate(`/${domain}/investigate/documents`)} sx={{ mb: 2 }}>
        Back to documents
      </Button>

      <Typography variant="h5" sx={{ fontWeight: 600, mb: 2 }}>
        {doc.title || `Document #${doc.id}`}
      </Typography>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2 }}>
        {/* Left: Original PDF and metadata */}
        <Card variant="outlined">
          <CardContent>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              Original document
            </Typography>
            {doc.source_url ? (
              <Button
                component={MuiLink}
                href={doc.source_url}
                target="_blank"
                rel="noopener"
                startIcon={<PictureAsPdf />}
                endIcon={<OpenInNew />}
                variant="outlined"
                fullWidth
                sx={{ justifyContent: 'flex-start', textAlign: 'left' }}
              >
                Open PDF in new tab
              </Button>
            ) : (
              <Typography variant="body2" color="text.secondary">
                No source URL
              </Typography>
            )}
            <Box sx={{ mt: 2 }}>
              {doc.source_type && (
                <Chip size="small" label={doc.source_type} sx={{ mr: 0.5, mb: 0.5 }} />
              )}
              {doc.document_type && (
                <Chip size="small" label={doc.document_type} variant="outlined" sx={{ mr: 0.5, mb: 0.5 }} />
              )}
              {doc.publication_date && (
                <Typography variant="caption" display="block" color="text.secondary">
                  Published: {new Date(doc.publication_date).toLocaleDateString()}
                </Typography>
              )}
              {doc.source_name && (
                <Typography variant="caption" display="block" color="text.secondary">
                  Source: {doc.source_name}
                </Typography>
              )}
              {doc.authors?.length ? (
                <Typography variant="caption" display="block" color="text.secondary">
                  Authors: {doc.authors.join(', ')}
                </Typography>
              ) : null}
              {doc.updated_at && (
                <Typography variant="caption" display="block" color="text.disabled" sx={{ mt: 1 }}>
                  Processed: {new Date(doc.updated_at).toLocaleString()}
                </Typography>
              )}
            </Box>
          </CardContent>
        </Card>

        {/* Right: Extractions */}
        <Card variant="outlined">
          <CardContent>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              Extractions
            </Typography>
            {sections.length === 0 && findings.length === 0 && entities.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No extractions yet. Process this document from the list (or run batch process) to extract sections and findings.
              </Typography>
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {sections.length > 0 && (
                  <Paper variant="outlined" sx={{ p: 1.5 }}>
                    <Typography variant="caption" fontWeight={600} color="text.secondary" display="block" gutterBottom>
                      Sections ({sections.length})
                    </Typography>
                    {sections.map((sec, i) => (
                      <Box key={i} sx={{ mb: 1.5 }}>
                        <Typography variant="subtitle2">
                          {sec.title ?? sec.heading ?? `Section ${i + 1}`}
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap' }}>
                          {(sec.content ?? sec.text ?? '').slice(0, 500)}
                          {((sec.content ?? sec.text)?.length ?? 0) > 500 ? '…' : ''}
                        </Typography>
                        <Divider sx={{ mt: 1 }} />
                      </Box>
                    ))}
                  </Paper>
                )}
                {findings.length > 0 && (
                  <Paper variant="outlined" sx={{ p: 1.5 }}>
                    <Typography variant="caption" fontWeight={600} color="text.secondary" display="block" gutterBottom>
                      Key findings ({findings.length})
                    </Typography>
                    <Box component="ul" sx={{ listStyle: 'disc', pl: 2, m: 0 }}>
                      {findings.map((f, i) => (
                        <Box key={i} component="li" sx={{ mb: 0.5 }}>
                          <Typography variant="body2">
                            {f.finding ?? f.summary ?? f.text ?? JSON.stringify(f)}
                          </Typography>
                        </Box>
                      ))}
                    </Box>
                  </Paper>
                )}
                {entities.length > 0 && (
                  <Paper variant="outlined" sx={{ p: 1.5 }}>
                    <Typography variant="caption" fontWeight={600} color="text.secondary" display="block" gutterBottom>
                      Entities mentioned ({entities.length})
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {entities.map((e, i) => (
                        <Chip
                          key={i}
                          size="small"
                          label={typeof e === 'string' ? e : (e?.name ?? JSON.stringify(e))}
                          variant="outlined"
                        />
                      ))}
                    </Box>
                  </Paper>
                )}
              </Box>
            )}
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
}
