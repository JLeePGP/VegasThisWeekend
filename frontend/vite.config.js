import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Bind to all interfaces so the app can be opened from a phone on the same network,
    // which is the only honest way to test a touch-first product.
    host: true,
  },
  build: {
    target: 'es2022',
    sourcemap: true,
  },
  // `npm run preview` serves the production build. Used for tunnelled demo builds, where
  // the API is proxied under /api so the whole app is one origin: no CORS, and an https
  // origin means the native share sheet and clipboard actually work.
  //
  // Production on Netlify does NOT use this — there the frontend calls the Railway API
  // directly via VITE_API_BASE_URL, and CORS applies.
  preview: {
    port: 4173,
    host: true,
    // A tunnel arrives with a *.trycloudflare.com Host header, which Vite rejects by
    // default as DNS-rebinding protection. Allow just that suffix, not everything.
    allowedHosts: ['.trycloudflare.com', 'localhost', '127.0.0.1'],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
});
