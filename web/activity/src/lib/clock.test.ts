// clock.ts의 기준점·남은 초·재측정 판단·RTT 통계 테스트
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  estimateServerNow,
  needsResync,
  pickAnchor,
  remainingSeconds,
  RESYNC_INTERVAL_MS,
  rttStats,
  type ClockAnchor,
} from './clock.ts'

describe('pickAnchor', () => {
  it('RTT가 가장 작은 샘플로 기준점을 잡는다', () => {
    const anchor = pickAnchor([
      { p0: 0, p1: 80, s: 1_000_050 },
      { p0: 100, p1: 130, s: 1_000_120 }, // RTT 30
      { p0: 200, p1: 260, s: 1_000_230 },
      { p0: 300, p1: 350, s: 1_000_330 },
      { p0: 400, p1: 440, s: 1_000_420 },
    ])
    assert.deepEqual(anchor, { serverMs: 1_000_135, perfMs: 130, rttMs: 30 })
  })

  it('유효하지 않은 샘플은 건너뛰고, 없으면 null이다', () => {
    assert.equal(pickAnchor([]), null)
    assert.equal(pickAnchor([{ p0: 10, p1: 5, s: 1 }]), null)
    const anchor = pickAnchor([
      { p0: 10, p1: 5, s: 1 },
      { p0: 0, p1: Number.NaN, s: 1 },
      { p0: 0, p1: 40, s: 500 },
    ])
    assert.deepEqual(anchor, { serverMs: 520, perfMs: 40, rttMs: 40 })
  })
})

describe('남은 초 계산', () => {
  const anchor: ClockAnchor = { serverMs: 10_000, perfMs: 1_000, rttMs: 20 }
  const deadlineMs = 30_000 // 기준점에서 20초 뒤

  it('주입한 시계의 경과 시간을 서버 시각에 더한다', () => {
    assert.equal(estimateServerNow(anchor, 1_000), 10_000)
    assert.equal(estimateServerNow(anchor, 6_500), 15_500)
  })

  it('시작 시점은 20초이고 남은 시간을 올림한다', () => {
    assert.equal(remainingSeconds(deadlineMs, anchor, 1_000), 20)
    assert.equal(remainingSeconds(deadlineMs, anchor, 1_001), 20)
    assert.equal(remainingSeconds(deadlineMs, anchor, 2_000), 19)
  })

  it('1초에서 0초로 넘어가는 경계', () => {
    const perfAtDeadline = 1_000 + 20_000
    assert.equal(remainingSeconds(deadlineMs, anchor, perfAtDeadline - 1_000), 1)
    assert.equal(remainingSeconds(deadlineMs, anchor, perfAtDeadline - 1), 1)
    assert.equal(remainingSeconds(deadlineMs, anchor, perfAtDeadline), 0)
  })

  it('마감 뒤에도 0 아래로 내려가지 않는다', () => {
    assert.equal(remainingSeconds(deadlineMs, anchor, 1_000 + 25_000), 0)
    assert.equal(remainingSeconds(deadlineMs, anchor, 1_000 + 999_999), 0)
  })
})

describe('needsResync', () => {
  it('측정한 적이 없거나 30초가 지나면 재측정한다', () => {
    assert.equal(needsResync(null, 0), true)
    assert.equal(needsResync(1_000, 1_000 + RESYNC_INTERVAL_MS - 1), false)
    assert.equal(needsResync(1_000, 1_000 + RESYNC_INTERVAL_MS), true)
  })
})

describe('rttStats', () => {
  it('샘플 수, p50, p95, 최대를 계산한다', () => {
    assert.deepEqual(rttStats([]), { count: 0, p50: null, p95: null, max: null })
    assert.deepEqual(rttStats([40]), { count: 1, p50: 40, p95: 40, max: 40 })
    const rtts = Array.from({ length: 20 }, (_, i) => (20 - i) * 10) // 200, 190, …, 10
    assert.deepEqual(rttStats(rtts), { count: 20, p50: 100, p95: 190, max: 200 })
  })
})
