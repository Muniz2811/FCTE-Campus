import React from 'react';
import ReactDOM from 'react-dom/client';
import { MotionConfig } from 'motion/react';
import './design/tokens.css';
import './design/chat.css';
import './design/evaluation.css';
import './design/grade.css';
import './design/workspace.css';
import './design/liquid-glass.css';
import './design/campus-glass.css';
import './design/app-glass.css';
import './design/importacao.css';
import { App } from './app/App';
import { AppErrorBoundary } from './app/AppErrorBoundary';

// Retira registros da versão anterior, sem instalar service worker ou cache offline.
if ('serviceWorker' in navigator) {
  const scope = new URL(import.meta.env.BASE_URL, location.origin).href;
  void navigator.serviceWorker.getRegistrations().then(registrations => Promise.all(
    registrations.filter(registration => registration.scope === scope).map(registration => registration.unregister()),
  )).catch(() => {});
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><AppErrorBoundary><MotionConfig reducedMotion="user"><App /></MotionConfig></AppErrorBoundary></React.StrictMode>,
);
