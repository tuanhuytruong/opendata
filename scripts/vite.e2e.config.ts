import config from '../vite.config';

export default {
  ...config,
  server: {
    ...config.server,
    port: Number(process.env.E2E_PORT ?? 5180),
    strictPort: true,
    proxy: { '/api': 'http://127.0.0.1:8021' },
  },
};
