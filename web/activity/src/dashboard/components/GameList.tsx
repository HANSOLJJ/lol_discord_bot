// 대전 기록 카드 목록 렌더링 및 30개 단위 더 보기 페이지네이션 컴포넌트
import { useState } from 'react'
import type { Game } from '../lib/types.ts'
import { GameCard } from './GameCard.tsx'
import styles from './GameList.module.css'

/** 처음 그리는 카드 수이자 "더 보기" 한 번에 늘어나는 카드 수. */
export const DEFAULT_PAGE_SIZE = 30

export interface GameListProps {
  /** 이미 기간·플레이어·검색·정렬 필터가 적용된 경기 목록(DashboardApp이 계산). */
  games: Game[]
  players: Record<string, string>
  championPortraits: Record<string, string>
  /** 카드 안에서 강조할 플레이어와 챔피언 검색어. 걸러 내기는 이미 끝났고 강조 표시에만 쓴다. */
  selectedPlayerIds?: string[]
  championQuery?: string
}

/**
 * 대전 기록 카드 목록. 처음 30개만 그리고 "더 보기"로 30개씩 늘린다.
 * 필터가 바뀌면 DashboardApp이 key를 바꿔 페이지를 처음부터 다시 시작한다.
 */
export function GameList({
  games,
  players,
  championPortraits,
  selectedPlayerIds = [],
  championQuery = '',
}: GameListProps) {
  const [page, setPage] = useState(1)

  const visibleCount = page * DEFAULT_PAGE_SIZE
  const visibleGames = games.slice(0, visibleCount)
  const hasMore = visibleCount < games.length

  const handleLoadMore = () => {
    setPage((prev) => prev + 1)
  }

  if (games.length === 0) {
    return (
      <div className={styles.emptyMessage} role="status">
        선택한 조건에 일치하는 경기 기록이 없습니다.
      </div>
    )
  }

  return (
    <div className={styles.listContainer}>
      {visibleGames.map((game) => (
        <GameCard
          key={`${game.season}-${game.round}-${game.time}`}
          game={game}
          players={players}
          championPortraits={championPortraits}
          selectedPlayerIds={selectedPlayerIds}
          championQuery={championQuery}
        />
      ))}

      {hasMore && (
        <div className={styles.loadMoreContainer}>
          <button
            type="button"
            className={styles.loadMoreButton}
            onClick={handleLoadMore}
          >
            더 보기 ({visibleGames.length} / {games.length})
          </button>
        </div>
      )}
    </div>
  )
}
