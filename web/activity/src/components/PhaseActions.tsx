// 게임 대기(none), 승리 팀 입력(awaiting_result), 결과 및 번복(completed) 액션 컴포넌트
import type { StateMessage, Team } from '../lib/protocol.ts'
import {
  canReportWinner,
  canReverseGame,
  canStartGame,
  COLOR_TEAM1,
  COLOR_TEAM2,
} from '../lib/view-logic.ts'
import styles from './PhaseActions.module.css'

interface Props {
  state: StateMessage | null
  isConnected: boolean
  isPending: boolean
  onStart: (gameId: string | null) => void
  onReport: (gameId: string, winner: Team) => void
  onReverse: (gameId: string, expectedWinner: Team) => void
}

export function PhaseActions({ state, isConnected, isPending, onStart, onReport, onReverse }: Props) {
  if (!state || state.phase === 'none' || state.phase === 'aborted') {
    const canStart = canStartGame(state, isPending, isConnected)
    return (
      <section aria-label="새 게임 시작" className={styles.noneBox}>
        <div className={styles.noneTitle}>진행 중인 게임이 없습니다</div>
        <div className={styles.noneDesc}>새 판을 시작하려면 게임 시작 버튼을 눌러 주세요.</div>
        <button
          type="button"
          className={styles.btnPrimary}
          disabled={!canStart}
          onClick={() => onStart(state?.game_id ?? null)}
        >
          게임 시작
        </button>
      </section>
    )
  }

  if (state.phase === 'awaiting_result') {
    const canReport = canReportWinner(state, isPending, isConnected)
    const canStart = canStartGame(state, isPending, isConnected)
    const gameId = state.game_id ?? ''

    return (
      <section aria-label="승리 팀 입력" className={styles.awaitingBox}>
        <div className={styles.awaitingHeader}>
          <strong className={styles.awaitingTitle}>모든 선택 완료</strong>
          <span className={styles.awaitingDesc}>
            게임이 끝나면 이긴 팀을 눌러 주세요. 누르면 바로 기록됩니다.
          </span>
        </div>
        <div className={styles.winnerGrid}>
          <button
            type="button"
            className={styles.btnWinnerTeam1}
            disabled={!canReport}
            onClick={() => onReport(gameId, 'team1')}
          >
            TEAM 1 승리
          </button>
          <button
            type="button"
            className={styles.btnWinnerTeam2}
            disabled={!canReport}
            onClick={() => onReport(gameId, 'team2')}
          >
            TEAM 2 승리
          </button>
        </div>
        <div className={styles.abandonRow}>
          <button
            type="button"
            className={styles.btnAbandon}
            disabled={!canStart}
            onClick={() => onStart(state.game_id)}
            title="이전 결과를 버리고 새 판을 시작합니다"
          >
            결과 없이 새 판
          </button>
        </div>
      </section>
    )
  }

  if (state.phase === 'completed') {
    const result = state.result
    const winner = result?.winner ?? 'team1'
    const winnerColor = winner === 'team1' ? COLOR_TEAM1 : COLOR_TEAM2
    const winnerLabel = winner === 'team1' ? 'TEAM 1 승리' : 'TEAM 2 승리'

    const isCorrected = Boolean(result?.corrected)
    const descText = isCorrected
      ? `번복됨 · ${result?.corrected?.from === 'team1' ? 'TEAM 1' : 'TEAM 2'}에서 정정됨`
      : '결과 기록됨 · 전적에 반영됨'

    const canReverse = canReverseGame(state, isPending, isConnected)
    const canStart = canStartGame(state, isPending, isConnected)
    const gameId = state.game_id ?? ''

    return (
      <section
        aria-label="기록된 결과"
        className={styles.completedBox}
        style={{ borderColor: winnerColor }}
      >
        <div className={styles.completedMainRow}>
          <div className={styles.completedLeft}>
            <strong className={styles.completedTitle} style={{ color: winnerColor }}>
              {winnerLabel}
            </strong>
            <span className={styles.completedDesc}>{descText}</span>
          </div>
          <button
            type="button"
            className={styles.btnReverse}
            disabled={!canReverse}
            onClick={() => onReverse(gameId, winner)}
          >
            번복
          </button>
        </div>
        <div className={nextGameRowStyle(canStart)}>
          <button
            type="button"
            className={styles.btnNextGame}
            disabled={!canStart}
            onClick={() => onStart(state.game_id)}
          >
            다음 판 시작
          </button>
        </div>
      </section>
    )
  }

  return null
}

function nextGameRowStyle(_canStart: boolean): string {
  return styles.nextGameRow
}
