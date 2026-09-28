// 통계 탭(개인, 시너지, 챔피언, 매치업)의 기간·인원선택·최소판수 컨트롤 컴포넌트
import type { PeriodOption, Session } from '../lib/types.ts'
import styles from './StatsFilters.module.css'

export interface StatsFiltersProps {
  period: string
  onPeriodChange: (p: string) => void
  periodOptions: PeriodOption[]
  sessions: Session[]
  summaryLabel: string
  gamesCount: number
  dateRange: string
  players: Record<string, string>
  selectedPlayerIds: string[]
  onTogglePlayer: (id: string) => void
  onClearPlayer: () => void
  maxSelection: number
  minGames: number
  onMinGamesChange: (n: number) => void
}

export function StatsFilters({
  period,
  onPeriodChange,
  periodOptions,
  sessions,
  summaryLabel,
  gamesCount,
  dateRange,
  players,
  selectedPlayerIds,
  onTogglePlayer,
  onClearPlayer,
  maxSelection,
  minGames,
  onMinGamesChange,
}: StatsFiltersProps) {
  const nonSessionOptions = periodOptions.filter((opt) => opt.group !== 'session')

  return (
    <div>
      {/* 상단 요약줄 */}
      <div className={styles.summary}>
        <b>{summaryLabel}</b> · <b>{gamesCount}판</b> · {dateRange}
      </div>

      <div className={styles.controls}>
        {/* 기간 선택 */}
        <div className={styles.periodGroup}>
          <label htmlFor="stats-period" className={styles.label}>
            기간
          </label>
          <select
            id="stats-period"
            className={styles.select}
            value={period}
            onChange={(e) => onPeriodChange(e.target.value)}
          >
            {nonSessionOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
            {sessions.length > 0 && (
              <optgroup label="세션별">
                {sessions.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.label}
                  </option>
                ))}
              </optgroup>
            )}
          </select>
        </div>

        {/* 인원 선택 칩 (최대 선택 수 제한 적용) */}
        <div className={styles.chipsRow} role="group" aria-label="인원 선택">
          <span className={styles.label}>인원 선택</span>
          <div className={styles.chipsList}>
            {Object.entries(players).map(([id, name]) => {
              const isSelected = selectedPlayerIds.includes(id)
              const isDisabled =
                maxSelection === 0 ||
                (selectedPlayerIds.length >= maxSelection && !isSelected)
              return (
                <button
                  key={id}
                  type="button"
                  className={`${styles.chip} ${isSelected ? styles.active : ''}`}
                  aria-pressed={isSelected}
                  disabled={isDisabled}
                  onClick={() => onTogglePlayer(id)}
                >
                  {name}
                </button>
              )
            })}
          </div>
          {selectedPlayerIds.length > 0 && (
            <button
              type="button"
              className={styles.clearBtn}
              onClick={onClearPlayer}
            >
              초기화
            </button>
          )}
        </div>

        {/* 최소 판수 슬라이더 */}
        <div className={styles.minGamesGroup}>
          <label htmlFor="min-games" className={styles.label}>
            최소 판수
          </label>
          <input
            type="range"
            id="min-games"
            className={styles.rangeInput}
            min={1}
            max={10}
            value={minGames}
            onChange={(e) => onMinGamesChange(Number(e.target.value))}
          />
          <span className={styles.minGamesVal}>{minGames}</span>
        </div>
      </div>
    </div>
  )
}
