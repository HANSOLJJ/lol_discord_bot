// 픽 화면의 차례·잠금·색상·버튼 활성화 등 순수 뷰 계산 모듈
import type { AdvantageState, Champion, Phase, Player, StateMessage, Team } from './protocol.ts'

export const COLOR_TEAM1 = '#5b8cff'
export const COLOR_TEAM2 = '#ff6b5e'
export const COLOR_YELLOW = '#facc15'
export const COLOR_WARNING_RED = '#ff3b3b'
export const COLOR_MUTED = '#8b93a7'
export const COLOR_BORDER_DEFAULT = '#262b36'

export function getTeamColor(team: Team): string {
  return team === 'team1' ? COLOR_TEAM1 : COLOR_TEAM2
}

/** 현재 차례의 플레이어를 구한다. */
export function getCurrentPicker(state: StateMessage): Player | null {
  if (state.phase !== 'picking' || state.current_index === null) return null
  const pickerId = state.pick_order[state.current_index]
  if (!pickerId) return null
  return state.players.find((p) => p.id === pickerId) ?? null
}

/** 내가 지금 픽해야 하는 차례인지 판정한다. */
export function isMyTurn(state: StateMessage): boolean {
  return state.phase === 'picking' && state.me.can_pick === true
}

/** 남은 시간이 5초 이하 경고 구간인지 판정한다. */
export function isWarningSeconds(seconds: number | null): boolean {
  return seconds !== null && seconds <= 5
}

/** 카운트다운 숫자 및 프로그레스 바 색상을 결정한다. 5초 이하는 #ff3b3b, 평소는 #facc15. */
export function getCountAndBarColor(seconds: number | null): string {
  return isWarningSeconds(seconds) ? COLOR_WARNING_RED : COLOR_YELLOW
}

/** 현재 차례 테두리 색상을 결정한다. 내 차례면 노란색, 남의 차례면 기본 테두리. */
export function getTurnBorderColor(myTurn: boolean): string {
  return myTurn ? COLOR_YELLOW : COLOR_BORDER_DEFAULT
}

/** 챔피언이 이미 뽑혔는지 여부를 확인한다. */
export function isChampionLocked(championId: string, selections: Record<string, string>): boolean {
  return Object.values(selections).includes(championId)
}

/** 챔피언이 밴되었는지 여부를 확인한다. */
export function isChampionBanned(championId: string, advantage: AdvantageState | null): boolean {
  return advantage?.kind === 'ban' && advantage.status === 'chosen' && advantage.champion_id === championId
}

/** 챔피언이 상대 팀 강제픽으로 지정되었는지 여부를 확인한다. */
export function isChampionForced(championId: string, advantage: AdvantageState | null): boolean {
  return advantage?.kind === 'force' && advantage.status === 'chosen' && advantage.champion_id === championId
}

/** 강제픽 챔피언이 아직 선택되지 않고 남아 있는지 확인한다. */
export function isForcedChampionRemaining(state: StateMessage): boolean {
  const adv = state.advantage
  if (!adv || adv.kind !== 'force' || adv.status !== 'chosen' || !adv.champion_id) {
    return false
  }
  return !isChampionLocked(adv.champion_id, state.selections)
}

/** 현재 차례가 상대 팀(강제픽 대상 팀)의 마지막 차례인지 판정한다. */
export function isLastTurnOfOpponent(state: StateMessage): boolean {
  if (state.phase !== 'picking' || state.current_index === null || !state.advantage) return false
  if (state.advantage.kind !== 'force' || state.advantage.status !== 'chosen') return false

  const opponentTeam: Team = state.advantage.team === 'team1' ? 'team2' : 'team1'
  const currentPicker = getCurrentPicker(state)
  if (!currentPicker || currentPicker.team !== opponentTeam) return false

  // pick_order에서 현재 인덱스 이후에 상대 팀 선수가 더 이상 없는지 확인
  const remainingPickers = state.pick_order.slice(state.current_index + 1)
  const hasRemainingOpponent = remainingPickers.some((id) => {
    const p = state.players.find((pl) => pl.id === id)
    return p?.team === opponentTeam
  })
  return !hasRemainingOpponent
}

/** 상대 팀의 마지막 차례에 강제픽이 남아 있어 강제픽만 골라야 하는 상황인지 판정한다. */
export function mustPickForced(state: StateMessage): boolean {
  return isForcedChampionRemaining(state) && isLastTurnOfOpponent(state)
}

export interface ChampionPickerInfo {
  picker: Player
  auto: boolean
}

/** 챔피언을 선택한 플레이어 및 자동 배정 여부를 반환한다. */
export function getChampionPicker(
  championId: string,
  selections: Record<string, string>,
  players: Player[],
  autoAssigned: string[],
): ChampionPickerInfo | null {
  const userId = Object.keys(selections).find((uid) => selections[uid] === championId)
  if (!userId) return null
  const picker = players.find((p) => p.id === userId)
  if (!picker) return null
  return {
    picker,
    auto: autoAssigned.includes(userId),
  }
}

/** 챔피언 카드를 클릭하여 픽 또는 어드밴티지 선택을 할 수 있는지 여부를 판정한다. */
export function canClickChampion(championId: string, state: StateMessage, isPending: boolean): boolean {
  if (isPending) return false

  // advantage 단계: me.can_advantage일 때 모든 후보 선택 가능
  if (state.phase === 'advantage') {
    return state.me.can_advantage === true
  }

  // picking 단계
  if (state.phase === 'picking') {
    if (!state.me.can_pick) return false
    if (isChampionLocked(championId, state.selections)) return false
    if (isChampionBanned(championId, state.advantage)) return false

    // 강제픽 관련 판정
    const adv = state.advantage
    if (adv && adv.kind === 'force' && adv.status === 'chosen') {
      const isForcedChamp = adv.champion_id === championId
      const currentPicker = getCurrentPicker(state)

      // 이점 팀의 차례에는 강제픽 카드를 누를 수 없다.
      if (isForcedChamp && currentPicker?.team === adv.team) {
        return false
      }

      // 상대 팀의 마지막 차례에 강제픽이 아직 남아 있다면 강제픽 카드만 누를 수 있다.
      if (mustPickForced(state) && !isForcedChamp) {
        return false
      }
    }

    return true
  }

  return false
}

/** 팀 구성 쪽에 표시할 이점 요약 한 줄 문구를 반환한다. */
export function getAdvantageSummary(
  advantage: AdvantageState | null,
  champions: Champion[],
  phase?: Phase,
): string | null {
  if (!advantage) return null

  if (advantage.status === 'skipped') {
    return '시간 초과로 어드밴티지 없음'
  }

  const teamLabel = advantage.team === 'team1' ? 'TEAM 1' : 'TEAM 2'
  const kindLabel = advantage.kind === 'ban' ? '밴' : '강제픽'

  if (advantage.status === 'chosen') {
    const champName = champions.find((c) => c.id === advantage.champion_id)?.name ?? advantage.champion_id ?? ''
    return `${teamLabel} 어드밴티지 · ${kindLabel}: ${champName}`
  }

  if (advantage.status === 'pending') {
    if (phase === 'starting') {
      return `${teamLabel} 어드밴티지 예정 · ${kindLabel}`
    }
    return `${teamLabel} 어드밴티지 · ${kindLabel} 선택 중`
  }

  return null
}

/** advantage 단계 카운트다운 박스에 표시할 안내 정보를 반환한다. */
export function getAdvantageHeaderInfo(state: StateMessage): {
  title: string
  hint: string
  teamLabel: string
  teamColor: string
} | null {
  if (state.phase !== 'advantage' || !state.advantage) return null

  const teamLabel = state.advantage.team === 'team1' ? 'TEAM 1' : 'TEAM 2'
  const teamColor = state.advantage.team === 'team1' ? COLOR_TEAM1 : COLOR_TEAM2
  const kindText = state.advantage.kind === 'ban' ? '밴할 챔피언 1개' : '상대 팀 강제픽 1개'
  const title = `${teamLabel} 어드밴티지 · ${kindText}`
  const hint = state.me.can_advantage ? '챔피언을 누르면 바로 확정됩니다' : `${teamLabel}가 고르는 중`

  return { title, hint, teamLabel, teamColor }
}

/** 게임 시작 버튼을 활성화할 수 있는지 판정한다. */
export function canStartGame(state: StateMessage | null, isPending: boolean, isConnected: boolean): boolean {
  if (!isConnected || isPending) return false
  if (!state) return true
  return state.me.can_start
}

/** 승리 보고 버튼을 누를 수 있는지 판정한다. */
export function canReportWinner(state: StateMessage, isPending: boolean, isConnected: boolean): boolean {
  if (!isConnected || isPending) return false
  return state.phase === 'awaiting_result' && state.me.can_report
}

/** 번복 버튼을 누를 수 있는지 판정한다. */
export function canReverseGame(state: StateMessage, isPending: boolean, isConnected: boolean): boolean {
  if (!isConnected || isPending) return false
  return state.phase === 'completed' && state.me.can_reverse
}

/** Data Dragon 초상화 이미지 URL을 생성한다. */
export function getChampionPortraitUrl(championId: string, ddragonVersion: string | null): string | null {
  if (!ddragonVersion) return null
  return `/ddragon/cdn/${ddragonVersion}/img/champion/${championId}.png`
}
