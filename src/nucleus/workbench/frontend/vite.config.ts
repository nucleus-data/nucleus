// Docs: https://vitejs.dev/config/  (vite==5.4.11)
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Forward /api/* to FastAPI (nucleus workbench up default port).
      '/api': {
        target: 'http://localhost:8765',
        changeOrigin: true,
      },
    },
  },
  build: {
    // Output goes to frontend/dist; Makefile / nucleus workbench up copies to static/.
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          query: ['@tanstack/react-query'],
          table: ['@tanstack/react-table'],
          flow: ['reactflow'],
          monaco: ['@monaco-editor/react'],
        },
      },
    },
  },
});
