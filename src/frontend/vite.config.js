import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The FastAPI backend serves `dist/` from the origin root, so asset URLs must
// be absolute: a relative base breaks nested routes like /projects/mathtools,
// where "./assets/x.js" would resolve to "/projects/assets/x.js".
// In development, /api is proxied to uvicorn on 8765.
export default defineConfig({
  plugins: [react()],
  base: '/',
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
