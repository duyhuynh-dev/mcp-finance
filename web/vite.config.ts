import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [tailwindcss(), react()],
  server: {
    // Explicit bind avoids some IPv6 localhost (::1) vs IPv4 issues.
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      // Finance API (avoid clashing with other apps on 8000)
      '/api': 'http://127.0.0.1:8001',
    },
  },
})
