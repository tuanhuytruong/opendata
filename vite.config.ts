import { execFileSync } from 'node:child_process';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { defineConfig } from 'vite';

const buildSha = process.env.OPENDATA_BUILD_SHA ?? execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();

export default defineConfig({
  define: { __OPENDATA_BUILD_SHA__: JSON.stringify(buildSha) },
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(__dirname, '.') } },
  server: {
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8020' },
  },
});
