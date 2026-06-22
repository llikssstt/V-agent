import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/chat': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/memory': 'http://127.0.0.1:8000',
      '/todos': 'http://127.0.0.1:8000'
    }
  }
})

