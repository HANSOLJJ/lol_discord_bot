// 챔피언 후보 4x2 그리드(초상화, 자물쇠 오버레이, 픽 클릭) 컴포넌트
import { useState } from 'react'
import type { Champion, StateMessage } from '../lib/protocol.ts'
import {
  canClickChampion,
  COLOR_MUTED,
  COLOR_TEAM1,
  COLOR_TEAM2,
  getChampionPicker,
  getChampionPortraitUrl,
  isChampionLocked,
  isMyTurn,
} from '../lib/view-logic.ts'
import styles from './ChampionGrid.module.css'

interface Props {
  state: StateMessage | null
  isPending: boolean
  isPc?: boolean
  onPick: (championId: string) => void
}

function ChampionCardImage({
  champion,
  ddragonVersion,
  locked,
  isPc,
}: {
  champion: Champion
  ddragonVersion: string | null
  locked: boolean
  isPc: boolean
}) {
  const [failed, setFailed] = useState(false)
  const url = getChampionPortraitUrl(champion.id, ddragonVersion)

  const wrapClass = isPc ? styles.imgWrapPc : styles.imgWrapMobile
  const imgClass = isPc ? styles.imgPc : styles.imgMobile
  const fallbackClass = isPc ? styles.fallbackCirclePc : styles.fallbackCircleMobile

  const initial = champion.name.trim().charAt(0) || '?'

  return (
    <div className={wrapClass}>
      {!url || failed ? (
        <div className={fallbackClass} aria-hidden="true">
          {initial}
        </div>
      ) : (
        <img
          src={url}
          alt=""
          className={imgClass}
          style={{ filter: locked ? 'grayscale(80%)' : 'none' }}
          loading="lazy"
          onError={() => setFailed(true)}
        />
      )}
      {locked && (
        <div className={styles.lockOverlay}>
          <svg
            width={isPc ? 28 : 24}
            height={isPc ? 28 : 24}
            viewBox="0 0 24 24"
            fill="none"
            stroke="#ffffff"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <rect x="5" y="11" width="14" height="10" rx="2" />
            <path d="M8 11V7a4 4 0 0 1 8 0v4" />
          </svg>
        </div>
      )}
    </div>
  )
}

export function ChampionGrid({ state, isPending, isPc = false, onPick }: Props) {
  if (!state || state.champions.length === 0) return null

  const myTurn = isMyTurn(state)

  return (
    <section aria-label="챔피언 후보" className={styles.section}>
      <span className={styles.title}>챔피언 후보</span>
      <div className={isPc ? styles.gridPc : styles.gridMobile}>
        {state.champions.map((champion) => {
          const locked = isChampionLocked(champion.id, state.selections)
          const clickable = canClickChampion(champion.id, state, isPending)
          const pickerInfo = getChampionPicker(
            champion.id,
            state.selections,
            state.players,
            state.auto_assigned,
          )

          const teamColor =
            pickerInfo?.picker.team === 'team1'
              ? COLOR_TEAM1
              : pickerInfo?.picker.team === 'team2'
                ? COLOR_TEAM2
                : null

          const borderColor = locked
            ? teamColor ?? '#262b36'
            : myTurn
              ? '#9aa4bb'
              : '#262b36'

          const tileBg = locked ? '#12141a' : '#171a21'
          const nameColor = locked ? COLOR_MUTED : '#e6e9ef'
          const pickerLabel = pickerInfo
            ? `${pickerInfo.picker.name}${pickerInfo.auto ? ' · 자동' : ''}`
            : ' '

          const cardClass = `${isPc ? styles.cardPc : styles.cardMobile} ${clickable ? styles.cardClickable : ''}`

          return (
            <button
              key={champion.id}
              type="button"
              disabled={!clickable}
              onClick={() => onPick(champion.id)}
              aria-label={
                locked && pickerInfo
                  ? `${champion.name}, ${pickerInfo.picker.name} 선택`
                  : myTurn
                    ? `${champion.name} 선택하기`
                    : champion.name
              }
              className={cardClass}
              style={{
                background: tileBg,
                border: `2px solid ${borderColor}`,
                cursor: clickable ? 'pointer' : 'default',
              }}
            >
              <ChampionCardImage
                champion={champion}
                ddragonVersion={state.ddragon_version}
                locked={locked}
                isPc={isPc}
              />
              <span className={isPc ? styles.namePc : styles.nameMobile} style={{ color: nameColor }}>
                {champion.name}
              </span>
              <span
                className={isPc ? styles.pickerLabelPc : styles.pickerLabelMobile}
                style={{ color: teamColor ?? COLOR_MUTED }}
                title={pickerLabel.trim()}
              >
                {pickerLabel}
              </span>
            </button>
          )
        })}
      </div>
    </section>
  )
}
