/**
 * Weekly / ad-hoc data audit checklist — links into corpus, pipeline, and docs.
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Checkbox,
  FormControlLabel,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Button,
  Divider,
  Grid,
  Chip,
} from '@mui/material';
import ChecklistIcon from '@mui/icons-material/Checklist';
import { useDomainRoute } from '../../hooks/useDomainRoute';

const STORAGE_KEY = 'newsintel_audit_checklist_v1';

type CheckState = Record<string, boolean>;

function loadState(): CheckState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw) as CheckState;
  } catch { /* ignore */ }
  return {};
}

function saveState(s: CheckState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch { /* ignore */ }
}

const ITEMS: { id: string; label: string; hint?: string }[] = [
  { id: 'discover', label: 'Scan Discover (contexts + entities) with pagination', hint: 'Spot-check new contexts and entity profiles.' },
  { id: 'articles', label: 'Sample Articles list — provenance strip and processing fields', hint: 'Open random articles; confirm source URL and quality_score.' },
  { id: 'storyline', label: 'Open an active Storyline — audit card + timeline', hint: 'Compare article count vs timeline events; note empty timelines.' },
  { id: 'context', label: 'Open a Context — cross-links (topics/storylines) + grouping feedback', hint: 'Verify article↔topic↔storyline matrix for one article.' },
  { id: 'dossier', label: 'Entity dossier — provenance + source articles list', hint: 'Confirm compile date and cited article ids.' },
  { id: 'monitor', label: 'Monitor — phases, backlog, collection health', hint: 'Confirm RSS and automation running.' },
  { id: 'docs', label: 'Read UI_PIPELINE_AUDIT_GUIDE (repo doc)', hint: 'Align the team on what “audit” means this week.' },
];

const LAYER_CARDS: Array<{
  title: string;
  layer: string;
  hint: string;
  links: Array<{ label: string; path: string }>;
}> = [
  {
    title: 'Ingest',
    layer: 'Sources and freshness',
    hint: 'Check feed status and collection health before deeper audits.',
    links: [{ label: 'RSS feeds', path: '/rss_feeds' }, { label: 'Monitor', path: '/monitor' }],
  },
  {
    title: 'Corpus',
    layer: 'Raw records',
    hint: 'Spot-check capture quality and source metadata.',
    links: [{ label: 'Articles', path: '/articles' }, { label: 'Processed docs', path: '/investigate/documents' }],
  },
  {
    title: 'Story and time',
    layer: 'Storyline and timeline integrity',
    hint: 'Compare article counts, chronological events, and empty-timeline state.',
    links: [{ label: 'Storylines', path: '/storylines' }, { label: 'Events', path: '/events' }],
  },
  {
    title: 'Cross-cutting',
    layer: 'Context and entities',
    hint: 'Validate context-topic-storyline agreement and entity dossier provenance.',
    links: [{ label: 'Discover', path: '/discover' }, { label: 'Investigate entities', path: '/investigate/entities' }],
  },
];

export default function AuditChecklistPage() {
  const { domain } = useDomainRoute();
  const navigate = useNavigate();
  const [checks, setChecks] = useState<CheckState>(() => loadState());

  const toggle = (id: string) => {
    setChecks((prev) => {
      const next = { ...prev, [id]: !prev[id] };
      saveState(next);
      return next;
    });
  };

  const reset = () => {
    setChecks({});
    saveState({});
  };

  const base = `/${domain}`;

  return (
    <Box sx={{ maxWidth: 720 }}>
      <Typography variant="h5" sx={{ fontWeight: 600, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
        <ChecklistIcon color="primary" /> Data audit checklist
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Run through this list as the corpus grows. Progress is saved in this browser ({STORAGE_KEY}).
      </Typography>

      <Grid container spacing={2} sx={{ mb: 2 }}>
        {LAYER_CARDS.map((card) => (
          <Grid item xs={12} md={6} key={card.title}>
            <Card variant="outlined" sx={{ height: '100%' }}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>{card.title}</Typography>
                  <Chip size="small" label={card.layer} variant="outlined" />
                </Box>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                  {card.hint}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  {card.links.map((link) => (
                    <Button key={link.path} size="small" variant="outlined" onClick={() => navigate(`${base}${link.path}`)}>
                      {link.label}
                    </Button>
                  ))}
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Card variant="outlined" sx={{ mb: 2 }}>
        <CardContent>
          <List dense disablePadding>
            {ITEMS.map((item) => (
              <ListItem key={item.id} disablePadding sx={{ alignItems: 'flex-start', py: 0.5 }}>
                <ListItemIcon sx={{ minWidth: 42, mt: 0.5 }}>
                  <Checkbox
                    edge="start"
                    checked={!!checks[item.id]}
                    onChange={() => toggle(item.id)}
                  />
                </ListItemIcon>
                <ListItemText
                  primary={item.label}
                  secondary={item.hint}
                  primaryTypographyProps={{ variant: 'body2', fontWeight: 500 }}
                />
              </ListItem>
            ))}
          </List>
          <Divider sx={{ my: 2 }} />
          <Button size="small" onClick={reset} color="inherit">
            Reset checklist
          </Button>
        </CardContent>
      </Card>

      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        Quick links ({domain})
      </Typography>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, alignItems: 'flex-start' }}>
        <Button size="small" variant="text" onClick={() => navigate(`${base}/discover`)}>Discover</Button>
        <Button size="small" variant="text" onClick={() => navigate(`${base}/articles`)}>Articles</Button>
        <Button size="small" variant="text" onClick={() => navigate(`${base}/storylines`)}>Storylines</Button>
        <Button size="small" variant="text" onClick={() => navigate(`${base}/investigate/entities`)}>Entities</Button>
        <Button size="small" variant="text" onClick={() => navigate(`${base}/monitor`)}>Monitor</Button>
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
          Reference: <code>docs/UI_PIPELINE_AUDIT_GUIDE.md</code> (listed in <code>docs/DOCS_INDEX.md</code>).
        </Typography>
      </Box>
    </Box>
  );
}
