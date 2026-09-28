// 작은 창(Pip) 요약 화면: 카운트다운 숫자, 차례 안내, 6개 진행 원 슬롯
import { useState } from 'react'
import { useRemainingSeconds } from '../hooks/useRemainingSeconds.ts'
import type { ClockAnchor } from '../lib/clock.ts'
import type { Champion, StateMessage } from '../lib/protocol.ts'
import {
  COLOR_TEAM1,
  COLOR_TEAM2,
  COLOR_WARNING_RED,
  COLOR_YELLOW,
  getChampionPortraitUrl,
  getCurrentPicker,
  isMyTurn,
  isWarningSeconds,
} from '../lib/view-logic.ts'
import styles from './PipView.module.css'

interface Props {
  state: StateMessage | null
  anchor: ClockAnchor | null
}

function PipSlotImage({ champion, ddragonVersion }: { champion: Champion; ddragonVersion: string | null }) {
  const [failed, setFailed] = useState(false)
  const url = getChampionPortraitUrl(champion.id, ddragonVersion)

  if (!url || failed) {
    const initial = champion.name.trim().charAt(0) || '?'
    return <span className={styles.slotFallback}>{initial}</span>
  }

  return (
    <img
      src={url}
      alt=""
      className={styles.slotImg}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  )
}

export function PipView({ state, anchor }: Props) {
  const isStarting = state?.phase === 'starting'
  const isPicking = state?.phase === 'picking'
  const deadlineMs = isPicking ? state?.deadline_ms ?? null : isStarting ? state?.start_at_ms ?? null : null
  const seconds = useRemainingSeconds(deadlineMs, anchor)

  const myTurn = state ? isMyTurn(state) : false
  const picker = state ? getCurrentPicker(state) : null

  const warning = isWarningSeconds(seconds)
  const color = warning ? COLOR_WARNING_RED : COLOR_YELLOW
  const frameBorder = myTurn ? COLOR_YELLOW : '#262b36'

  let title = '대기 중'
  let hint = '게임이 시작되면 여기에 표시됩니다'

  if (state?.phase === 'starting') {
    title = '게임 시작 준비 중'
    hint = '곧 픽이 시작됩니다'
  } else if (state?.phase === 'picking') {
    title = myTurn ? '내 차례입니다!' : picker ? `${picker.name} 님이 고르는 중` : '선택 진행 중'
    hint = myTurn ? '창을 눌러 크게 열고 고르세요' : '내 차례가 오면 여기에 표시됩니다'
  } else if (state?.phase === 'awaiting_result') {
    title = '모든 선택 완료'
    hint = '승리 팀 결과 입력 대기 중'
  } else if (state?.phase === 'completed') {
    const winner = state.result?.winner === 'team1' ? 'TEAM 1' : 'TEAM 2'
    title = `${winner} 승리!`
    hint = state.result?.corrected ? '결과 번복됨' : '전적에 반영됨'
  }

  const maxSeconds = isStarting ? 15 : 20
  const currentSeconds = seconds ?? 0
  const progressPercent = Math.min(100, Math.max(0, Math.round((currentSeconds / maxSeconds) * 100)))

  const pickOrder = state?.pick_order ?? []
  const currentIndex = state?.phase === 'picking' ? state.current_index : null

  return (
    <div className={styles.pipBox} style={{ border: `2px solid ${frameBorder}` }}>
      <div className={styles.topRow}>
        <div className={styles.countNum} style={{ color }}>
          {seconds !== null && seconds > 0 ? (
            seconds
          ) : seconds === 0 ? (
            <span className={styles.countClosing}>마감 확인 중…</span>
          ) : (
            '–'
          )}
        </div>
        <div className={styles.titleHintCol}>
          <strong className={styles.title}>{title}</strong>
          <span className={styles.hint}>{hint}</span>
        </div>
      </div>

      <div className={styles.bottomCol}>
        <div className={styles.slotsRow}>
          {pickOrder.map((userId, idx) => {
            const player = state?.players.find((p) => p.id === userId)
            const teamColor = player?.team === 'team1' ? COLOR_TEAM1 : COLOR_TEAM2
            const isCurrent = idx === currentIndex
            const ring = isCurrent ? COLOR_YELLOW : teamColor
            const champId = state?.selections[userId]
            const champ = champId ? state?.champions.find((c) => c.id === champId) : null

            return (
              <div key={userId} className={styles.slot} style={{ border: `2px solid ${ring}` }}>
                {champ ? (
                  <PipSlotImage champion={champ} ddragonVersion={state?.ddragon_version ?? null} />
                ) : (
                  <span className={styles.slotNum} style={{ color: ring }}>
                    {idx + 1}
                  </span>
                )}
              </div>
            )
          })}
        </div>

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
    </div>
  )
}
