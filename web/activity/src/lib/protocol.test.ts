// protocol.ts의 수신 메시지 검증 테스트
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { hello, state, USER } from '../test/fixtures.ts'
import { decodeServerMessage, parseServerMessage, parseTokenResponse } from './protocol.ts'

describe('parseServerMessage', () => {
  it('규격 예시 메시지를 받아들인다', () => {
    assert.ok(parseServerMessage(hello()))
    assert.ok(parseServerMessage(state()))
    assert.ok(parseServerMessage({ t: 'pong', id: 'p-3', c: 12345.67, s: 1790000000123 }))
    assert.ok(
      parseServerMessage({
        t: 'reply',
        id: 'k-7',
        ok: false,
        code: 'not_your_turn',
        message: '지금은 청명사냥꾼 님의 차례입니다.',
        state_version: 41,
      }),
    )
  })

  it('completed 상태의 result와 corrected를 정상적으로 검증한다', () => {
    const completed = state({
      phase: 'completed',
      result: {
        winner: 'team2',
        recorded_ms: 1790000900000,
        corrected: { from: 'team1', at_ms: 1790000960000 },
      },
    })
    assert.deepEqual(parseServerMessage(completed), completed)
  })

  it('protocol_version이 1이거나 다르면 거절한다', () => {
    assert.equal(parseServerMessage(state({ protocol_version: 1 })), null)
    assert.equal(parseServerMessage(state({ protocol_version: 3 })), null)
    assert.equal(parseServerMessage(state({ protocol_version: '2' })), null)
  })

  it('모르는 추가 필드는 허용한다', () => {
    const msg = { ...state(), future_field: { x: 1 } }
    assert.equal(parseServerMessage(msg), msg)
    assert.ok(parseServerMessage(hello({ extra: true, user: { ...USER, banner: 'b' } })))
  })

  it('필수 필드가 없으면 거부한다', () => {
    const { server_epoch: _drop, ...noEpoch } = state()
    assert.equal(parseServerMessage(noEpoch), null)
    assert.equal(parseServerMessage({ t: 'pong', id: 'p-1', c: 1 }), null)
    const { me: _me, ...noMe } = state()
    assert.equal(parseServerMessage(noMe), null)
    const { players: _players, ...noPlayers } = state()
    assert.equal(parseServerMessage(noPlayers), null)
    const { pick_order: _po, ...noPickOrder } = state()
    assert.equal(parseServerMessage(noPickOrder), null)
    const { champions: _champs, ...noChampions } = state()
    assert.equal(parseServerMessage(noChampions), null)
    const { selections: _sel, ...noSelections } = state()
    assert.equal(parseServerMessage(noSelections), null)
    // null로 보내야 하는 필드를 생략해도 거부한다.
    const { deadline_ms: _deadline, ...noDeadline } = state()
    assert.equal(parseServerMessage(noDeadline), null)
  })

  it('필드 타입이 다르면 거부한다', () => {
    assert.equal(parseServerMessage(state({ state_version: '3' })), null)
    assert.equal(parseServerMessage(state({ state_version: 1.5 })), null)
    assert.equal(parseServerMessage(state({ phase: 'unknown' })), null)
    assert.equal(parseServerMessage(state({ deadline_ms: '1790000020000' })), null)
    assert.equal(parseServerMessage(state({ selections: [] })), null)
    assert.equal(parseServerMessage(state({ selections: { a: 123 } })), null)
    assert.equal(parseServerMessage(state({ players: [{ id: '1', name: 'a', team: 'team3', wins: 0 }] })), null)
    assert.equal(parseServerMessage(state({ champions: [{ id: '1' }] })), null)
    assert.equal(parseServerMessage(state({ me: { id: USER.id, role: 'admin' } })), null)
    assert.equal(parseServerMessage(state({ me: { ...state().me, can_pick: 'true' } })), null)
    assert.equal(
      parseServerMessage(
        state({
          result: { winner: 'invalid', recorded_ms: 1000, corrected: null },
        }),
      ),
      null,
    )
    assert.equal(parseServerMessage(hello({ user: { ...USER, id: Number(USER.id) } })), null)
    assert.equal(parseServerMessage({ t: 'pong', id: 3, c: 1, s: 2 }), null)
    assert.equal(parseServerMessage({ t: 'reply', id: 'd-1', ok: 'false', code: 'x', message: null, state_version: 1 }), null)
  })

  it('모르는 t와 객체가 아닌 값을 거부한다', () => {
    assert.equal(parseServerMessage({ ...state(), t: 'pick' }), null)
    assert.equal(parseServerMessage({ ...state(), t: 'toString' }), null)
    assert.equal(parseServerMessage({ id: 'p-1', c: 1, s: 2 }), null)
    assert.equal(parseServerMessage(null), null)
    assert.equal(parseServerMessage([hello()]), null)
    assert.equal(parseServerMessage('hello'), null)
  })
})

describe('decodeServerMessage', () => {
  it('JSON 텍스트를 해석하고 JSON 오류는 거부한다', () => {
    assert.equal(decodeServerMessage(JSON.stringify(hello()))?.t, 'hello')
    assert.equal(decodeServerMessage('{not json'), null)
    assert.equal(decodeServerMessage(new ArrayBuffer(4)), null)
  })
})

describe('parseTokenResponse', () => {
  it('성공 응답을 검증한다', () => {
    const ok = { access_token: 'a', session: 's', session_expires_ms: 1790000000000, user: USER }
    assert.equal(parseTokenResponse(ok), ok)
    assert.equal(parseTokenResponse({ ...ok, session: null }), null)
    assert.equal(parseTokenResponse({ error: 'oauth_failed' }), null)
  })
})
