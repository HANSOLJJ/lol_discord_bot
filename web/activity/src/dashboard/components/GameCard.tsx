// 단일 경기 결과 카드(팀 대진, 승리 강조, 번복 배지) 렌더링 컴포넌트
import { formatCorrectedInfo } from '../lib/corrected.ts'
import { isRowHighlighted } from '../lib/filter.ts'
import { formatKoreanDate } from '../lib/time.ts'
import type { Game } from '../lib/types.ts'
import { ChampionPortrait } from './ChampionPortrait.tsx'
import styles from './GameCard.module.css'

export interface GameCardProps {
  game: Game
  players: Record<string, string>
  championPortraits: Record<string, string>
  selectedPlayerIds?: string[]
  championQuery?: string
}

export function GameCard({
  game,
  players,
  championPortraits,
  selectedPlayerIds = [],
  championQuery = '',
}: GameCardProps) {
  const isTeam1Winner = game.winner === 'team1'
  const isTeam2Winner = game.winner === 'team2'

  const formattedTime = formatKoreanDate(game.time)
  const correctedInfo = game.corrected ? formatCorrectedInfo(game.corrected) : null

  return (
    <article className={styles.card} aria-label={`시즌 ${game.season} 라운드 ${game.round} 경기 결과`}>
      {/* 카드 머리줄 */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <span className={styles.roundTitle}>
            시즌 {game.season} · R{game.round}
          </span>
          <time dateTime={game.time} className={styles.gameTime}>
            {formattedTime}
          </time>
        </div>

        <div className={styles.headerRight}>
          {correctedInfo && (
            <div className={styles.correctedGroup}>
              <span className={styles.correctedBadge}>번복됨</span>
              <span className={styles.correctedDetail}>({correctedInfo.summary})</span>
            </div>
          )}
          <span
            className={`${styles.winBadge} ${isTeam1Winner ? styles.team1 : styles.team2}`}
          >
            {isTeam1Winner ? 'TEAM 1 승리' : 'TEAM 2 승리'}
          </span>
        </div>
      </div>

      {/* 카드 본문 (양 팀 대진) */}
      <div className={styles.body}>
        {/* TEAM 1 칸 */}
        <div
          className={`${styles.teamBox} ${isTeam1Winner ? `${styles.winner} ${styles.team1}` : styles.loser}`}
        >
          <div className={`${styles.teamTitle} ${styles.team1}`}>
            <span>TEAM 1</span>
            <span className={styles.resultLabel}>{isTeam1Winner ? '승리' : '패배'}</span>
          </div>
          <div className={styles.playerList}>
            {game.team1.map((slot) => {
              const playerName = players[slot.id] || slot.id
              const portraitUrl = championPortraits[slot.champ]
              const isHighlighted = isRowHighlighted(slot, selectedPlayerIds, championQuery)
              return (
                <div
                  key={slot.id}
                  className={`${styles.playerRow}${isHighlighted ? ` ${styles.highlighted}` : ''}`}
                >
                  <ChampionPortrait championName={slot.champ} imageUrl={portraitUrl} />
                  <div className={styles.playerInfo}>
                    <span className={styles.playerName} title={playerName}>
                      {playerName}
                    </span>
                    <span className={styles.champName} title={slot.champ}>
                      {slot.champ}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* TEAM 2 칸 */}
        <div
          className={`${styles.teamBox} ${isTeam2Winner ? `${styles.winner} ${styles.team2}` : styles.loser}`}
        >
          <div className={`${styles.teamTitle} ${styles.team2}`}>
            <span>TEAM 2</span>
            <span className={styles.resultLabel}>{isTeam2Winner ? '승리' : '패배'}</span>
          </div>
          <div className={styles.playerList}>
            {game.team2.map((slot) => {
              const playerName = players[slot.id] || slot.id
              const portraitUrl = championPortraits[slot.champ]
              const isHighlighted = isRowHighlighted(slot, selectedPlayerIds, championQuery)
              return (
                <div
                  key={slot.id}
                  className={`${styles.playerRow}${isHighlighted ? ` ${styles.highlighted}` : ''}`}
                >
                  <ChampionPortrait championName={slot.champ} imageUrl={portraitUrl} />
                  <div className={styles.playerInfo}>
                    <span className={styles.playerName} title={playerName}>
                      {playerName}
                    </span>
                    <span className={styles.champName} title={slot.champ}>
                      {slot.champ}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </article>
  )
}
