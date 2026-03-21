/**
 * Audit-oriented provenance strip: source, timestamps, pipeline fields, deep links.
 */
import React from 'react';
import {
  Card,
  CardHeader,
  CardContent,
  Divider,
  Table,
  TableBody,
  TableRow,
  TableCell,
  Link,
  Typography,
} from '@mui/material';
import OpenInNew from '@mui/icons-material/OpenInNew';

export interface ProvenanceRow {
  label: string;
  value?: React.ReactNode;
}

interface ProvenancePanelProps {
  title?: string;
  subtitle?: string;
  rows: ProvenanceRow[];
}

function isExternalUrl(v: unknown): v is string {
  return typeof v === 'string' && /^https?:\/\//i.test(v);
}

export default function ProvenancePanel({
  title = 'Provenance & pipeline',
  subtitle,
  rows,
}: ProvenancePanelProps) {
  const filtered = rows.filter(
    (r) => r.value !== null && r.value !== undefined && r.value !== '',
  );
  if (filtered.length === 0) return null;

  return (
    <Card variant="outlined" sx={{ mb: 2 }}>
      <CardHeader
        title={title}
        subheader={subtitle}
        titleTypographyProps={{ variant: 'subtitle1', fontWeight: 600 }}
      />
      <Divider />
      <CardContent sx={{ '&:last-child': { pb: 2 }, pt: 2 }}>
        <Table size="small">
          <TableBody>
            {filtered.map((r) => (
              <TableRow key={r.label} sx={{ '&:last-child td': { border: 0 } }}>
                <TableCell
                  sx={{
                    color: 'text.secondary',
                    fontWeight: 600,
                    width: 160,
                    verticalAlign: 'top',
                    pl: 0,
                  }}
                >
                  {r.label}
                </TableCell>
                <TableCell sx={{ verticalAlign: 'top', wordBreak: 'break-word' }}>
                  {isExternalUrl(r.value) ? (
                    <Link
                      href={r.value}
                      target="_blank"
                      rel="noopener noreferrer"
                      underline="hover"
                      sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}
                    >
                      {r.value}
                      <OpenInNew sx={{ fontSize: 14 }} />
                    </Link>
                  ) : (
                    (r.value as React.ReactNode)
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

/** Build rows for a domain article detail view. */
export function articleProvenanceRows(
  article: Record<string, unknown> | null | undefined,
  domain: string,
  articleId: string | number,
): ProvenanceRow[] {
  if (!article) return [];
  const a = article;
  const published = (a.published_at || a.published_date) as string | undefined;
  const rows: ProvenanceRow[] = [
    { label: 'Article ID', value: String(articleId) },
    { label: 'Domain', value: domain },
    {
      label: 'Browse corpus',
      value: (
        <Link href={`/${domain}/articles`} underline="hover">
          All articles in domain
        </Link>
      ),
    },
    { label: 'Source', value: (a.source || a.source_domain) as string | undefined },
    { label: 'Published', value: published },
    { label: 'Category', value: a.category as string | undefined },
    { label: 'Quality score', value: a.quality_score != null ? String(a.quality_score) : undefined },
    { label: 'ML status', value: a.ml_processing_status as string | undefined },
    { label: 'Created (ingested)', value: a.created_at as string | undefined },
    { label: 'Original URL', value: a.url as string | undefined },
  ];
  const meta = a.metadata as Record<string, unknown> | undefined;
  if (meta?.feed_name) rows.push({ label: 'Feed', value: String(meta.feed_name) });
  if (meta?.feed_url) rows.push({ label: 'Feed URL', value: String(meta.feed_url) });
  return rows;
}

export function contextProvenanceRows(
  context: {
    id?: number;
    domain_key?: string;
    source_type?: string;
    created_at?: string | null;
    updated_at?: string | null;
    metadata?: Record<string, unknown> | null;
  },
  article?: { id?: number; title?: string; url?: string | null; source?: string | null; published_date?: string | null } | null,
  domainForRoutes?: string,
): ProvenanceRow[] {
  const d = domainForRoutes || context.domain_key || '';
  const rows: ProvenanceRow[] = [
    { label: 'Context ID', value: context.id != null ? String(context.id) : undefined },
    { label: 'Domain key', value: context.domain_key },
    { label: 'Source type', value: context.source_type },
    { label: 'Created', value: context.created_at ?? undefined },
    { label: 'Updated', value: context.updated_at ?? undefined },
  ];
  const meta = context.metadata || {};
  if (meta.url) rows.push({ label: 'Source URL', value: String(meta.url) });
  if (meta.feed_name) rows.push({ label: 'Feed', value: String(meta.feed_name) });
  if (meta.feed_url) rows.push({ label: 'Feed URL', value: String(meta.feed_url) });
  if (article?.id && d) {
    rows.push({
      label: 'Linked article',
      value: (
        <Link href={`/${d}/articles/${article.id}`} underline="hover">
          #{article.id} — {article.title || 'Open article'}
        </Link>
      ),
    });
  }
  if (article?.url) rows.push({ label: 'Article original URL', value: article.url });
  if (article?.source) rows.push({ label: 'Article source', value: article.source });
  if (article?.published_date) rows.push({ label: 'Article published', value: article.published_date });
  return rows;
}

export function entityDossierProvenanceRows(
  synthesis: {
    statistics?: { article_count?: number; has_dossier?: boolean };
    domain_key?: string;
    entity?: { id?: number };
  } | null,
  dossier: {
    compilation_date?: string | null;
    created_at?: string | null;
    metadata?: Record<string, unknown> | null;
  } | null,
  domain: string,
  canonicalEntityId: number,
): ProvenanceRow[] {
  const meta = dossier?.metadata || {};
  const conf = meta.average_confidence ?? meta.confidence_summary ?? meta.compilation_confidence;
  const rows: ProvenanceRow[] = [
    { label: 'Domain', value: domain },
    { label: 'Canonical entity id', value: String(canonicalEntityId) },
    {
      label: 'Synthesis article sample',
      value:
        synthesis?.statistics?.article_count != null
          ? `${synthesis.statistics.article_count} articles in synthesis payload`
          : undefined,
    },
    {
      label: 'Dossier compiled',
      value: dossier?.compilation_date ?? dossier?.created_at ?? undefined,
    },
    {
      label: 'Confidence / quality (metadata)',
      value: conf != null ? String(conf) : undefined,
    },
    {
      label: 'Note',
      value: (
        <Typography variant="body2" color="text.secondary" component="span">
          Use the Articles tab for per–article ids; dossier narrative is derived from those rows.
        </Typography>
      ),
    },
  ];
  return rows;
}

export function storylineProvenanceRows(
  storyline: Record<string, unknown> | null | undefined,
  domain: string,
  storylineId: string | number,
): ProvenanceRow[] {
  if (!storyline) return [];
  const s = storyline;
  return [
    { label: 'Storyline ID', value: String(storylineId) },
    { label: 'Domain', value: domain },
    { label: 'Status', value: s.status as string | undefined },
    { label: 'Articles linked', value: s.article_count != null ? String(s.article_count) : undefined },
    { label: 'Created', value: s.created_at as string | undefined },
    { label: 'Updated', value: s.updated_at as string | undefined },
    { label: 'ML processing', value: s.ml_processing_status as string | undefined },
    {
      label: 'Timeline',
      value: (
        <Link href={`/${domain}/storylines/${storylineId}/timeline`} underline="hover">
          Open chronological timeline
        </Link>
      ),
    },
  ];
}

export function timelineProvenanceRows(
  timeline: {
    storyline_id?: number;
    built_at?: string;
    event_count?: number;
    source_count?: number;
    merged_duplicate_events_count?: number;
    timeline_status?: string;
    time_span?: { start: string; end: string; days: number } | null;
  },
  domain: string,
  storylineId: string | number,
): ProvenanceRow[] {
  return [
    { label: 'Storyline ID', value: String(storylineId) },
    { label: 'Domain', value: domain },
    {
      label: 'Storyline',
      value: (
        <Link href={`/${domain}/storylines/${storylineId}`} underline="hover">
          Back to storyline
        </Link>
      ),
    },
    {
      label: 'Timeline status',
      value: timeline.timeline_status || (timeline.event_count ? 'ok' : 'empty'),
    },
    { label: 'Events in timeline', value: timeline.event_count != null ? String(timeline.event_count) : undefined },
    {
      label: 'Merged duplicate rows',
      value:
        timeline.merged_duplicate_events_count != null && timeline.merged_duplicate_events_count > 0
          ? String(timeline.merged_duplicate_events_count)
          : undefined,
    },
    { label: 'Distinct sources', value: timeline.source_count != null ? String(timeline.source_count) : undefined },
    {
      label: 'Time span',
      value: timeline.time_span
        ? `${timeline.time_span.start} → ${timeline.time_span.end} (${timeline.time_span.days} days)`
        : undefined,
    },
    { label: 'Timeline built at', value: timeline.built_at },
    {
      label: 'Note',
      value: (
        <Typography variant="body2" color="text.secondary" component="span">
          Events come from <code>public.chronological_events</code> (non-canonical rows). Extraction method is shown per
          event when expanded.
        </Typography>
      ),
    },
  ];
}
