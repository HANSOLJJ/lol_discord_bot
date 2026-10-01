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
  isChampionBanned,
  isChampionForced,
  isChampionLocked,
  isMyTurn,
} from '../lib/view-logic.ts'
import styles from './ChampionGrid.module.css'

interface Props {
  state: StateMessage | null
  /** 앞 요청의 응답을 기다리는 중이면 카드를 누를 수 없다. */
  isPending: boolean
  isPc?: boolean
  /** 카드를 눌렀을 때. 어드밴티지 지정인지 일반 픽인지는 ActivityScreen이 단계를 보고 나눈다. */
  onPick: (championId: string) => void
}

/**
 * 카드 위쪽 초상화 영역. 이미지를 못 불러오면 첫 글자로 대신하고,
 * 이미 뽑혔거나 밴된 카드는 흑백 처리와 자물쇠를, 강제픽 카드는 "강제픽" 배지를 얹는다.
 */
function ChampionCardImage({
  champion,
  ddragonVersion,
  locked,
  banned,
  forced,
  isPc,
}: {
  champion: Champion
  ddragonVersion: string | null
  locked: boolean
  banned: boolean
  forced: boolean
  isPc: boolean
}) {
  const [failed, setFailed] = useState(false)
  const url = getChampionPortraitUrl(champion.id, ddragonVersion)

  const wrapClass = isPc ? styles.imgWrapPc : styles.imgWrapMobile
  const imgClass = isPc ? styles.imgPc : styles.imgMobile
  const fallbackClass = isPc ? styles.fallbackCirclePc : styles.fallbackCircleMobile

  const initial = champion.name.trim().charAt(0) || '?'
  const showOverlay = locked || banned

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
          style={{ filter: showOverlay ? 'grayscale(80%)' : 'none' }}
          loading="lazy"
          onError={() => setFailed(true)}
        />
      )}
      {forced && !locked && (
        <span className={styles.forcedBadge}>강제픽</span>
      )}
      {showOverlay && (
        <div className={styles.lockOverlay}>
          <svg
            width={isPc ? 24 : 20}
            height={isPc ? 24 : 20}
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
          {banned && <span className={styles.banOverlayText}>밴</span>}
        </div>
      )}
    </div>
  )
}

/**
 * 챔피언 후보 카드 그리드(PC·모바일 모두 4x2). advantage 단계에서는 밴·강제픽 지정에, picking 단계에서는 픽에 쓴다.
 * 누를 수 있는지는 canClickChampion이 판정하고, 이 컴포넌트는 카드 상태별 색과 문구만 정한다.
 */
export function ChampionGrid({ state, isPending, isPc = false, onPick }: Props) {
  if (!state || state.champions.length === 0) return null

  const myTurn = isMyTurn(state)
  const isAdvantagePhase = state.phase === 'advantage'

  return (
    <section aria-label="챔피언 후보" className={styles.section}>
      <span className={styles.title}>챔피언 후보</span>
      <div className={isPc ? styles.gridPc : styles.gridMobile}>
        {state.champions.map((champion) => {
          const locked = isChampionLocked(champion.id, state.selections)
          const banned = isChampionBanned(champion.id, state.advantage)
          const forced = isChampionForced(champion.id, state.advantage)
          const clickable = canClickChampion(champion.id, state, isPending)
          // 내 차례인데 규칙(강제픽 마지막 차례 등) 때문에 못 고르는 카드는 흐리게 보여 준다.
          const ruleBlocked = myTurn && !isPending && !clickable && !locked && !banned
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

          // 카드 상태별 표시. 우선순위는 밴 > 이미 뽑힘 > 강제픽 > 어드밴티지 단계 > 일반 픽 단계이다.
          // 누를 수 있는 카드는 밝은 테두리(#9aa4bb)로 구분한다.
          let borderColor = '#262b36'
          let tileBg = '#171a21'
          let nameColor = '#e6e9ef'
          let pickerLabel = ' '
          let labelColor = teamColor ?? COLOR_MUTED
          let ariaLabel = champion.name

          if (banned) {
            borderColor = '#3a3f4d'
            tileBg = '#12141a'
            nameColor = COLOR_MUTED
            pickerLabel = '밴'
            labelColor = '#ff5b5b'
            ariaLabel = `${champion.name}, 밴됨`
          } else if (locked) {
            borderColor = teamColor ?? '#262b36'
            tileBg = '#12141a'
            nameColor = COLOR_MUTED
            pickerLabel = pickerInfo
              ? `${pickerInfo.picker.name}${pickerInfo.auto ? ' · 자동' : ''}`
              : ' '
            ariaLabel = pickerInfo
              ? `${champion.name}, ${pickerInfo.picker.name} 선택`
              : champion.name
          } else if (forced) {
            borderColor = '#f97316'
            tileBg = '#171a21'
            nameColor = '#e6e9ef'
            pickerLabel = '강제픽'
            labelColor = '#f97316'
            ariaLabel = `${champion.name}, 강제픽`
          } else if (isAdvantagePhase) {
            borderColor = state.me.can_advantage ? '#9aa4bb' : '#262b36'
            tileBg = '#171a21'
            nameColor = '#e6e9ef'
            ariaLabel = state.me.can_advantage ? `${champion.name} 선택하기` : champion.name
          } else {
            borderColor = myTurn && !ruleBlocked ? '#9aa4bb' : '#262b36'
            tileBg = '#171a21'
            nameColor = '#e6e9ef'
            ariaLabel = myTurn && !ruleBlocked ? `${champion.name} 선택하기` : champion.name
          }

          const cardClass = `${isPc ? styles.cardPc : styles.cardMobile} ${clickable ? styles.cardClickable : ''}`

          return (
            <button
              key={champion.id}
              type="button"
              disabled={!clickable}
              onClick={() => onPick(champion.id)}
              aria-label={ariaLabel}
              className={cardClass}
              style={{
                background: tileBg,
                border: `2px solid ${borderColor}`,
                cursor: clickable ? 'pointer' : 'default',
                opacity: ruleBlocked ? 0.4 : 1,
              }}
            >
              <ChampionCardImage
                champion={champion}
                ddragonVersion={state.ddragon_version}
                locked={locked}
                banned={banned}
                forced={forced}
                isPc={isPc}
              />
              <span className={isPc ? styles.namePc : styles.nameMobile} style={{ color: nameColor }}>
                {champion.name}
              </span>
              <span
                className={isPc ? styles.pickerLabelPc : styles.pickerLabelMobile}
                style={{ color: labelColor }}
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
