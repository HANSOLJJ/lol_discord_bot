// 픽 화면의 차례·잠금·색상·버튼 활성화 등 순수 뷰 계산 모듈
import type { Player, StateMessage, Team } from './protocol.ts'

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

/** 챔피언 카드를 클릭하여 픽할 수 있는지 여부를 판정한다. */
export function canClickChampion(championId: string, state: StateMessage, isPending: boolean): boolean {
  if (isPending) return false
  if (state.phase !== 'picking' || !state.me.can_pick) return false
  return !isChampionLocked(championId, state.selections)
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
