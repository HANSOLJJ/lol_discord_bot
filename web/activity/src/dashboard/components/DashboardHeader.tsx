// 대시보드 상단 타이틀, 마지막 갱신 시각 및 새로고침 버튼 컴포넌트
import { formatTimeHHMM } from '../lib/time.ts'
import styles from './DashboardHeader.module.css'

export interface DashboardHeaderProps {
  lastUpdated: Date | null
  loading: boolean
  onRefresh: () => void
}

export function DashboardHeader({ lastUpdated, loading, onRefresh }: DashboardHeaderProps) {
  const formattedTime = lastUpdated ? formatTimeHHMM(lastUpdated) : '--:--'

  return (
    <header className={styles.header}>
      <h1 className={styles.title}>투기장 전적</h1>
      <div className={styles.actions}>
        <span className={styles.lastUpdated}>마지막 갱신 {formattedTime}</span>
        <button
          type="button"
          className={styles.refreshButton}
          aria-label="새로고침"
          onClick={onRefresh}
          disabled={loading}
        >
          <span className={loading ? styles.spin : undefined} aria-hidden="true">
            🔄
          </span>
        </button>
      </div>
    </header>
  )
}
