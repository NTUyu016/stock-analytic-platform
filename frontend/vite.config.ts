import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // 開發時模擬 Caddy 的 /api/* 反向代理（tech-stack.md §8）。
    // 生產環境沒有這層——Caddy 直接發 dist/ 靜態檔並代理 /api/*。
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
