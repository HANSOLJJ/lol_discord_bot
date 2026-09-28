import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const __dirname = dirname(fileURLToPath(import.meta.url))

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // 개발 터널(lol-dev.hansoljj.com)이 IPv4 127.0.0.1:5173으로 연결하므로 주소와 포트를 고정한다.
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    allowedHosts: ['lol-dev.hansoljj.com'],
    // Discord 프록시·터널을 거치면 HMR 웹소켓도 https 기본 포트로 들어온다.
    hmr: { clientPort: 443 },
    // 봇의 액티비티 서버(127.0.0.1:8790)로 HTTP와 WebSocket을 함께 넘긴다.
    proxy: {
      '/pick-api': { target: 'http://127.0.0.1:8790', ws: true },
      '/history_data.json': {
        target: 'https://arena.hansoljj.com',
        changeOrigin: true,
      },
      '/ddragon': {
        target: 'https://ddragon.leagueoflegends.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/ddragon/, ''),
      },
    },
  },
  build: {
    rollupOptions: {
      input: {
        activity: resolve(__dirname, 'index.html'),
        dashboard: resolve(__dirname, 'dashboard.html'),
      },
    },
  },
  // 첫 접속 중에 SDK를 최적화하면 Vite가 페이지를 새로고침해 Discord와의 SDK 연결 확인이 끊기고
  // 액티비티가 "연결 중"에 멈춘다. 서버 시작 때 미리 최적화해 둔다.
  optimizeDeps: { include: ['@discord/embedded-app-sdk'] },
})

