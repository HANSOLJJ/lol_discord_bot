// requestAnimationFrame으로 남은 초를 계산하고 표시할 초가 바뀔 때만 상태를 갱신하는 훅
import { useEffect, useState } from 'react'
import { remainingSeconds, type ClockAnchor } from '../lib/clock.ts'

interface Shown {
  deadlineMs: number
  seconds: number
}

export function useRemainingSeconds(deadlineMs: number | null, anchor: ClockAnchor | null): number | null {
  const [shown, setShown] = useState<Shown | null>(null)

  useEffect(() => {
    if (deadlineMs === null || anchor === null) return
    let frame = 0
    let last: number | null = null
    const tick = () => {
      const seconds = remainingSeconds(deadlineMs, anchor, performance.now())
      if (seconds !== last) {
        last = seconds
        setShown({ deadlineMs, seconds })
      }
      // 0이 되면 서버의 다음 state를 기다리므로 더 계산하지 않는다.
      if (seconds > 0) frame = requestAnimationFrame(tick)
    }
    tick()
    return () => cancelAnimationFrame(frame)
  }, [deadlineMs, anchor])

  // 새 마감의 첫 계산 전에는 이전 마감의 숫자를 보여주지 않는다.
  if (deadlineMs === null || anchor === null || shown === null || shown.deadlineMs !== deadlineMs) return null
  return shown.seconds
}
