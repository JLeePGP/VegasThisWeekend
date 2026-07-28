import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

// Self-hosted so the page makes no third-party font requests and the CSP stays tight.
import '@fontsource-variable/inter';
import '@fontsource-variable/space-grotesk';

import './styles/tokens.css';
import './styles/app.css';

import App from './App';
import { SavedEventsProvider } from './store/savedEvents';
import { ToastProvider } from './store/toast';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <SavedEventsProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </SavedEventsProvider>
    </BrowserRouter>
  </StrictMode>,
);
