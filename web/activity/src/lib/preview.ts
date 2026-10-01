// 개발 환경 전용 미리보기 상태 및 URL 쿼리 파싱 모듈
import {
  advantageBanPendingState,
  advantageForcePendingState,
  advantageWaitingState,
  awaitingResultState,
  completedReversedState,
  completedState,
  noneState,
  pickingBannedState,
  pickingForcedLastState,
  pickingForcedState,
  pickingMyTurnState,
  pickingOtherTurnState,
  pickingPausedState,
  pickingWarningState,
  startingCountdownState,
  startingPausedState,
  startingState,
} from '../test/fixtures.ts'
import type { StateMessage } from './protocol.ts'

/** ?preview=로 고를 수 있는 고정 상태 이름. 실제 state 내용은 test/fixtures.ts가 만든다. */
export type PreviewKey =
  | 'none'
  | 'starting'
  | 'starting_countdown'
  | 'starting_paused'
  | 'advantage_ban'
  | 'advantage_force'
  | 'advantage_waiting'
  | 'picking'
  | 'picking_other'
  | 'picking_warning'
  | 'picking_paused'
  | 'picking_banned'
  | 'picking_forced'
  | 'picking_forced_last'
  | 'awaiting_result'
  | 'completed'
  | 'completed_reversed'

/** 개발 환경에서만 주소의 ?preview= 값을 읽는다. 운영 빌드에서는 언제나 null이다. */
export function getPreviewPhase(search: string = typeof location !== 'undefined' ? location.search : ''): string | null {
  // node --test처럼 import.meta.env가 없는 환경은 개발로 보아 테스트할 수 있게 한다.
  const isDev = Boolean((import.meta as unknown as { env?: { DEV?: boolean } }).env?.DEV ?? true)
  if (!isDev) return null
  const params = new URLSearchParams(search)
  return params.get('preview')
}

/** 미리보기 이름을 고정 state로 바꾼다. 대소문자와 하이픈(-)은 가리지 않고, 모르는 이름이면 null이다. reversed는 completed_reversed의 별칭이다. */
export function getPreviewState(phaseKey: string | null): StateMessage | null {
  const isDev = Boolean((import.meta as unknown as { env?: { DEV?: boolean } }).env?.DEV ?? true)
  if (!isDev || !phaseKey) return null
  const normalized = phaseKey.toLowerCase().replace(/-/g, '_')
  switch (normalized) {
    case 'none':
      return noneState()
    case 'starting':
      return startingState()
    case 'starting_countdown':
      return startingCountdownState()
    case 'starting_paused':
      return startingPausedState()
    case 'advantage_ban':
      return advantageBanPendingState()
    case 'advantage_force':
      return advantageForcePendingState()
    case 'advantage_waiting':
      return advantageWaitingState()
    case 'picking':
      return pickingMyTurnState()
    case 'picking_other':
      return pickingOtherTurnState()
    case 'picking_warning':
      return pickingWarningState()
    case 'picking_paused':
      return pickingPausedState()
    case 'picking_banned':
      return pickingBannedState()
    case 'picking_forced':
      return pickingForcedState()
    case 'picking_forced_last':
      return pickingForcedLastState()
    case 'awaiting_result':
      return awaitingResultState()
    case 'completed':
      return completedState()
    case 'completed_reversed':
    case 'reversed':
      return completedReversedState()
    default:
      return null
  }
}
