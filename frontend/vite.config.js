import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // Set base to '/Breathesg/' for GitHub Pages deployment
  // In local dev, this is overridden by VITE_BASE_URL or defaults to '/'
  base: process.env.GITHUB_ACTIONS ? '/Breathesg/' : '/',
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
