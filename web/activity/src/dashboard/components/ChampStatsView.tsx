// 챔피언 탭의 전체 픽 수 및 승률 통계 테이블 컴포넌트
import { useState } from 'react'
import {
  calculateChampStats,
  formatWinRate,
  sortStatsRows,
  type SortDir,
} from '../lib/stats.ts'
import type { Game } from '../lib/types.ts'
import styles from './StatsTable.module.css'

export interface ChampStatsViewProps {
  games: Game[]
  championPortraits: Record<string, string>
  minGames: number
}

export function ChampStatsView({
  games,
  championPortraits,
  minGames,
}: ChampStatsViewProps) {
  // 기본 정렬: 픽(col 1) 내림차순
  const [sortCol, setSortCol] = useState<number>(1)
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const rows = calculateChampStats(games, minGames)

  const sortedRows = sortStatsRows(
    rows,
    (r) => {
      if (sortCol === 0) return r.champ
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
                  챔피언
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
                  픽
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
                  승률
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
                  const portraitUrl = championPortraits[r.champ]
                  return (
                    <tr key={r.champ} className={styles.tr}>
                      <td className={`${styles.td} ${styles.combo}`}>
                        {portraitUrl && (
                          <img
                            src={portraitUrl}
                            alt=""
                            className={styles.portraitSm}
                            loading="lazy"
                          />
                        )}
                        {r.champ}
                      </td>
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

      <div className={styles.note}>챔프별 전체 픽 수·승률 (인원 선택 사용 안 함).</div>
    </>
  )
}
