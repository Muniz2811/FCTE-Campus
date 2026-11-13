import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const proxy = {
    '/api/v1': { target: env.RAG_API_TARGET || 'http://127.0.0.1:8001',
      changeOrigin: true, timeout: 120000, proxyTimeout: 120000 },
  };
  return {
    plugins: [react()],
    server: { port: 5173, strictPort: true, proxy },
    preview: { proxy },
    build: { target: 'es2022' },
  };
});
