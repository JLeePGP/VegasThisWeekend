import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

// Self-hosted so the page makes no third-party font requests and the CSP stays tight.
import '@fontsource-variable/inter';
import '@fontsource-variable/space-grotesk';

import './styles/tokens.css';
import './styles/app.css';

import App from './App';
import ErrorBoundary from './components/ErrorBoundary';
import { SavedEventsProvider } from './store/savedEvents';
import { ToastProvider } from './store/toast';

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
