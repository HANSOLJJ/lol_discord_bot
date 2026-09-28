// 전적 대시보드의 React 렌더링 진입점
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { DashboardApp } from './DashboardApp.tsx'

const rootEl = document.getElementById('root')
if (rootEl) {
  createRoot(rootEl).render(
    <StrictMode>
      <DashboardApp />
    </StrictMode>,
  )
}
