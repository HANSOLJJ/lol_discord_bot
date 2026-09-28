// connection.ts의 상태 적용·재접속·재인증·시계 측정·정리 테스트
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { fakeEnv, type FakeSocket } from '../test/fakes.ts'
import { hello, state } from '../test/fixtures.ts'
import { RESYNC_INTERVAL_MS } from './clock.ts'
import { buildSocketUrl, Connection } from './connection.ts'

type Env = ReturnType<typeof fakeEnv>

/** 가장 최근 ping에 차례로 pong을 돌려준다. 서버 시계는 단조 시계 + 1_000_000으로 둔다. */
function answerPings(env: Env, socket: FakeSocket, rtts: number[]): void {
  for (const rtt of rtts) {
    const pings = socket.sentOf('ping')
    const ping = pings[pings.length - 1]
    const sentAt = ping.c as number
    env.clock.now = sentAt + rtt
    socket.receive({ t: 'pong', id: ping.id, c: ping.c, s: 1_000_000 + sentAt + rtt / 2 })
  }
}

function handshake(env: Env, socket: FakeSocket, epoch = 'epoch-a', version = 0): void {
  socket.open()
  socket.receive(hello({ server_epoch: epoch }))
  socket.receive(state({ server_epoch: epoch, state_version: version }))
  answerPings(env, socket, [40, 40, 40, 40, 40])
}

function setup() {
  const env = fakeEnv()
  const conn = new Connection(env.options)
  conn.start('sess')
  return { env, conn }
}

describe('Connection 상태 적용', () => {
  it('같은 epoch의 더 낮거나 같은 state_version을 무시한다', () => {
    const { env, conn } = setup()
    const s1 = env.last()
    handshake(env, s1, 'epoch-a', 5)
    assert.equal(conn.getSnapshot().state?.state_version, 5)

    s1.receive(state({ state_version: 4, phase: 'picking' }))
    assert.equal(conn.getSnapshot().state?.phase, 'none')
    s1.receive(state({ state_version: 5, phase: 'picking' }))
    assert.equal(conn.getSnapshot().state?.phase, 'none')

    s1.receive(state({ state_version: 6, phase: 'picking' }))
    assert.equal(conn.getSnapshot().state?.state_version, 6)
  })

  it('sync 응답으로 받은 같은 버전은 적용한다', () => {
    const { env, conn } = setup()
    const s1 = env.last()
    handshake(env, s1, 'epoch-a', 5)
    env.visibility.set(false)
    env.visibility.set(true)
    assert.equal(s1.sentOf('sync').length, 1)
    s1.receive(state({ state_version: 5, phase: 'picking' }))
    assert.equal(conn.getSnapshot().state?.phase, 'picking')
  })

  it('server_epoch가 바뀌면 이전 상태를 버리고, 이전 epoch·이전 소켓의 메시지는 무시한다', () => {
    const { env, conn } = setup()
    const s1 = env.last()
    handshake(env, s1, 'epoch-a', 7)

    // 현재 epoch와 다른 state는 적용하지 않는다.
    s1.receive(state({ server_epoch: 'epoch-b', state_version: 99 }))
    assert.equal(conn.getSnapshot().state?.state_version, 7)

    s1.serverClose(1001)
    env.timers.fire(500)
    const s2 = env.last()
    assert.notEqual(s1, s2)
    s2.open()
    s2.receive(hello({ server_epoch: 'epoch-b' }))
    assert.equal(conn.getSnapshot().state, null)

    // 서버가 재시작했으므로 더 낮은 버전도 새 상태로 적용한다.
    s2.receive(state({ server_epoch: 'epoch-b', state_version: 0 }))
    assert.equal(conn.getSnapshot().state?.server_epoch, 'epoch-b')

    // 이전 epoch 메시지와 닫힌 소켓의 메시지는 무시한다.
    s2.receive(state({ server_epoch: 'epoch-a', state_version: 100 }))
    s1.receive(state({ server_epoch: 'epoch-b', state_version: 100 }))
    assert.equal(conn.getSnapshot().state?.state_version, 0)
  })

  it('같은 epoch로 재접속하면 상태를 유지하고 직후 state를 적용한다', () => {
    const { env, conn } = setup()
    const s1 = env.last()
    handshake(env, s1, 'epoch-a', 3)
    s1.serverClose(1006)
    assert.equal(conn.getSnapshot().status, 'disconnected')
    assert.equal(conn.getSnapshot().state?.state_version, 3)
    env.timers.fire(500)
    handshake(env, env.last(), 'epoch-a', 3)
    assert.equal(conn.getSnapshot().status, 'connected')
    assert.equal(conn.getSnapshot().state?.state_version, 3)
  })

  it('형식이 틀린 메시지는 무시한다', () => {
    const { env, conn } = setup()
    const s1 = env.last()
    handshake(env, s1, 'epoch-a', 1)
    s1.receiveRaw('{broken')
    s1.receive({ ...state({ state_version: 2 }), deadline_ms: 'soon' })
    assert.equal(conn.getSnapshot().state?.state_version, 1)
  })
})

describe('Connection 연결 상태', () => {
  it('hello·state·ping 5회가 끝나야 연결됨이 되고, 최소 RTT로 기준점을 잡는다', () => {
    const { env, conn } = setup()
    const s1 = env.last()
    assert.equal(s1.url, 'ws://test/pick-api/ws?session=sess')
    assert.equal(conn.getSnapshot().status, 'connecting')
    s1.open()
    s1.receive(hello())
    s1.receive(state())
    assert.equal(conn.getSnapshot().status, 'connecting')
    // ping은 한 번에 하나씩 보낸다.
    assert.equal(s1.sentOf('ping').length, 1)
    answerPings(env, s1, [80, 30, 60, 50, 90])
    assert.equal(s1.sentOf('ping').length, 5)
    const snap = conn.getSnapshot()
    assert.equal(snap.status, 'connected')
    assert.equal(snap.anchor?.rttMs, 30)
    assert.deepEqual(snap.rtt, { count: 5, p50: 60, p95: 90, max: 90 })
    // 두 번째 ping은 80ms에 보내고 110ms에 받았다. s = 1_000_000 + 80 + 15
    assert.equal(snap.anchor?.perfMs, 110)
    assert.equal(snap.anchor?.serverMs, 1_000_000 + 80 + 15 + 15)
  })

  it('모르는 id의 pong은 샘플로 쓰지 않는다', () => {
    const { env, conn } = setup()
    const s1 = env.last()
    s1.open()
    s1.receive(hello())
    s1.receive({ t: 'pong', id: 'p-999', c: 0, s: 1 })
    assert.equal(conn.getSnapshot().rtt.count, 0)
    answerPings(env, s1, [10])
    assert.equal(conn.getSnapshot().rtt.count, 1)
  })

  it('전경에서 30초마다 다시 재고, 배경에서는 전경 복귀 때 sync와 ping을 보낸다', () => {
    const { env } = setup()
    const s1 = env.last()
    handshake(env, s1)
    assert.deepEqual(env.timers.delays(), [RESYNC_INTERVAL_MS])

    env.clock.now += RESYNC_INTERVAL_MS
    env.timers.fire(RESYNC_INTERVAL_MS)
    assert.equal(s1.sentOf('ping').length, 6)
    answerPings(env, s1, [20, 20, 20, 20, 20])

    env.visibility.set(false)
    env.clock.now += RESYNC_INTERVAL_MS
    env.timers.fire(RESYNC_INTERVAL_MS)
    assert.equal(s1.sentOf('ping').length, 10)
    assert.deepEqual(env.timers.delays(), [])

    env.visibility.set(true)
    assert.equal(s1.sentOf('sync').length, 1)
    assert.equal(s1.sentOf('ping').length, 11)
  })

  it('protocol_version이 다르면 업데이트 필요로 멈추고 재접속하지 않는다', () => {
    const { env, conn } = setup()
    const s1 = env.last()
    s1.open()
    s1.receive(hello({ protocol_version: 1 }))
    assert.equal(conn.getSnapshot().status, 'update_required')
    assert.notEqual(s1.closedWith, null)
    assert.deepEqual(env.timers.delays(), [])
    assert.equal(env.sockets.length, 1)
  })
})

describe('Connection 종료 코드와 재접속', () => {
  it('0.5 → 1 → 2 → 5 → 5초 간격으로 재접속하고, hello를 받으면 처음 간격으로 돌아간다', () => {
    const { env, conn } = setup()
    const waits: number[] = []
    for (let i = 0; i < 5; i += 1) {
      env.last().serverClose(1006)
      assert.equal(conn.getSnapshot().status, 'disconnected')
      const delays = env.timers.delays()
      assert.equal(delays.length, 1)
      waits.push(delays[0])
      env.timers.fire(delays[0])
      assert.equal(conn.getSnapshot().status, 'connecting')
    }
    assert.deepEqual(waits, [500, 1000, 2000, 5000, 5000])
    assert.equal(env.sockets.length, 6)

    handshake(env, env.last())
    env.last().serverClose(4408)
    assert.ok(env.timers.delays().includes(500))
  })

  it('4401이면 재인증 이벤트를 보내고 재접속하지 않으며, 새 세션으로 다시 시작할 수 있다', () => {
    const { env, conn } = setup()
    let reauthCount = 0
    conn.onReauth(() => {
      reauthCount += 1
    })
    handshake(env, env.last())
    env.last().serverClose(4401)
    assert.equal(reauthCount, 1)
    assert.equal(conn.getSnapshot().status, 'reauth_required')
    assert.deepEqual(env.timers.delays(), [])

    conn.start('sess-2')
    assert.equal(env.last().url, 'ws://test/pick-api/ws?session=sess-2')
    assert.equal(conn.getSnapshot().status, 'connecting')
  })

  it('4400이면 재접속을 멈추고 업데이트 필요로 표시한다', () => {
    const { env, conn } = setup()
    handshake(env, env.last())
    env.last().serverClose(4400)
    assert.equal(conn.getSnapshot().status, 'update_required')
    assert.deepEqual(env.timers.delays(), [])
    assert.equal(env.sockets.length, 1)
  })
})

describe('Connection 요청 ID', () => {
  it('start, pick, result, reverse 요청이 규격대로 만들어지고 reply를 같은 id의 요청에 대응시킨다', async () => {
    const { env, conn } = setup()
    const s1 = env.last()
    handshake(env, s1)

    // start
    const pStart = conn.start('g-1', 'guild-1')
    const reqStart = s1.sentOf('start')[0]
    assert.deepEqual(reqStart, { t: 'start', id: reqStart.id, game_id: 'g-1', guild_id: 'guild-1' })
    s1.receive({ t: 'reply', id: reqStart.id, ok: true, code: 'ok', message: null, state_version: 10 })
    const resStart = await pStart
    assert.equal(resStart.ok, true)

    // pick
    const pPick = conn.pick('g-1', 'turn-1', 'Ahri')
    const reqPick = s1.sentOf('pick')[0]
    assert.deepEqual(reqPick, { t: 'pick', id: reqPick.id, game_id: 'g-1', turn_id: 'turn-1', champion_id: 'Ahri' })
    s1.receive({ t: 'reply', id: reqPick.id, ok: true, code: 'ok', message: null, state_version: 11 })
    const resPick = await pPick
    assert.equal(resPick.ok, true)

    // result
    const pResult = conn.result('g-1', 'team1')
    const reqResult = s1.sentOf('result')[0]
    assert.deepEqual(reqResult, { t: 'result', id: reqResult.id, game_id: 'g-1', winner: 'team1' })
    s1.receive({ t: 'reply', id: reqResult.id, ok: true, code: 'ok', message: null, state_version: 12 })
    const resResult = await pResult
    assert.equal(resResult.ok, true)

    // reverse
    const pReverse = conn.reverse('g-1', 'team1')
    const reqReverse = s1.sentOf('reverse')[0]
    assert.deepEqual(reqReverse, { t: 'reverse', id: reqReverse.id, game_id: 'g-1', expected_winner: 'team1' })
    s1.receive({ t: 'reply', id: reqReverse.id, ok: true, code: 'ok', message: null, state_version: 13 })
    const resReverse = await pReverse
    assert.equal(resReverse.ok, true)
  })

  it('연결이 끊기면 대기 중인 요청을 거부한다', async () => {
    const { env, conn } = setup()
    handshake(env, env.last())
    const pending = conn.pick('g-1', 't-1', 'Ahri')
    env.last().serverClose(1006)
    await assert.rejects(pending)
    await assert.rejects(conn.pick('g-1', 't-1', 'Ahri'))
  })
})

describe('Connection 정리', () => {
  it('dispose 뒤에는 타이머·visibility 리스너·소켓이 남지 않는다', () => {
    const { env, conn } = setup()
    let notified = 0
    conn.subscribe(() => {
      notified += 1
    })
    const s1 = env.last()
    handshake(env, s1)
    assert.ok(env.timers.pending.size > 0)

    conn.dispose()
    assert.equal(env.timers.pending.size, 0)
    assert.equal(env.visibility.listeners.size, 0)
    assert.equal(s1.closedWith, 1000)
    assert.equal(s1.onmessage, null)

    const before = notified
    s1.serverClose(1006)
    conn.start('again')
    assert.equal(env.timers.pending.size, 0)
    assert.equal(env.sockets.length, 1)
    assert.equal(notified, before)
  })

  it('재접속 대기 중에 dispose해도 타이머가 남지 않는다', () => {
    const { env, conn } = setup()
    env.last().serverClose(1006)
    assert.equal(env.timers.pending.size, 1)
    conn.dispose()
    assert.equal(env.timers.pending.size, 0)
  })

  it('구독 해제한 리스너는 더 이상 호출되지 않는다', () => {
    const { env, conn } = setup()
    let calls = 0
    const off = conn.subscribe(() => {
      calls += 1
    })
    env.last().open()
    env.last().receive(hello())
    const afterHello = calls
    assert.ok(afterHello > 0)
    off()
    env.last().receive(state())
    assert.equal(calls, afterHello)
  })
})

describe('buildSocketUrl', () => {
  it('페이지 프로토콜에 맞춰 ws/wss를 고르고 세션을 인코딩한다', () => {
    assert.equal(
      buildSocketUrl('a+b/c', { protocol: 'https:', host: 'x.discordsays.com' }),
      'wss://x.discordsays.com/pick-api/ws?session=a%2Bb%2Fc',
    )
    assert.equal(buildSocketUrl('s', { protocol: 'http:', host: '127.0.0.1:5173' }), 'ws://127.0.0.1:5173/pick-api/ws?session=s')
  })
})
