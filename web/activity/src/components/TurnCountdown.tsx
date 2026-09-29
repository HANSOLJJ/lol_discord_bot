// 카운트다운 숫자 및 프로그레스 바를 격리 렌더링하는 컴포넌트
import type { ReactNode } from 'react'
import { useCountdownMaxSeconds } from '../hooks/useCountdownMaxSeconds.ts'
import { useRemainingSeconds } from '../hooks/useRemainingSeconds.ts'
import type { ClockAnchor } from '../lib/clock.ts'
import type { StateMessage } from '../lib/protocol.ts'
import {
  canPause,
  canResume,
  canStartNow,
  COLOR_MUTED,
  COLOR_TEAM1,
  COLOR_TEAM2,
  COLOR_WARNING_RED,
  COLOR_YELLOW,
  getCountdownDeadline,
  getCurrentPicker,
  getPauseBanner,
  getPausedSeconds,
  getPresence,
  isMyTurn,
  isWaitingForPlayers,
  isWarningSeconds,
  mustPickForced,
} from '../lib/view-logic.ts'
import styles from './TurnCountdown.module.css'

interface Props {
  state: StateMessage
  anchor: ClockAnchor | null
  isConnected: boolean
  isPending: boolean
  onStartNow: (gameId: string) => void
  onPause: (gameId: string) => void
  onResume: (gameId: string) => void
}

export function TurnCountdown({ state, anchor, isConnected, isPending, onStartNow, onPause, onResume }: Props) {
  const isStarting = state.phase === 'starting'
  const isAdvantage = state.phase === 'advantage'
  const isPicking = state.phase === 'picking'
  const deadlineMs = getCountdownDeadline(state)
  const liveSeconds = useRemainingSeconds(deadlineMs, anchor)
  const paused = state.paused !== null
  // 정지 중에는 서버가 저장한 남은 시간으로 숫자를 고정한다.
  const seconds = paused ? getPausedSeconds(state) : liveSeconds
  const waiting = isWaitingForPlayers(state)
  // 입장 대기 중(카운트다운 없음)에 정지하면 남은 초가 없다.
  const waitingPaused = isStarting && state.paused !== null && state.paused.remaining_ms === null
  const presence = getPresence(state)
  const pauseBanner = getPauseBanner(state)

  const myTurn = !paused && (isAdvantage ? state.me.can_advantage : isMyTurn(state))
  const picker = getCurrentPicker(state)

  const warning = isWarningSeconds(seconds)
  const color = paused ? COLOR_MUTED : warning ? COLOR_WARNING_RED : COLOR_YELLOW

  let title: ReactNode = ''
  let hint = ''

  if (isStarting) {
    if (waitingPaused) {
      title = '입장 대기 중 일시정지'
      hint = '재개하면 다시 입장을 기다립니다'
    } else if (waiting) {
      title = `참가자 입장 대기 ${presence?.present ?? 0}/${presence?.total ?? 0}`
      hint = '모두 들어오면 5초 뒤 픽이 시작됩니다'
    } else {
      title = '게임 시작 준비 중'
      hint = '곧 픽이 시작됩니다'
    }
  } else if (isAdvantage) {
    const teamLabel = state.advantage?.team === 'team1' ? 'TEAM 1' : 'TEAM 2'
    const teamColor = state.advantage?.team === 'team1' ? COLOR_TEAM1 : COLOR_TEAM2
    const kindText = state.advantage?.kind === 'ban' ? '밴할 챔피언 1개' : '상대 팀 강제픽 1개'
    title = (
      <>
        <span style={{ color: teamColor }}>{teamLabel}</span> 어드밴티지
      </>
    )
    hint = state.me.can_advantage
      ? `${kindText}를 고르세요 · 누르면 바로 확정`
      : `${teamLabel}가 ${kindText}를 고르는 중`
  } else if (isPicking) {
    title = myTurn ? '내 차례입니다' : picker ? `${picker.name} 님이 고르는 중` : '선택 진행 중'
    hint = mustPickForced(state)
      ? '강제픽 챔피언을 골라야 합니다'
      : myTurn
        ? '챔피언을 누르면 바로 확정됩니다'
        : '내 차례가 오면 여기에 표시됩니다'
  }

  if (paused && !waitingPaused) {
    hint = '재개하면 남은 시간부터 이어집니다'
  }

  const maxSeconds = useCountdownMaxSeconds(deadlineMs, liveSeconds, state.phase)
  const currentSeconds = seconds ?? 0
  const progressPercent = Math.min(100, Math.max(0, Math.round((currentSeconds / maxSeconds) * 100)))

  const gameId = state.game_id ?? ''
  const showStartNow = waiting && state.me.can_start_now
  const showPause = state.me.can_pause
  const showResume = state.me.can_resume

  return (
    <section aria-label="현재 차례" className={styles.turnBox} data-my-turn={myTurn} data-paused={paused}>
      <div className={styles.countCol} style={{ color }}>
        {seconds !== null && (seconds > 0 || paused) ? (
          seconds
        ) : seconds === 0 ? (
          <span className={styles.closing}>마감 확인 중…</span>
        ) : (
          '–'
        )}
      </div>
      <div className={styles.rightCol}>
        {pauseBanner && <span className={styles.pauseBanner}>{pauseBanner}</span>}
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
        {(showStartNow || showPause || showResume) && (
          <div className={styles.actions}>
            {showStartNow && (
              <button
                type="button"
                className={styles.btnStartNow}
                disabled={!canStartNow(state, isPending, isConnected)}
                onClick={() => onStartNow(gameId)}
                title="아직 들어오지 않은 참가자를 기다리지 않고 5초 뒤 시작합니다"
              >
                지금 시작
              </button>
            )}
            {showPause && (
              <button
                type="button"
                className={styles.btnControl}
                disabled={!canPause(state, isPending, isConnected)}
                onClick={() => onPause(gameId)}
              >
                일시정지
              </button>
            )}
            {showResume && (
              <button
                type="button"
                className={styles.btnResume}
                disabled={!canResume(state, isPending, isConnected)}
                onClick={() => onResume(gameId)}
              >
                재개
              </button>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
