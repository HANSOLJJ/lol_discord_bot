// 2인 및 3인 시너지 조합 승률 및 판수 통계 테이블 컴포넌트
import { useState } from 'react'
import {
  calculateComboStats,
  formatWinRate,
  sortStatsRows,
  type SortDir,
} from '../lib/stats.ts'
import type { Game } from '../lib/types.ts'
import styles from './StatsTable.module.css'

export interface ComboStatsViewProps {
  games: Game[]
  players: Record<string, string>
  k: number
  selectedPlayerIds: string[]
  minGames: number
}

export function ComboStatsView({
  games,
  players,
  k,
  selectedPlayerIds,
  minGames,
}: ComboStatsViewProps) {
  // 기본 정렬: 승률(col 2) 내림차순
  const [sortCol, setSortCol] = useState<number>(2)
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const rows = calculateComboStats(
    games,
    players,
    k,
    selectedPlayerIds,
    minGames,
  )

  const sortedRows = sortStatsRows(
    rows,
    (r) => {
      if (sortCol === 0) return r.name
      if (sortCol === 1) return r.n
      return r.winRate
    },
    sortDir,
  )

  const handleSortClick = (colIdx: number) => {
    if (sortCol === colIdx) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortCol(colIdx)
      setSortDir(colIdx === 0 ? 'asc' : 'desc')
    }
  }

  const noteText =
    k === 2
      ? '두 명이 같은 팀이었던 판의 시너지 승률. 인원은 2명까지(1명이면 그 사람의 모든 페어).'
      : '세 명이 한 팀을 이뤘을 때 승률. 인원은 3명까지 — 2명만 골라도 그 2명이 낀 트리오가 전부 나옵니다.'

  return (
    <>
      <div className={styles.panel}>
        <div className={styles.tablewrap}>
          <table className={styles.table}>
            <thead>
              <tr className={styles.tr}>
                <th
                  scope="col"
                  className={`${styles.th} ${styles.sortable}`}
                  onClick={() => handleSortClick(0)}
                >
                  조합
                  {sortCol === 0 && (
                    <span className={styles.arrow}>
                      {sortDir === 'asc' ? '▲' : '▼'}
                    </span>
                  )}
                </th>
                <th
                  scope="col"
                  className={`${styles.th} ${styles.num} ${styles.sortable}`}
                  onClick={() => handleSortClick(1)}
                >
                  판
                  {sortCol === 1 && (
                    <span className={styles.arrow}>
                      {sortDir === 'asc' ? '▲' : '▼'}
                    </span>
                  )}
                </th>
                <th
                  scope="col"
                  className={`${styles.th} ${styles.num} ${styles.sortable}`}
                  onClick={() => handleSortClick(2)}
                >
                  같은 팀일 때 승률
                  {sortCol === 2 && (
                    <span className={styles.arrow}>
                      {sortDir === 'asc' ? '▲' : '▼'}
                    </span>
                  )}
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedRows.length === 0 ? (
                <tr className={styles.tr}>
                  <td colSpan={3} className={styles.empty}>
                    최소 판수 조건을 만족하는 데이터가 없습니다.
                  </td>
                </tr>
              ) : (
                sortedRows.map((r) => {
                  const wr = formatWinRate(r.w, r.n)
                  return (
                    <tr key={r.ids.join('|')} className={styles.tr}>
                      <td className={`${styles.td} ${styles.combo}`}>{r.name}</td>
                      <td className={`${styles.td} ${styles.num}`}>{r.n}</td>
                      <td className={styles.td}>
                        <div className={styles.bar}>
                          <span className={styles.wl}>
                            <span className={styles.w}>{r.w}</span>승{' '}
                            <span className={styles.l}>{r.l}</span>패
                          </span>
                          <div className={styles.track}>
                            <div
                              className={styles.fill}
                              style={{
                                width: `${wr.rate}%`,
                                background: wr.color,
                              }}
                            />
                          </div>
                          <span className={styles.wrnum}>{wr.formatted}</span>
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className={styles.note}>{noteText}</div>
    </>
  )
}
