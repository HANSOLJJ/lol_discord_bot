// 개인 탭의 전체 플레이어 개요 테이블, 모바일 카드 뷰, 챔피언별 상세 드릴다운 컴포넌트
import { useEffect, useRef, useState } from 'react'
import {
  calculateChampStats,
  calculatePlayerDrilldownHeader,
  calculatePlayerOverview,
  formatWinRate,
  sortStatsRows,
  type PlayerChampStat,
  type SortDir,
} from '../lib/stats.ts'
import type { Game } from '../lib/types.ts'
import styles from './StatsTable.module.css'

export interface PlayerStatsViewProps {
  games: Game[]
  players: Record<string, string>
  championPortraits: Record<string, string>
  selectedPlayerId: string | null
  onSelectPlayer: (id: string | null) => void
  minGames: number
}

interface TooltipState {
  champ: string
  w: number
  l: number
  n: number
  winRate: number
  x: number
  y: number
}

export function PlayerStatsView({
  games,
  players,
  championPortraits,
  selectedPlayerId,
  onSelectPlayer,
  minGames,
}: PlayerStatsViewProps) {
  // 개요 화면 정렬 상태 (기본: 승률 내림차순)
  const [overviewSortDir, setOverviewSortDir] = useState<SortDir>('desc')

  // 드릴다운 화면 정렬 상태 (기본: 픽 내림차순, col: 0=챔프, 1=픽, 2=승률)
  const [drillSortCol, setDrillSortCol] = useState<number>(1)
  const [drillSortDir, setDrillSortDir] = useState<SortDir>('desc')

  // 챔피언 초상화 툴팁 상태
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)

  // 툴팁 닫기 이벤트 리스너 등록
  useEffect(() => {
    if (!tooltip) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setTooltip(null)
    }
    const handleClickOutside = (e: MouseEvent) => {
      if (
        tooltipRef.current &&
        !tooltipRef.current.contains(e.target as Node) &&
        !(e.target as HTMLElement).closest(`.${styles.champTrigger}`)
      ) {
        setTooltip(null)
      }
    }
    const handleScroll = () => setTooltip(null)

    window.addEventListener('keydown', handleKeyDown)
    document.addEventListener('click', handleClickOutside)
    window.addEventListener('scroll', handleScroll, true)
    window.addEventListener('resize', handleScroll)

    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      document.removeEventListener('click', handleClickOutside)
      window.removeEventListener('scroll', handleScroll, true)
      window.removeEventListener('resize', handleScroll)
    }
  }, [tooltip])

  const openTooltip = (
    stat: { champ: string; w: number; l: number; n: number; winRate: number },
    target: HTMLElement,
  ) => {
    const rect = target.getBoundingClientRect()
    const boxWidth = 220
    const boxHeight = 75
    const left = Math.max(
      12,
      Math.min(rect.left, window.innerWidth - boxWidth - 12),
    )
    const top =
      rect.bottom + boxHeight + 20 < window.innerHeight
        ? rect.bottom + 8
        : Math.max(12, rect.top - boxHeight - 8)

    setTooltip({
      champ: stat.champ,
      w: stat.w,
      l: stat.l,
      n: stat.n,
      winRate: stat.winRate,
      x: left,
      y: top,
    })
  }

  // --- A. 특정 플레이어 드릴다운 모드 ---
  if (selectedPlayerId) {
    const header = calculatePlayerDrilldownHeader(
      games,
      selectedPlayerId,
      players,
    )
    const rawChamps = calculateChampStats(
      games,
      minGames,
      (p) => p.id === selectedPlayerId,
    )

    const sortedChamps = sortStatsRows(
      rawChamps,
      (r) => {
        if (drillSortCol === 0) return r.champ
        if (drillSortCol === 1) return r.n
        return r.winRate
      },
      drillSortDir,
    )

    const handleSortClick = (colIdx: number) => {
      if (drillSortCol === colIdx) {
        setDrillSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'))
      } else {
        setDrillSortCol(colIdx)
        setDrillSortDir(colIdx === 0 ? 'asc' : 'desc')
      }
    }

    return (
      <div className={styles.panel}>
        {/* 뒤로가기 버튼 */}
        <button
          type="button"
          className={styles.backbar}
          onClick={() => onSelectPlayer(null)}
        >
          ‹ 전체 플레이어로
        </button>

        {/* 드릴다운 요약 헤더 */}
        <div className={styles.drillhead}>
          {header.who} · {header.picks}판 · 플레이 챔프{' '}
          <b>{header.uniqueChampCount}종</b> ·{' '}
          <span className={styles.w}>{header.wins}</span>승{' '}
          <span className={styles.l}>{header.losses}</span>패
        </div>

        {/* 챔피언별 전적 테이블 */}
        <div className={styles.tablewrap}>
          <table className={styles.table}>
            <thead>
              <tr className={styles.tr}>
                <th
                  scope="col"
                  className={`${styles.th} ${styles.sortable}`}
                  onClick={() => handleSortClick(0)}
                >
                  {header.who} 챔프
                  {drillSortCol === 0 && (
                    <span className={styles.arrow}>
                      {drillSortDir === 'asc' ? '▲' : '▼'}
                    </span>
                  )}
                </th>
                <th
                  scope="col"
                  className={`${styles.th} ${styles.num} ${styles.sortable}`}
                  onClick={() => handleSortClick(1)}
                >
                  픽
                  {drillSortCol === 1 && (
                    <span className={styles.arrow}>
                      {drillSortDir === 'asc' ? '▲' : '▼'}
                    </span>
                  )}
                </th>
                <th
                  scope="col"
                  className={`${styles.th} ${styles.num} ${styles.sortable}`}
                  onClick={() => handleSortClick(2)}
                >
                  승률
                  {drillSortCol === 2 && (
                    <span className={styles.arrow}>
                      {drillSortDir === 'asc' ? '▲' : '▼'}
                    </span>
                  )}
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedChamps.length === 0 ? (
                <tr className={styles.tr}>
                  <td colSpan={3} className={styles.empty}>
                    최소 판수 조건을 만족하는 데이터가 없습니다.
                  </td>
                </tr>
              ) : (
                sortedChamps.map((r) => {
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
    )
  }

  // --- B. 전체 6명 플레이어 개요 모드 ---
  const rawRows = calculatePlayerOverview(games, players)
  const sortedRows = sortStatsRows(rawRows, (r) => r.winRate, overviewSortDir)

  const handleToggleOverviewSort = () => {
    setOverviewSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'))
  }

  const renderTopChampions = (top5: PlayerChampStat[]) => {
    if (!top5.length) {
      return <span className={styles.drill}>기록 없음</span>
    }
    return (
      <div className={styles.champStrip}>
        {top5.map((s) => {
          const img = championPortraits[s.champ]
          return (
            <button
              key={s.champ}
              type="button"
              className={styles.champTrigger}
              aria-label={`${s.champ} 전적`}
              onClick={(e) => {
                e.stopPropagation()
                openTooltip(s, e.currentTarget)
              }}
            >
              {img ? (
                <img
                  src={img}
                  alt=""
                  className={styles.portrait}
                  loading="lazy"
                />
              ) : (
                <span className={styles.champFallback}>{s.champ}</span>
              )}
            </button>
          )
        })}
      </div>
    )
  }

  return (
    <>
      <div className={styles.panel}>
        {/* PC 테이블 */}
        <div className={`${styles.tablewrap} ${styles.playerTable}`}>
          <table className={styles.table}>
            <thead>
              <tr className={styles.tr}>
                <th scope="col" className={styles.th}>
                  플레이어
                </th>
                <th scope="col" className={`${styles.th} ${styles.num}`}>
                  판
                </th>
                <th scope="col" className={`${styles.th} ${styles.num}`}>
                  플레이 챔프 수
                </th>
                <th scope="col" className={styles.th}>
                  주력 챔프 TOP5
                </th>
                <th
                  scope="col"
                  className={`${styles.th} ${styles.num} ${styles.sortable}`}
                  onClick={handleToggleOverviewSort}
                >
                  승률
                  <span className={styles.arrow}>
                    {overviewSortDir === 'asc' ? '▲' : '▼'}
                  </span>
                </th>
                <th scope="col" className={`${styles.th} ${styles.num}`}>
                  번 돈
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((r) => {
                const wr = formatWinRate(r.w, r.n)
                const earningsClass =
                  r.earnings.sign === 'positive'
                    ? styles.earningsPositive
                    : r.earnings.sign === 'negative'
                      ? styles.earningsNegative
                      : styles.earningsNeutral

                return (
                  <tr
                    key={r.id}
                    className={`${styles.tr} ${styles.clickable}`}
                    onClick={(e) => {
                      if (!(e.target as HTMLElement).closest('button')) {
                        onSelectPlayer(r.id)
                      }
                    }}
                  >
                    <td className={`${styles.td} ${styles.combo}`}>
                      <button
                        type="button"
                        className={styles.playerLink}
                        onClick={() => onSelectPlayer(r.id)}
                        aria-label={`${r.name} 챔피언별 전적`}
                      >
                        {r.name}{' '}
                        <span className={styles.drill} aria-hidden="true">
                          챔프 ›
                        </span>
                      </button>
                    </td>
                    <td className={`${styles.td} ${styles.num}`}>{r.n}</td>
                    <td className={`${styles.td} ${styles.num}`}>{r.champN}</td>
                    <td className={styles.td}>{renderTopChampions(r.top5)}</td>
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
                    <td className={`${styles.td} ${styles.num}`}>
                      <span className={`${styles.earnings} ${earningsClass}`}>
                        {r.earnings.formatted}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* 모바일 전용 카드 목록 (≤768px) */}
        <section className={styles.playerMobile} aria-label="플레이어 전적">
          <div className={styles.playerHeading}>
            <span>플레이어</span>
            <button
              type="button"
              onClick={handleToggleOverviewSort}
              aria-label={`승률 ${overviewSortDir === 'desc' ? '내림차순, 오름차순으로 변경' : '오름차순, 내림차순으로 변경'}`}
            >
              승률{' '}
              <span className={styles.arrow} aria-hidden="true">
                {overviewSortDir === 'asc' ? '▲' : '▼'}
              </span>
            </button>
            <span>번 돈</span>
          </div>
          <ul className={styles.playerList}>
            {sortedRows.map((r) => {
              const wr = formatWinRate(r.w, r.n)
              const earningsClass =
                r.earnings.sign === 'positive'
                  ? styles.earningsPositive
                  : r.earnings.sign === 'negative'
                    ? styles.earningsNegative
                    : styles.earningsNeutral

              return (
                <li key={r.id} className={styles.playerItem}>
                  <div className={styles.playerPrimary}>
                    <button
                      type="button"
                      className={styles.playerLink}
                      onClick={() => onSelectPlayer(r.id)}
                      aria-label={`${r.name} 챔피언별 전적`}
                    >
                      {r.name}{' '}
                      <span className={styles.drill} aria-hidden="true">
                        ›
                      </span>
                    </button>
                    <div className={styles.playerRate}>
                      <strong>{wr.formatted}</strong>
                      <span className={styles.wl}>
                        <span className={styles.w}>{r.w}</span>승{' '}
                        <span className={styles.l}>{r.l}</span>패
                      </span>
                    </div>
                    <div className={styles.playerMoney}>
                      <span className={`${styles.earnings} ${earningsClass}`}>
                        {r.earnings.formatted}
                      </span>
                    </div>
                  </div>
                  <div className={styles.playerSecondary}>
                    <div className={styles.playerChamps}>
                      <span className={styles.caption}>주력 챔프 TOP5</span>
                      {renderTopChampions(r.top5)}
                    </div>
                    <div className={styles.playerMeta}>
                      <span>
                        <b>{r.n}</b>판
                      </span>
                      <span>
                        챔프 <b>{r.champN}</b>종
                      </span>
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>
        </section>
      </div>

      {/* 하단 안내 문구 */}
      <div className={styles.note}>
        주력 챔프 TOP5는 승수 많은 순입니다. <b>초상화를 누르면 전적</b>,{' '}
        <b>플레이어 이름을 누르면 챔피언별 상세</b>를 볼 수 있습니다. '번 돈'은
        선택한 기간의 승 +5,000원 / 패 -5,000원 정산입니다.
      </div>

      {/* 챔피언 초상화 툴팁 팝업 */}
      {tooltip && (
        <div
          ref={tooltipRef}
          className={styles.champInfo}
          role="status"
          style={{ left: `${tooltip.x}px`, top: `${tooltip.y}px` }}
        >
          <strong>{tooltip.champ}</strong>
          <span className={styles.wl}>
            <span className={styles.w}>{tooltip.w}승</span>{' '}
            <span className={styles.l}>{tooltip.l}패</span>
          </span>{' '}
          · {tooltip.winRate.toFixed(0)}% · {tooltip.n}판
        </div>
      )}
    </>
  )
}
