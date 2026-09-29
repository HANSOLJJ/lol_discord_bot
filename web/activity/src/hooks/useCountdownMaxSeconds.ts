// 카운트다운 진행 막대의 전체 길이(초)를 카운트다운마다 처음 본 남은 초로 보정하는 훅
import { useState } from 'react'
import type { Phase } from '../lib/protocol.ts'
import { type CountdownPeak, getCountdownMaxSeconds, nextCountdownPeak } from '../lib/view-logic.ts'

export function useCountdownMaxSeconds(deadlineMs: number | null, seconds: number | null, phase: Phase | undefined): number {
  const [peak, setPeak] = useState<CountdownPeak>({ key: null, value: 0 })
  const next = nextCountdownPeak(peak, deadlineMs, seconds)
  // 이전 렌더 정보를 state로 갱신하는 React 권장 패턴이다(값이 바뀔 때만 다시 렌더).
  if (next !== peak) setPeak(next)
  return Math.max(getCountdownMaxSeconds(phase), next.value)
}
