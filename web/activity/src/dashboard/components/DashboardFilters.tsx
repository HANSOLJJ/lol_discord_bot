// 챔피언 검색창, 정렬, 같은 팀 플레이어 칩(최대 3개), 승패 요약 및 모바일 접기/펼치기 필터 컴포넌트
import { useState } from 'react'
import type { PeriodOption, RecordSummary, Session, SortOrder } from '../lib/types.ts'
import styles from './DashboardFilters.module.css'

export interface DashboardFiltersProps {
  period: string
  defaultPeriod: string
  onPeriodChange: (p: string) => void
  periodOptions: PeriodOption[]
  sessions: Session[]
  sortOrder: SortOrder
  onSortOrderChange: (order: SortOrder) => void
  players: Record<string, string>
  selectedPlayerIds: string[]
  onTogglePlayer: (id: string) => void
  championQuery: string
  onChampionQueryChange: (q: string) => void
  totalCount: number
  filteredCount: number
  recordSummary: RecordSummary | null
  onResetFilters: () => void
}

export function DashboardFilters({
  period,
  defaultPeriod,
  onPeriodChange,
  periodOptions,
  sessions,
  sortOrder,
  onSortOrderChange,
  players,
  selectedPlayerIds,
  onTogglePlayer,
  championQuery,
  onChampionQueryChange,
  totalCount,
  filteredCount,
  recordSummary,
  onResetFilters,
}: DashboardFiltersProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  const nonSessionOptions = periodOptions.filter((opt) => opt.group !== 'session')

  // 기간·정렬 기본값을 제외한 켜진 조건 수 계산
  let activeCollapsibleCount = 0
  if (period !== defaultPeriod) activeCollapsibleCount++
  if (sortOrder !== 'desc') activeCollapsibleCount++
  activeCollapsibleCount += selectedPlayerIds.length

  const hasActiveFilters =
    selectedPlayerIds.length > 0 ||
    championQuery.trim() !== '' ||
    period !== defaultPeriod ||
    sortOrder !== 'desc'

  return (
    <section className={styles.filterContainer} aria-label="대전 기록 필터">
      {/* 챔피언 검색창 및 모바일 필터 펼침 토글 줄 */}
      <div className={styles.headerRow}>
        <div className={styles.searchGroup}>
          <input
            type="search"
            className={styles.searchInput}
            placeholder="챔피언 검색"
            aria-label="챔피언 검색"
            value={championQuery}
            onChange={(e) => onChampionQueryChange(e.target.value)}
          />
        </div>

        <button
          type="button"
          className={styles.filterToggleButton}
          aria-expanded={isExpanded}
          onClick={() => setIsExpanded((prev) => !prev)}
        >
          <span>필터{activeCollapsibleCount > 0 ? ` ${activeCollapsibleCount}` : ''}</span>
          <span aria-hidden="true">{isExpanded ? '▲' : '▼'}</span>
        </button>
      </div>

      {/* 펼쳐지는 필터 영역 (기간, 정렬, 플레이어 칩) */}
      <div className={`${styles.drawer} ${isExpanded ? styles.drawerOpen : ''}`}>
        <div className={styles.selectsRow}>
          {/* 기간 선택 드롭다운 */}
          <div className={styles.selectGroup}>
            <label htmlFor="period-select" className={styles.selectLabel}>
              기간
            </label>
            <select
              id="period-select"
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

          {/* 정렬 선택 드롭다운 */}
          <div className={styles.selectGroup}>
            <label htmlFor="sort-select" className={styles.selectLabel}>
              정렬
            </label>
            <select
              id="sort-select"
              className={styles.select}
              value={sortOrder}
              onChange={(e) => onSortOrderChange(e.target.value as SortOrder)}
            >
              <option value="desc">최신순</option>
              <option value="asc">오래된 순</option>
            </select>
          </div>
        </div>

        {/* 플레이어 칩 목록 (최대 3개 선택) */}
        <div className={styles.chipsWrapper} role="group" aria-label="플레이어 필터 (같은 팀)">
          <span className={styles.chipLabel}>플레이어:</span>
          {Object.entries(players).map(([id, name]) => {
            const isSelected = selectedPlayerIds.includes(id)
            const isDisabled = !isSelected && selectedPlayerIds.length >= 3
            return (
              <button
                key={id}
                type="button"
                className={`${styles.chipButton} ${isSelected ? styles.active : ''}`}
                aria-pressed={isSelected}
                disabled={isDisabled}
                onClick={() => onTogglePlayer(id)}
              >
                {name}
              </button>
            )
          })}
        </div>
      </div>

      {/* 결과 수 요약 및 초기화 (접혀 있어도 항시 표시) */}
      <div className={styles.resultSummary}>
        <div className={styles.resultCount}>
          필터 결과:{' '}
          <b>{recordSummary ? recordSummary.formatted : `${filteredCount}판`}</b>
          {!recordSummary && ` / ${totalCount}판`}
        </div>
        {hasActiveFilters && (
          <button
            type="button"
            className={styles.resetButton}
            onClick={onResetFilters}
          >
            선택 초기화
          </button>
        )}
      </div>
    </section>
  )
}
