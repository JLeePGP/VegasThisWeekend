import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

// Self-hosted so the page makes no third-party font requests and the CSP stays tight.
import '@fontsource-variable/inter';
import '@fontsource-variable/space-grotesk';

import './styles/tokens.css';
import './styles/app.css';

import {
  isStandalone,
  trackAppInstalled,
  trackSessionStart,
  trackStandaloneSession,
} from './analytics';
import App from './App';
import ErrorBoundary from './components/ErrorBoundary';
import { SavedEventsProvider } from './store/savedEvents';
import { ToastProvider } from './store/toast';

// The denominator for every other metric. Counted per page load rather than per
// navigation, since this is a single-page app and a route change is not a new visit.
trackSessionStart();

// Fired in addition to the line above, never instead of it, so `session_start` stays a
// true denominator and the standalone share is a ratio of it rather than a slice taken
// out of it.
if (isStandalone()) trackStandaloneSession();

// Android and desktop Chrome only. Safari has no equivalent, which is exactly why the
// counter above exists and why this one is labelled in the dashboard.
window.addEventListener('appinstalled', trackAppInstalled);

// The boundary sits outside the router and the providers on purpose: a crash while
// reading localStorage or resolving a route should still land on the fallback rather
// than an empty page.
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <SavedEventsProvider>
          <ToastProvider>
            <App />
          </ToastProvider>
        </SavedEventsProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
);
