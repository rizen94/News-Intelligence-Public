/**
 * v2 Admin audit checklist — localStorage, same items as classic.
 */
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { getDefaultDomainKey } from '../../../utils/domainHelper';

const STORAGE_KEY = 'newsintel_audit_checklist_v2';

type CheckState = Record<string, boolean>;

function loadState(): CheckState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw) as CheckState;
  } catch {
    /* ignore */
  }
  return {};
}

function saveState(s: CheckState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch {
    /* ignore */
  }
}

const ITEMS: { id: string; label: string; hint?: string }[] = [
  {
    id: 'v2-home',
    label: 'Scan /v2 home — hero + News cascade have real deks',
    hint: 'Reject membership-only bumps.',
  },
  {
    id: 'v2-reader',
    label: 'Open a storyline reader — summary, timeline, citations, dossier',
  },
  {
    id: 'v2-oneoffs',
    label: 'One-offs calendar — expected_on vs announced_on',
  },
  {
    id: 'classic',
    label: 'Spot-check classic /:domain SPA still loads',
  },
  {
    id: 'monitor',
    label: 'Admin Monitor + Work executed show live data',
  },
];

export default function AdminAuditPage() {
  const [state, setState] = useState<CheckState>(() => loadState());
  const domain = getDefaultDomainKey();

  const toggle = (id: string) => {
    const next = { ...state, [id]: !state[id] };
    setState(next);
    saveState(next);
  };

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Audit checklist</h1>
      <p className='v2-admin-muted'>
        Side-by-side review checklist. Classic audit remains at{' '}
        <Link to={`/${domain}/audit-checklist`}>/{domain}/audit-checklist</Link>.
      </p>
      <div className='v2-admin-panel'>
        <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
          {ITEMS.map(item => (
            <li key={item.id} style={{ marginBottom: '0.75rem' }}>
              <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start' }}>
                <input
                  type='checkbox'
                  checked={!!state[item.id]}
                  onChange={() => toggle(item.id)}
                />
                <span>
                  <strong>{item.label}</strong>
                  {item.hint ? (
                    <div className='v2-admin-muted'>{item.hint}</div>
                  ) : null}
                </span>
              </label>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
