import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The admin panel is never deployed. It runs here, on John's machine, and talks to
// whichever API VITE_API_BASE_URL points at — local backend or the live Railway one.
// Port 5174 keeps it clear of the public app on 5173, and both are in the API's CORS
// allowlist.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    // Deliberately loopback-only: no reason for an internal tool to be on the LAN.
    host: '127.0.0.1',
    strictPort: true,
  },
});
