// 개발 환경 미리보기 상태 생성 및 쿼리 파싱 모듈 테스트
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { getPreviewPhase, getPreviewState } from './preview.ts'

describe('getPreviewPhase', () => {
  it('URL 쿼리에서 preview 값을 추출한다', () => {
    assert.equal(getPreviewPhase('?preview=advantage_ban'), 'advantage_ban')
    assert.equal(getPreviewPhase('?preview=picking_forced_last&foo=bar'), 'picking_forced_last')
    assert.equal(getPreviewPhase('?foo=bar'), null)
    assert.equal(getPreviewPhase(''), null)
  })
})

describe('getPreviewState', () => {
  it('요구된 어드밴티지 및 강제픽 미리보기 키에 대해 적절한 상태를 반환한다', () => {
    const advBan = getPreviewState('advantage_ban')
    assert.ok(advBan)
    assert.equal(advBan.phase, 'advantage')
    assert.equal(advBan.advantage?.kind, 'ban')
    assert.equal(advBan.me.can_advantage, true)

    const advForce = getPreviewState('advantage_force')
    assert.ok(advForce)
    assert.equal(advForce.phase, 'advantage')
    assert.equal(advForce.advantage?.kind, 'force')
    assert.equal(advForce.me.can_advantage, true)

    const advWaiting = getPreviewState('advantage_waiting')
    assert.ok(advWaiting)
    assert.equal(advWaiting.phase, 'advantage')
    assert.equal(advWaiting.me.can_advantage, false)

    const pickBanned = getPreviewState('picking_banned')
    assert.ok(pickBanned)
    assert.equal(pickBanned.phase, 'picking')
    assert.equal(pickBanned.advantage?.kind, 'ban')
    assert.equal(pickBanned.advantage?.status, 'chosen')

    const pickForced = getPreviewState('picking_forced')
    assert.ok(pickForced)
    assert.equal(pickForced.phase, 'picking')
    assert.equal(pickForced.advantage?.kind, 'force')
    assert.equal(pickForced.advantage?.status, 'chosen')

    const pickForcedLast = getPreviewState('picking_forced_last')
    assert.ok(pickForcedLast)
    assert.equal(pickForcedLast.phase, 'picking')
    assert.equal(pickForcedLast.advantage?.kind, 'force')
    assert.equal(pickForcedLast.advantage?.status, 'chosen')
    assert.equal(pickForcedLast.me.can_pick, true)
  })

  it('기존 미리보기 키도 정상 지원한다', () => {
    assert.equal(getPreviewState('none')?.phase, 'none')
    assert.equal(getPreviewState('starting')?.phase, 'starting')
    assert.equal(getPreviewState('picking')?.phase, 'picking')
    assert.equal(getPreviewState('awaiting_result')?.phase, 'awaiting_result')
    assert.equal(getPreviewState('completed')?.phase, 'completed')
  })
})
