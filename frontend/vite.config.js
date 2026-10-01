import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8003',
        changeOrigin: true
      },
      '/profile': 'http://127.0.0.1:8003',
      '/permissions': 'http://127.0.0.1:8003',
      '/ask': 'http://127.0.0.1:8003',
      '/simulate': 'http://127.0.0.1:8003',
      '/feedback': 'http://127.0.0.1:8003',
      '/twin-knowledge': 'http://127.0.0.1:8003',
      '/audit-log': 'http://127.0.0.1:8003'
    }
  }
})
