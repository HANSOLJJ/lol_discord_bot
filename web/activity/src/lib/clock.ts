// ping 샘플로 서버 시각 기준점을 잡고 보정된 서버 시각·남은 초·RTT 통계를 계산하는 모듈 (React 비의존)

/** performance.now()처럼 단조 증가하는 밀리초 시계. 테스트에서 주입한다. */
export type MonotonicClock = () => number

export const PING_SAMPLE_COUNT = 5
export const RESYNC_INTERVAL_MS = 30_000

/** p0, p1은 ping 송신·pong 수신 시각(단조 시계), s는 pong의 서버 유닉스 밀리초이다. */
export interface PingSample {
  p0: number
  p1: number
  s: number
}

export interface ClockAnchor {
  /** 기준 시점의 추정 서버 시각(유닉스 밀리초) */
  serverMs: number
  /** 기준 시점의 단조 시계 값 */
  perfMs: number
  rttMs: number
}

export interface RttStats {
  count: number
  p50: number | null
  p95: number | null
  max: number | null
}

const isValidSample = (x: PingSample) =>
  Number.isFinite(x.p0) && Number.isFinite(x.p1) && Number.isFinite(x.s) && x.p1 >= x.p0

/** RTT가 가장 작은 유효 샘플로 기준점을 만든다. 유효 샘플이 없으면 null이다. */
export function pickAnchor(samples: readonly PingSample[]): ClockAnchor | null {
  let best: PingSample | null = null
  for (const x of samples) {
    if (isValidSample(x) && (best === null || x.p1 - x.p0 < best.p1 - best.p0)) best = x
  }
  if (best === null) return null
  const rttMs = best.p1 - best.p0
  return { serverMs: best.s + rttMs / 2, perfMs: best.p1, rttMs }
}

/** 기준점에 단조 시계의 경과 시간을 더한 현재 서버 시각 추정값 */
export function estimateServerNow(anchor: ClockAnchor, perfNow: number): number {
  return anchor.serverMs + (perfNow - anchor.perfMs)
}

/** 마감까지 남은 초. 올림하고 0 아래로 내려가지 않는다. */
export function remainingSeconds(deadlineMs: number, anchor: ClockAnchor, perfNow: number): number {
  return Math.max(0, Math.ceil((deadlineMs - estimateServerNow(anchor, perfNow)) / 1000))
}

/** 마지막 측정 이후 재측정 주기가 지났는지 판단한다. 측정한 적이 없으면 true이다. */
export function needsResync(lastMeasuredPerfMs: number | null, perfNow: number): boolean {
  return lastMeasuredPerfMs === null || perfNow - lastMeasuredPerfMs >= RESYNC_INTERVAL_MS
}

/** 가장 가까운 순위(nearest-rank) 방식의 백분위수 */
function percentile(sorted: readonly number[], q: number): number {
  const rank = Math.ceil(q * sorted.length)
  return sorted[Math.min(sorted.length, Math.max(1, rank)) - 1]
}

export function rttStats(rtts: readonly number[]): RttStats {
  if (rtts.length === 0) return { count: 0, p50: null, p95: null, max: null }
  const sorted = [...rtts].sort((a, b) => a - b)
  return {
    count: sorted.length,
    p50: percentile(sorted, 0.5),
    p95: percentile(sorted, 0.95),
    max: sorted[sorted.length - 1],
  }
}
