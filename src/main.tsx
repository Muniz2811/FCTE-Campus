import React from 'react';
import ReactDOM from 'react-dom/client';
import { MotionConfig } from 'motion/react';
import 'leaflet/dist/leaflet.css';
import './design/tokens.css';
import './design/layout.css';
import './design/panels.css';
import './design/map.css';
import './design/chat.css';
import { App } from './app/App';
import { AppErrorBoundary } from './app/AppErrorBoundary';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><AppErrorBoundary><MotionConfig reducedMotion="user"><App /></MotionConfig></AppErrorBoundary></React.StrictMode>,
);
