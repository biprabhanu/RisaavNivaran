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
    chunkSizeWarningLimit: 1500,
  },
})
