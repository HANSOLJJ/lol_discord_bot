// 단일 경기 결과 카드(팀 대진, 승리 강조, 번복 배지) 렌더링 컴포넌트
import { formatCorrectedInfo } from '../lib/corrected.ts'
import { isRowHighlighted } from '../lib/filter.ts'
import { formatKoreanDate } from '../lib/time.ts'
import type { Game } from '../lib/types.ts'
import { ChampionPortrait } from './ChampionPortrait.tsx'
import styles from './GameCard.module.css'

export interface GameCardProps {
  game: Game
  /** 디스코드 id → 표시 이름. 이름이 없는 id는 id를 그대로 보인다. */
  players: Record<string, string>
  /** 챔피언 이름 → 초상화 주소. */
  championPortraits: Record<string, string>
  /** 강조할 플레이어와 챔피언 검색어. 해당하는 줄을 isRowHighlighted로 강조한다. */
  selectedPlayerIds?: string[]
  championQuery?: string
}

/**
 * 한 판의 결과 카드. 머리줄에 시즌·라운드·시각과 승리 팀(번복됐으면 번복 배지와 요약)을,
 * 본문에 두 팀의 플레이어·챔피언을 보인다. 두 팀 칸은 같은 구조이고 승패 스타일만 다르다.
 */
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
