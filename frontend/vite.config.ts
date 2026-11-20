import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In dev, the React app runs on :5173 and proxies /api to the FastAPI backend on :8000.
// In production, FastAPI serves the built app itself, so relative /api URLs just work.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: {
    // The offline snapshot (~380 KB) is its own lazily-imported chunk; it is only fetched in offline mode.
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        // Split big third-party libraries into separate, long-cacheable chunks.
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (/[\\/]node_modules[\\/](leaflet|react-leaflet|@react-leaflet)[\\/]/.test(id)) return 'vendor-leaflet';
          if (/[\\/]node_modules[\\/](recharts|d3-[^\\/]+|victory-vendor|recharts-scale|decimal\.js-light)[\\/]/.test(id)) return 'vendor-recharts';
          if (/[\\/]node_modules[\\/](react|react-dom|react-router|react-router-dom|@remix-run|scheduler)[\\/]/.test(id)) return 'vendor-react';
          return undefined;
        },
      },
    },
  },
})
