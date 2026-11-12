import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const base = env.BASE_PATH || '/';
  if (!base.startsWith('/') || !base.endsWith('/') || base.includes('..')) throw new Error('BASE_PATH deve começar e terminar com /');
  const proxyPrefix = `${base}api/rag`;
  const proxy = { [proxyPrefix]: { target: env.RAG_API_TARGET || 'http://127.0.0.1:8001', changeOrigin: true,
    timeout: 120000, proxyTimeout: 120000, rewrite: (path: string) => `/api/v1${path.slice(proxyPrefix.length)}` } };
  return {
    base,
    server: { port: 5173, strictPort: true, proxy },
    preview: { proxy },
    plugins: [react(), VitePWA({
      registerType: 'prompt', injectRegister: false,
      manifest: {
        id: base, name: 'FCTE Campus', short_name: 'FCTE Campus', lang: 'pt-BR',
        description: 'Explore os locais do campus Gama da UnB.',
        theme_color: '#003f7a', background_color: '#f6f8f7', display: 'standalone',
        start_url: base, scope: base,
        icons: [
          { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: 'icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
        navigateFallback: `${base}index.html`,
        navigateFallbackAllowlist: [new RegExp(`^${base.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`)],
        runtimeCaching: [], // Somente o shell: nenhum tile, GPS ou resposta de conhecimento.
        cleanupOutdatedCaches: true,
      },
      devOptions: { enabled: false },
    })],
    build: { target: 'es2022' },
  };
});
