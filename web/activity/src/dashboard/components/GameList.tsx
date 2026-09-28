// 대전 기록 카드 목록 렌더링 및 30개 단위 더 보기 페이지네이션 컴포넌트
import { useState } from 'react'
import type { Game } from '../lib/types.ts'
import { GameCard } from './GameCard.tsx'
import styles from './GameList.module.css'

export const DEFAULT_PAGE_SIZE = 30

export interface GameListProps {
  games: Game[]
  players: Record<string, string>
  championPortraits: Record<string, string>
  selectedPlayerIds?: string[]
  championQuery?: string
}

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
