import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import './index.css';

// The browser gate reads this stable marker and compares it with /api/health.
document.documentElement.dataset.buildSha = __OPENDATA_BUILD_SHA__;

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
