/**
 * Context detail — full content, metadata, and linked article summary.
 */
import React, { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card, CardHeader, CardContent, Typography, Button, Box, Skeleton, Chip, Divider, Link,
  Table, TableBody, TableRow, TableCell, List, ListItem, ListItemText,
} from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import ArrowBack from '@mui/icons-material/ArrowBack';
import OpenInNew from '@mui/icons-material/OpenInNew';
import { contextCentricApi, type Context } from '@/services/api/contextCentric';
import OrchestratorTagsEditor from '@/components/shared/OrchestratorTagsEditor/OrchestratorTagsEditor';
import ProvenancePanel, { contextProvenanceRows } from '@/components/ProvenancePanel/ProvenancePanel';
import ContextGroupingFeedbackCard from '@/components/ContextGroupingFeedback/ContextGroupingFeedbackCard';

interface LinkedArticle {
  id: number;
  title: string;
  url: string | null;
  source: string | null;
  summary: string | null;
  published_date: string | null;
  content: string | null;
}

type RelatedBundle = {
  topics: { id: number; name: string }[];
  storylines: { id: number; title: string | null }[];
};

type ContextWithArticle = Context & { article?: LinkedArticle | null; related?: RelatedBundle };

function stripHtml(html: string): string {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  return (doc.body.textContent || '').trim();
}

function hasHtml(text: string): boolean {
  return /<[a-z][\s\S]*?>/i.test(text);
}

function cleanContent(raw: string): string {
  return hasHtml(raw) ? stripHtml(raw) : raw;
}

const META_LABELS: Record<string, string> = {
  url: 'Source URL',
  published_at: 'Published',
  source: 'Source',
  domain_key: 'Domain',
  source_type: 'Type',
  author: 'Author',
  feed_url: 'Feed URL',
  feed_name: 'Feed',
  category: 'Category',
  language: 'Language',
};

function formatMetaLabel(key: string): string {
  return META_LABELS[key] ?? key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function isUrl(v: unknown): v is string {
  return typeof v === 'string' && /^https?:\/\//i.test(v);
}

function isDateString(v: unknown): boolean {
  if (typeof v !== 'string') return false;
  return /^\d{4}-\d{2}-\d{2}/.test(v) && !Number.isNaN(Date.parse(v));
}

function formatMetaValue(key: string, val: unknown): React.ReactNode {
  if (isUrl(val)) {
    return (
      <Link href={val} target="_blank" rel="noopener" underline="hover" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.3, wordBreak: 'break-all' }}>
        {val} <OpenInNew sx={{ fontSize: 14 }} />
      </Link>
    );
  }
  if (isDateString(val)) {
    return new Date(val as string).toLocaleString(undefined, {
      weekday: 'short', month: 'short', day: 'numeric', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  }
  if (typeof val === 'string') return val;
  return JSON.stringify(val);
}

export default function ContextDetailPage() {
  const { domain, id } = useParams<{ domain: string; id: string }>();
  const navigate = useNavigate();
  const [context, setContext] = useState<ContextWithArticle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    const numId = parseInt(id, 10);
    if (Number.isNaN(numId)) {
      setLoading(false);
      setError('Invalid context id.');
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    contextCentricApi.getContext(numId)
      .then((data) => { if (!cancelled) setContext(data); })
      .catch((e) => { if (!cancelled) setError(e?.message ?? 'Failed to load context.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [id]);

  const article = context?.article;
  const meta = context?.metadata as Record<string, unknown> | null;

  const contextBody = useMemo(
    () => (context?.content ? cleanContent(context.content) : null),
    [context?.content],
  );
  const articleBody = useMemo(
    () => (article?.content ? cleanContent(article.content) : null),
    [article?.content],
  );
  const articleSummary = useMemo(
    () => (article?.summary ? cleanContent(article.summary) : null),
    [article?.summary],
  );

  const date = context?.created_at
    ? new Date(context.created_at).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    : null;

  if (!domain) return null;

  return (
    <Box>
      <Button startIcon={<ArrowBack />} onClick={() => navigate(`/${domain}/discover`)} sx={{ mb: 2 }}>
        Back to Discover
      </Button>

      {loading && <Skeleton variant="rectangular" height={300} sx={{ borderRadius: 1 }} />}

      {error && !loading && (
        <Typography color="error">{error}</Typography>
      )}

      {!loading && context && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <ProvenancePanel
            title="Provenance & pipeline"
            subtitle="How this context is grounded in the corpus"
            rows={contextProvenanceRows(context, article ?? null, domain)}
          />

          {context.related && (context.related.topics?.length > 0 || context.related.storylines?.length > 0) && (
            <Card variant="outlined">
              <CardHeader
                title="Cross-entity links (same article)"
                subheader="Topics and storylines that reference the linked article — for manual consistency checks"
                titleTypographyProps={{ variant: 'subtitle1', fontWeight: 600 }}
              />
              <Divider />
              <CardContent sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {context.related.topics?.length > 0 && (
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>Topics</Typography>
                    <List dense disablePadding>
                      {context.related.topics.map((t) => (
                        <ListItem key={t.id} disablePadding sx={{ py: 0.25 }}>
                          <ListItemText
                            primary={
                              <Link component={RouterLink} to={`/${domain}/topics`} underline="hover">
                                #{t.id} — {t.name}
                              </Link>
                            }
                          />
                        </ListItem>
                      ))}
                    </List>
                  </Box>
                )}
                {context.related.storylines?.length > 0 && (
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>Storylines</Typography>
                    <List dense disablePadding>
                      {context.related.storylines.map((s) => (
                        <ListItem key={s.id} disablePadding sx={{ py: 0.25 }}>
                          <ListItemText
                            primary={
                              <Link component={RouterLink} to={`/${domain}/storylines/${s.id}`} underline="hover">
                                #{s.id} — {s.title || '(untitled)'}
                              </Link>
                            }
                          />
                        </ListItem>
                      ))}
                    </List>
                  </Box>
                )}
              </CardContent>
            </Card>
          )}

          {/* Context card */}
          <Card variant="outlined">
            <CardHeader
              title={context.title || '(No title)'}
              subheader={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', mt: 0.5 }}>
                  <Chip label={context.source_type} size="small" variant="outlined" />
                  <Chip label={context.domain_key} size="small" color="primary" variant="outlined" />
                  {date && <Typography variant="caption" color="text.secondary">{date}</Typography>}
                </Box>
              }
            />
            <CardContent>
              {contextBody ? (
                <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
                  {contextBody}
                </Typography>
              ) : (
                <Typography color="text.secondary">No content available.</Typography>
              )}
            </CardContent>
          </Card>

          {/* Linked article card */}
          {article && (
            <Card variant="outlined">
              <CardHeader
                title="Source article"
                titleTypographyProps={{ variant: 'subtitle1', fontWeight: 600 }}
              />
              <Divider />
              <CardContent>
                <Typography variant="h6" gutterBottom>{article.title}</Typography>

                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5, flexWrap: 'wrap' }}>
                  {article.source && <Chip label={article.source} size="small" />}
                  {article.published_date && (
                    <Typography variant="caption" color="text.secondary">
                      {new Date(article.published_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                    </Typography>
                  )}
                  {article.url && (
                    <Link href={article.url} target="_blank" rel="noopener" underline="hover" variant="caption" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.3 }}>
                      Open original <OpenInNew sx={{ fontSize: 14 }} />
                    </Link>
                  )}
                </Box>

                {articleSummary && (
                  <Box sx={{ mb: 2, p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}>
                    <Typography variant="subtitle2" gutterBottom>Summary</Typography>
                    <Typography variant="body2" sx={{ lineHeight: 1.6 }}>{articleSummary}</Typography>
                  </Box>
                )}

                {articleBody && (
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>Article text</Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                      {articleBody}
                    </Typography>
                  </Box>
                )}
              </CardContent>
            </Card>
          )}

          {context.id != null && <ContextGroupingFeedbackCard contextId={context.id} />}

          {/* Orchestrator tags */}
          {context.id && (
            <Card variant="outlined">
              <CardHeader title="Story prioritization" titleTypographyProps={{ variant: 'subtitle1', fontWeight: 600 }} />
              <Divider />
              <CardContent>
                <OrchestratorTagsEditor
                  tags={Array.isArray(meta?.orchestrator_tags) ? (meta.orchestrator_tags as string[]) : []}
                  onSave={async (tags) => {
                    const updated = await contextCentricApi.updateContext(context.id!, { orchestrator_tags: tags });
                    setContext((prev) => (prev ? { ...prev, metadata: updated.metadata ?? prev.metadata } : null));
                  }}
                />
              </CardContent>
            </Card>
          )}

          {/* Metadata card */}
          {meta && Object.keys(meta).filter((k) => k !== 'orchestrator_tags').length > 0 && (
            <Card variant="outlined">
              <CardHeader title="Metadata" titleTypographyProps={{ variant: 'subtitle1', fontWeight: 600 }} />
              <Divider />
              <CardContent sx={{ '&:last-child': { pb: 2 } }}>
                <Table size="small">
                  <TableBody>
                    {Object.entries(meta)
                      .filter(([key]) => key !== 'orchestrator_tags')
                      .map(([key, val]) => (
                      <TableRow key={key} sx={{ '&:last-child td': { border: 0 } }}>
                        <TableCell sx={{ color: 'text.secondary', fontWeight: 500, width: 140, whiteSpace: 'nowrap', verticalAlign: 'top', pl: 0 }}>
                          {formatMetaLabel(key)}
                        </TableCell>
                        <TableCell sx={{ verticalAlign: 'top' }}>
                          {formatMetaValue(key, val)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </Box>
      )}
    </Box>
  );
}
