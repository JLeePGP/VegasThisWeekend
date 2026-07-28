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
});
