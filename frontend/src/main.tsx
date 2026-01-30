import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { initErrorTracking } from '@/services/errorTracking';
import { registerSW } from 'virtual:pwa-register';
import '@/i18n';

// Initialize error tracking
initErrorTracking();

// Register service worker for PWA support
if ('serviceWorker' in navigator) {
  registerSW({
    onNeedRefresh() {
      console.log('New content available, please refresh.');
    },
    onOfflineReady() {
      console.log('App ready to work offline.');
    },
  });
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
