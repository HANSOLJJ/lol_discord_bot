// 픽 순서 세로 목록(1~6순위, 이름, 승수, 선택 상태, 초상화) 컴포넌트
import { useState } from 'react'
import type { Champion, StateMessage } from '../lib/protocol.ts'
import {
  COLOR_TEAM1,
  COLOR_TEAM2,
  getChampionPortraitUrl,
} from '../lib/view-logic.ts'
import styles from './PickOrderList.module.css'

interface Props {
  state: StateMessage | null
  isPc?: boolean
}

/** 픽 순서 줄의 작은 초상화. 주소가 없거나 이미지를 불러오지 못하면 챔피언 이름 첫 글자로 대신한다. */
function SmallPortrait({ champion, ddragonVersion }: { champion: Champion; ddragonVersion: string | null }) {
  const [failed, setFailed] = useState(false)
  const url = getChampionPortraitUrl(champion.id, ddragonVersion)

  if (!url || failed) {
    const initial = champion.name.trim().charAt(0) || '?'
    return <span className={styles.fallbackCircle}>{initial}</span>
  }

  return (
    <img
      src={url}
      alt=""
      className={styles.champPortrait}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  )
}

/** 픽 순서(승수 낮은 순) 목록. 줄마다 순번·이름·승수와, 고른 챔피언 또는 "선택 중"·"대기"를 보인다. */
export function PickOrderList({ state, isPc = false }: Props) {
  if (!state || state.pick_order.length === 0) return null

  const myId = state.me.id
  // 현재 차례 줄 강조는 picking 단계에서만 한다.
  const currentIndex = state.phase === 'picking' ? state.current_index : null

  return (
    <section aria-label="픽 순서" className={styles.section}>
      <div className={styles.headerRow}>
        <span>픽 순서 · 승수 낮은 순</span>
        <span>
          <span className={styles.teamLegend1}>TEAM 1</span> · <span className={styles.teamLegend2}>TEAM 2</span>
        </span>
      </div>

      {state.pick_order.map((userId, index) => {
        const player = state.players.find((p) => p.id === userId)
        if (!player) return null

        const isMe = userId === myId
        const isCurrentTurn = index === currentIndex
        const champId = state.selections[userId]
        const champ = champId ? state.champions.find((c) => c.id === champId) : null
        // 시간 초과로 서버가 대신 고른 사람은 "자동" 태그를 붙인다.
        const isAuto = state.auto_assigned.includes(userId)

        const nameColor = player.team === 'team1' ? COLOR_TEAM1 : COLOR_TEAM2
        const rowClass = `${isPc ? styles.rowPc : styles.rowMobile} ${isCurrentTurn ? styles.rowActive : ''}`

        return (
          <div key={userId} className={rowClass}>
            <span className={styles.num}>{index + 1}</span>

            <span className={styles.nameWrap}>
              <span className={styles.playerName} style={{ color: nameColor }} title={player.name}>
                {player.name}
              </span>
              {isMe && <span className={styles.meTag}>(나)</span>}
            </span>

            <span className={styles.wins}>{player.wins}승</span>

            <div className={styles.statusCol}>
              {champ ? (
                <>
                  <SmallPortrait champion={champ} ddragonVersion={state.ddragon_version} />
                  <span className={styles.champName} title={champ.name}>
                    {champ.name}
                  </span>
                  {isAuto && <span className={styles.autoTag}>자동</span>}
                </>
              ) : isCurrentTurn ? (
                <span className={styles.selectingBadge}>선택 중</span>
              ) : (
                <span className={styles.waitingText}>대기</span>
              )}
            </div>
          </div>
        )
      })}
    </section>
  )
}
