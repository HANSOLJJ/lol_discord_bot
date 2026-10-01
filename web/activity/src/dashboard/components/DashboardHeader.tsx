// 대시보드 상단 타이틀과 마지막 갱신 시각 컴포넌트
import { formatTimeHHMM } from '../lib/time.ts'
import styles from './DashboardHeader.module.css'

export interface DashboardHeaderProps {
  /** 마지막으로 전적을 받아 온 시각. useHistoryData가 갱신하고, 아직 받기 전이면 null이다. */
  lastUpdated: Date | null
}

/** 대시보드 맨 위 제목과 마지막 갱신 시각(HH:MM). 받기 전에는 --:--을 보인다. */
export function DashboardHeader({ lastUpdated }: DashboardHeaderProps) {
  const formattedTime = lastUpdated ? formatTimeHHMM(lastUpdated) : '--:--'

  return (
    <header className={styles.header}>
      <h1 className={styles.title}>투기장 전적</h1>
      <span className={styles.lastUpdated}>마지막 갱신 {formattedTime}</span>
    </header>
  )
}
