// 개발 환경 전용 미리보기 상태 및 URL 쿼리 파싱 모듈
import {
  awaitingResultState,
  completedReversedState,
  completedState,
  noneState,
  pickingMyTurnState,
  pickingOtherTurnState,
  pickingWarningState,
  startingState,
} from '../test/fixtures.ts'
import type { StateMessage } from './protocol.ts'

export type PreviewKey =
  | 'none'
  | 'starting'
  | 'picking'
  | 'picking_other'
  | 'picking_warning'
  | 'awaiting_result'
  | 'completed'
  | 'completed_reversed'

export function getPreviewPhase(search: string = typeof location !== 'undefined' ? location.search : ''): string | null {
  if (!import.meta.env.DEV) return null
  const params = new URLSearchParams(search)
  return params.get('preview')
}

export function getPreviewState(phaseKey: string | null): StateMessage | null {
  if (!import.meta.env.DEV || !phaseKey) return null
  const normalized = phaseKey.toLowerCase().replace(/-/g, '_')
  switch (normalized) {
    case 'none':
      return noneState()
    case 'starting':
      return startingState()
    case 'picking':
      return pickingMyTurnState()
    case 'picking_other':
      return pickingOtherTurnState()
    case 'picking_warning':
      return pickingWarningState()
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
