// 픽 화면의 팀 구성(TEAM 1, TEAM 2 명단 및 현재 턴 강조) 컴포넌트
import type { Player, StateMessage } from '../lib/protocol.ts'
import { getAdvantageSummary, getCurrentPicker, isPlayerPresent } from '../lib/view-logic.ts'
import styles from './TeamRoster.module.css'

interface Props {
  state: StateMessage | null
  isPc?: boolean
}

/**
 * TEAM 1·TEAM 2 명단. 현재 차례인 사람을 강조하고, 이름 옆 점으로 액티비티 입장 여부를 보인다.
 * 어드밴티지가 있으면 그 요약을 한 줄 덧붙인다.
 */
export function TeamRoster({ state, isPc = false }: Props) {
  if (!state || state.players.length === 0) return null

  const currentPicker = getCurrentPicker(state)
  const currentPickerId = currentPicker?.id ?? null

  const team1 = state.players.filter((p) => p.team === 'team1')
  const team2 = state.players.filter((p) => p.team === 'team2')
  const advantageSummary = getAdvantageSummary(state.advantage, state.champions, state.phase)

  // PC와 모바일이 같은 명단을 쓰고 이름 글자 클래스만 다르다.
  const renderNames = (players: Player[], isPcView: boolean) => (
    <div className={styles.namesWrap}>
      {players.map((p) => {
        const isActive = p.id === currentPickerId
        const isPresent = isPlayerPresent(state, p.id)
        const nameClass = isPcView ? styles.playerNamePc : styles.playerName
        return (
          <span key={p.id} className={styles.player} title={`${p.name} · ${isPresent ? '입장' : '미입장'}`}>
            <span className={styles.presenceDot} data-present={isPresent} aria-hidden="true" />
            <span className={nameClass} data-active={isActive} data-present={isPresent}>
              {p.name}
            </span>
          </span>
        )
      })}
    </div>
  )

  if (isPc) {
    return (
      <section aria-label="팀 구성" className={styles.rosterPc}>
        <div className={styles.teamCardPc}>
          <span className={styles.labelTeam1}>TEAM 1</span>
          {renderNames(team1, true)}
        </div>
        <div className={styles.teamCardPc}>
          <span className={styles.labelTeam2}>TEAM 2</span>
          {renderNames(team2, true)}
        </div>
        {advantageSummary && (
          <div className={styles.advantageRowPc}>{advantageSummary}</div>
        )}
      </section>
    )
  }

  return (
    <section aria-label="팀 구성" className={styles.rosterMobile}>
      <div className={styles.teamRowMobile}>
        <span className={styles.labelTeam1}>TEAM 1</span>
        {renderNames(team1, false)}
      </div>
      <div className={styles.teamRowMobile}>
        <span className={styles.labelTeam2}>TEAM 2</span>
        {renderNames(team2, false)}
      </div>
      {advantageSummary && (
        <div className={styles.advantageRowMobile}>{advantageSummary}</div>
      )}
    </section>
  )
}
