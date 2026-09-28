// 3:3 매치업 반복 구도 및 팀별 전적 통계 테이블 컴포넌트
import { useState } from 'react'
import {
  calculateMatchupStats,
  getWinRateColor,
  sortStatsRows,
  type SortDir,
} from '../lib/stats.ts'
import type { Game } from '../lib/types.ts'
import styles from './StatsTable.module.css'

export interface MatchupStatsViewProps {
  games: Game[]
  players: Record<string, string>
  selectedPlayerIds: string[]
  minGames: number
}

export function MatchupStatsView({
  games,
  players,
  selectedPlayerIds,
  minGames,
}: MatchupStatsViewProps) {
  const focus = selectedPlayerIds.length === 1 ? selectedPlayerIds[0] : null
  const focusName = focus ? players[focus] || focus : null

  // 포커스 플레이어가 바뀔 때마다 기본 정렬(포커스 있으면 col 1, 없으면 col 0, desc)로 파생
  const [userSort, setUserSort] = useState<{
    focus: string | null
    col: number
    dir: SortDir
  } | null>(null)

  const activeSort =
    userSort && userSort.focus === focus
      ? userSort
      : { focus, col: focus ? 1 : 0, dir: 'desc' as SortDir }

  const sortCol = activeSort.col
  const sortDir = activeSort.dir

  const rows = calculateMatchupStats(games, players, focus, minGames)

  const sortedRows = sortStatsRows(
    rows,
    (r) => {
      if (sortCol === 0) return r.n
      if (sortCol === 1) return r.aWinRate
      return r.bWinRate
    },
    sortDir,
  )

  const handleSortClick = (colIdx: number) => {
    if (sortCol === colIdx) {
      setUserSort({
        focus,
        col: colIdx,
        dir: sortDir === 'asc' ? 'desc' : 'asc',
      })
    } else {
      // col 0(판)은 num: true이므로 desc 기본, col 1/2(팀)은 num: false이므로 asc 기본 (옛 동작 유지)
      setUserSort({
        focus,
        col: colIdx,
        dir: colIdx === 0 ? 'desc' : 'asc',
      })
    }
  }

  const aHeaderLabel = focusName ? `${focusName} 팀` : 'A팀'
  const bHeaderLabel = focusName ? '상대팀' : 'B팀'

  return (
    <>
      <div className={styles.panel}>
        <div className={styles.tablewrap}>
          <table className={styles.table}>
            <thead>
              <tr className={styles.tr}>
                <th
                  scope="col"
                  className={`${styles.th} ${styles.num} ${styles.sortable}`}
                  onClick={() => handleSortClick(0)}
                >
                  판
                  {sortCol === 0 && (
                    <span className={styles.arrow}>
                      {sortDir === 'asc' ? '▲' : '▼'}
                    </span>
                  )}
                </th>
                <th
                  scope="col"
                  className={`${styles.th} ${styles.sortable}`}
                  onClick={() => handleSortClick(1)}
                >
                  {aHeaderLabel}
                  {sortCol === 1 && (
                    <span className={styles.arrow}>
                      {sortDir === 'asc' ? '▲' : '▼'}
                    </span>
                  )}
                </th>
                <th
                  scope="col"
                  className={`${styles.th} ${styles.sortable}`}
                  onClick={() => handleSortClick(2)}
                >
                  {bHeaderLabel}
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
                  const aColor = getWinRateColor(r.aWinRate)
                  const bColor = getWinRateColor(r.bWinRate)
                  const rowKey = `${r.a.join(',')}-vs-${r.b.join(',')}`

                  return (
                    <tr key={rowKey} className={styles.tr}>
                      <td className={`${styles.td} ${styles.num}`}>{r.n}</td>
                      <td className={`${styles.td} ${styles.combo}`}>
                        {r.aName}
                        <div className={styles.mrec}>
                          <span className={styles.w}>{r.aw}승</span>{' '}
                          <span className={styles.l}>{r.al}패</span>{' '}
                          <span style={{ color: aColor }}>
                            ({r.aWinRate.toFixed(0)}%)
                          </span>
                        </div>
                      </td>
                      <td className={`${styles.td} ${styles.combo}`}>
                        {r.bName}
                        <div className={styles.mrec}>
                          <span className={styles.w}>{r.bw}승</span>{' '}
                          <span className={styles.l}>{r.bl}패</span>{' '}
                          <span style={{ color: bColor }}>
                            ({r.bWinRate.toFixed(0)}%)
                          </span>
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

      <div className={styles.note}>
        같은 3:3 구도가 2번 이상 반복된 경우만. 각 팀 아래는 그 팀 기준 전적.{' '}
        <b>인원 1명 선택 시 그 사람 팀이 왼쪽으로 고정</b>돼 '내 팀 vs 상대팀'으로
        읽힘.
      </div>
    </>
  )
}
