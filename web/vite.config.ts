import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:9091',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: '../src/inq/web',
    emptyOutDir: true,
    sourcemap: false,
  },
})
