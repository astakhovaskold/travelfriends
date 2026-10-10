import tailwind from '@tailwindcss/vite';
import {defineConfig} from 'vite';
import solid from 'vite-plugin-solid';

export default defineConfig({
  plugins: [
    solid(),
    tailwind(),
  ],
  base: '/',
  server: {
    port: 5173,
    strictPort: true,
    watch: {
      ignored: [
        '**/test-results/**',
        '**/playwright-report/**',
        '**/tests/snapshots/**',
      ],
    },
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  build: {
    target: 'es2022',
    assetsDir: 'assets',
  },
});
