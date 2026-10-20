import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    environmentOptions: { jsdom: { url: 'http://127.0.0.1:8000/' } },
    include: ['src/**/*.test.tsx'],
    fileParallelism: false,
    testTimeout: 30_000,
    hookTimeout: 20_000,
    pool: 'forks',
  },
});
