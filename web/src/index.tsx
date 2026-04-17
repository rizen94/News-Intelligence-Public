import React from 'react';
import { createRoot } from 'react-dom/client';

import './index.css';
import App from './App';

const container = document.getElementById('root');
if (!container) {
  throw new Error(
    'News Intelligence: #root element not found — check index.html'
  );
}
const root = createRoot(container);

root.render(
  
    <App />
  
);
