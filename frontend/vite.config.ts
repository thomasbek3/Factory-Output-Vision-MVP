import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backendOrigin = process.env.VITE_BACKEND_ORIGIN || 'http://127.0.0.1:8080'
const backendWsOrigin = backendOrigin.replace(/^http/, 'ws')

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': backendOrigin,
      '/openapi.json': backendOrigin,
      '/ws': {
        target: backendWsOrigin,
        ws: true,
      },
    },
  },
  preview: {
    host: '127.0.0.1',
    port: 4173,
  },
})
