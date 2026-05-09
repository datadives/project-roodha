import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Ensures assets load correctly relative to the server root
  base: './',
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('aws-amplify') || id.includes('lucide-react')) {
              return 'vendor'
            }
            if (id.includes('recharts')) {
              return 'charts'
            }
          }
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
  },
})
