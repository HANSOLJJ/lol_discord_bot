// 픽 화면의 팀 구성(TEAM 1, TEAM 2 명단 및 현재 턴 강조) 컴포넌트
import type { Player, StateMessage } from '../lib/protocol.ts'
import { getCurrentPicker } from '../lib/view-logic.ts'
import styles from './TeamRoster.module.css'

interface Props {
  state: StateMessage | null
  isPc?: boolean
}

export function TeamRoster({ state, isPc = false }: Props) {
  if (!state || state.players.length === 0) return null

  const currentPicker = getCurrentPicker(state)
  const currentPickerId = currentPicker?.id ?? null

  const team1 = state.players.filter((p) => p.team === 'team1')
  const team2 = state.players.filter((p) => p.team === 'team2')

  const renderNames = (players: Player[], isPcView: boolean) => (
    <div className={styles.namesWrap}>
      {players.map((p) => {
        const isActive = p.id === currentPickerId
        const nameClass = isPcView ? styles.playerNamePc : styles.playerName
        return (
          <span key={p.id} className={nameClass} data-active={isActive} title={p.name}>
            {p.name}
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
    </section>
  )
}
