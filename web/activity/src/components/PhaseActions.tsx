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
  /** 서버에 연결돼 있는지. 끊겨 있으면 모든 버튼을 막는다. */
  isConnected: boolean
  /** 앞서 보낸 요청의 응답을 기다리는 중인지. 그동안 버튼을 막아 같은 요청이 두 번 가지 않게 한다. */
  isPending: boolean
  /**
   * 새 판 시작. 화면에 떠 있는 판의 ID(없으면 null)를 함께 보낸다. 두 사람이 동시에 눌러도
   * 서버가 늦게 온 쪽을 stale_game으로 거절해 판이 두 번 만들어지지 않는다(ACTIVITY_PROTOCOL.md 9절).
   */
  onStart: (gameId: string | null) => void
  onReport: (gameId: string, winner: Team) => void
  /** 결과 번복. 지금 화면의 승리 팀을 보내, 그사이 다른 사람이 이미 번복했으면 서버가 거절하게 한다. */
  onReverse: (gameId: string, expectedWinner: Team) => void
}

/**
 * 카운트다운이 없는 단계의 버튼 영역. 게임 없음(none·aborted)이면 "게임 시작",
 * 결과 대기(awaiting_result)면 승리 팀 버튼과 "결과 없이 새 판", 기록 완료(completed)면 결과와 번복·다음 판 버튼을 보인다.
 * 버튼을 누를 수 있는지는 view-logic의 can* 함수가 서버의 me 권한과 연결·대기 상태로 판정한다.
 */
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
        {/* 게임을 중간에 접은 경우용. 실수로 누르지 않게 승리 팀 버튼과 떨어뜨려 둔다. 이전 판은 기록 없이 버려진다. */}
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

/** "다음 판 시작" 줄의 클래스. 지금은 버튼 활성 여부와 관계없이 같은 클래스를 돌려준다. */
function nextGameRowStyle(_canStart: boolean): string {
  return styles.nextGameRow
}
