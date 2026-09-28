// 대시보드 6개 탭(대전 기록, 개인, 2인 시너지, 3인 시너지, 챔피언, 3:3 매치업) 네비게이션 컴포넌트
import styles from './DashboardTabs.module.css'

export interface TabItem {
  key: string
  label: string
}

const DASHBOARD_TABS: TabItem[] = [
  { key: 'history', label: '대전 기록' },
  { key: 'player', label: '개인' },
  { key: 'pair', label: '2인 시너지' },
  { key: 'trio', label: '3인 시너지' },
  { key: 'champ', label: '챔피언' },
  { key: 'matchup', label: '3:3 매치업' },
]

export interface DashboardTabsProps {
  activeTab: string
  onTabChange: (key: string) => void
}

export function DashboardTabs({ activeTab, onTabChange }: DashboardTabsProps) {
  return (
    <nav className={styles.tabNav} aria-label="대시보드 탭 목록">
      {DASHBOARD_TABS.map((tab) => {
        const isActive = activeTab === tab.key
        return (
          <button
            key={tab.key}
            type="button"
            className={`${styles.tabItem} ${isActive ? styles.active : ''}`}
            aria-current={isActive ? 'page' : undefined}
            onClick={() => onTabChange(tab.key)}
          >
            {tab.label}
          </button>
        )
      })}
    </nav>
  )
}
