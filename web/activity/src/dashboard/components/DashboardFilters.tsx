// 챔피언 검색창, 정렬, 같은 팀 플레이어 칩(최대 3개), 승패 요약 및 모바일 접기/펼치기 필터 컴포넌트
import { useState } from 'react'
import type { PeriodOption, RecordSummary, Session, SortOrder } from '../lib/types.ts'
import styles from './DashboardFilters.module.css'

export interface DashboardFiltersProps {
  period: string
  /** 기본 기간(최신 시즌, 없으면 전체). 지금 기간이 이 값과 다르면 켜진 조건으로 센다. */
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
  /** 전체 판 수와 필터 뒤 판 수. 플레이어를 고르지 않았을 때 "n판 / 전체판"으로 보인다. */
  totalCount: number
  filteredCount: number
  /** 고른 플레이어가 속한 팀의 승패. 고른 사람이 없으면 null이다. */
  recordSummary: RecordSummary | null
  onResetFilters: () => void
}

/**
 * 대전 기록 탭 필터. 챔피언 검색창과 결과 요약은 늘 보이고, 기간·정렬·플레이어 칩은 서랍 안에 둔다.
 * 서랍은 화면 폭 480px 이하에서만 접히고 "필터" 버튼으로 펼친다(DashboardFilters.module.css).
 * 플레이어를 고르면 결과 요약이 판 수 대신 그 사람들이 같은 팀이었을 때의 승패로 바뀐다.
 */
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

  // 세션 기간은 아래에서 "세션별" 묶음으로 따로 보이므로 나머지 기간(전체·시즌)만 먼저 나열한다.
  const nonSessionOptions = periodOptions.filter((opt) => opt.group !== 'session')

  // 기간·정렬 기본값을 제외한 켜진 조건 수 계산
  let activeCollapsibleCount = 0
  if (period !== defaultPeriod) activeCollapsibleCount++
  if (sortOrder !== 'desc') activeCollapsibleCount++
  activeCollapsibleCount += selectedPlayerIds.length

  // "필터 n" 숫자는 서랍 안 조건만 센다(검색창은 접히지 않아 늘 보이므로). 초기화 버튼은 검색어까지 포함해 판단한다.
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
