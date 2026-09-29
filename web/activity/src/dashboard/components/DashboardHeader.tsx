// 대시보드 상단 타이틀과 마지막 갱신 시각 컴포넌트
import { formatTimeHHMM } from '../lib/time.ts'
import styles from './DashboardHeader.module.css'

export interface DashboardHeaderProps {
  lastUpdated: Date | null
}

export function DashboardHeader({ lastUpdated }: DashboardHeaderProps) {
  const formattedTime = lastUpdated ? formatTimeHHMM(lastUpdated) : '--:--'

  return (
    <header className={styles.header}>
      <h1 className={styles.title}>투기장 전적</h1>
      <span className={styles.lastUpdated}>마지막 갱신 {formattedTime}</span>
    </header>
  )
}
