import React from 'react';
import { createRoot } from 'react-dom/client';

import './index.css';
import App from './App';

// After a deploy, open tabs can keep an old module graph that points at deleted
// hashed chunks. Vite fires this when a lazy import 404s — force a one-shot reload.
if (typeof window !== 'undefined') {
  window.addEventListener('vite:preloadError', event => {
    event.preventDefault();
    const key = 'ni_vite_preload_reload_ts';
    try {
      const last = Number(sessionStorage.getItem(key) || '0');
      if (Date.now() - last > 15_000) {
        sessionStorage.setItem(key, String(Date.now()));
        window.location.reload();
      }
    } catch {
      window.location.reload();
    }
  });
}

const container = document.getElementById('root');
if (!container) {
  throw new Error(
    'News Intelligence: #root element not found — check index.html'
  );
}
const root = createRoot(container);

root.render(<App />);
