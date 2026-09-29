// 카운트다운 숫자 및 프로그레스 바를 격리 렌더링하는 컴포넌트
import type { ReactNode } from 'react'
import { useRemainingSeconds } from '../hooks/useRemainingSeconds.ts'
import type { ClockAnchor } from '../lib/clock.ts'
import type { StateMessage } from '../lib/protocol.ts'
import {
  COLOR_TEAM1,
  COLOR_TEAM2,
  COLOR_WARNING_RED,
  COLOR_YELLOW,
  getCurrentPicker,
  isMyTurn,
  isWarningSeconds,
  mustPickForced,
} from '../lib/view-logic.ts'
import styles from './TurnCountdown.module.css'

interface Props {
  state: StateMessage
  anchor: ClockAnchor | null
}

export function TurnCountdown({ state, anchor }: Props) {
  const isStarting = state.phase === 'starting'
  const isAdvantage = state.phase === 'advantage'
  const isPicking = state.phase === 'picking'
  const deadlineMs = isPicking || isAdvantage ? state.deadline_ms : isStarting ? state.start_at_ms : null
  const seconds = useRemainingSeconds(deadlineMs, anchor)

  const myTurn = isAdvantage ? state.me.can_advantage : isMyTurn(state)
  const picker = getCurrentPicker(state)

  const warning = isWarningSeconds(seconds)
  const color = warning ? COLOR_WARNING_RED : COLOR_YELLOW

  let title: ReactNode = ''
  let hint = ''

  if (isStarting) {
    title = '게임 시작 준비 중'
    hint = '곧 픽이 시작됩니다'
  } else if (isAdvantage) {
    const teamLabel = state.advantage?.team === 'team1' ? 'TEAM 1' : 'TEAM 2'
    const teamColor = state.advantage?.team === 'team1' ? COLOR_TEAM1 : COLOR_TEAM2
    const kindText = state.advantage?.kind === 'ban' ? '밴할 챔피언 1개' : '상대 팀 강제픽 1개'
    title = (
      <>
        <span style={{ color: teamColor }}>{teamLabel}</span> 어드밴티지 · {kindText}
      </>
    )
    hint = state.me.can_advantage ? '챔피언을 누르면 바로 확정됩니다' : `${teamLabel}가 고르는 중`
  } else if (isPicking) {
    title = myTurn ? '내 차례입니다' : picker ? `${picker.name} 님이 고르는 중` : '선택 진행 중'
    hint = mustPickForced(state)
      ? '강제픽 챔피언을 골라야 합니다'
      : myTurn
        ? '챔피언을 누르면 바로 확정됩니다'
        : '내 차례가 오면 여기에 표시됩니다'
  }

  const maxSeconds = isStarting ? 15 : 20
  const currentSeconds = seconds ?? 0
  const progressPercent = Math.min(100, Math.max(0, Math.round((currentSeconds / maxSeconds) * 100)))

  return (
    <section aria-label="현재 차례" className={styles.turnBox} data-my-turn={myTurn}>
      <div className={styles.countCol} style={{ color }}>
        {seconds !== null && seconds > 0 ? (
          seconds
        ) : seconds === 0 ? (
          <span className={styles.closing}>마감 확인 중…</span>
        ) : (
          '–'
        )}
      </div>
      <div className={styles.rightCol}>
        <strong className={styles.turnTitle}>{title}</strong>
        <span className={styles.turnHint}>{hint}</span>
        <div className={styles.progressBarBg}>
          <div
            className={styles.progressBarFill}
            style={{
              width: `${progressPercent}%`,
              background: color,
            }}
          />
        </div>
      </div>
    </section>
  )
}
