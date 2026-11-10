import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Served under https://<host>/tg/ ; API calls go to same-origin /api/* which
// nginx rewrites to the FastAPI /v1/* routes. In dev we proxy the same way.
const apiTarget = process.env.VITE_DEV_API ?? 'http://localhost:8008';

export default defineConfig({
  // /tg/ behind our nginx; GitHub Pages builds pass VITE_BASE=/<repo>/
  base: process.env.VITE_BASE ?? '/tg/',
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, '/v1'),
      },
    },
  },
  test: {
    environment: 'node',
  },
});
