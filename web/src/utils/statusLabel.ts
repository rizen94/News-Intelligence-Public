/**
 * Map engineering status enums to reader-facing labels.
 */
const STATUS_LABELS: Record<string, string> = {
  closed_thin: 'Closed (thin)',
  forming: 'Waiting for events',
  cooling: 'Quiet',
  dormant: 'Dormant',
  concluded: 'Concluded',
  active: 'Active',
  quarantined: 'Set aside',
  ready_for_editor: 'Ready to publish',
  in_editing: 'In editing',
  in_research: 'In research',
  in_narrative: 'In narrative',
  in_reduction: 'In reduction',
  published: 'Published',
  draft: 'Draft',
  blocked: 'Blocked',
  hypothesized: 'Provisional',
  candidate: 'Candidate',
  established: 'Established',
};

export function statusLabel(raw: string | null | undefined): string {
  if (!raw) return '';
  const key = String(raw).trim();
  return STATUS_LABELS[key] || STATUS_LABELS[key.toLowerCase()] || key.replace(/_/g, ' ');
}
