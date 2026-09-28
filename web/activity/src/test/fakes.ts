// connection 테스트용 가짜 WebSocket·타이머·시계·visibility
import type { ConnectionOptions, SocketLike, Timers, VisibilitySource } from '../lib/connection.ts'

export class FakeSocket implements SocketLike {
  readonly url: string
  sent: Record<string, unknown>[] = []
  closedWith: number | null = null
  onopen: SocketLike['onopen'] = null
  onmessage: SocketLike['onmessage'] = null
  onclose: SocketLike['onclose'] = null
  onerror: SocketLike['onerror'] = null

  constructor(url: string) {
    this.url = url
  }

  send(data: string): void {
    this.sent.push(JSON.parse(data))
  }

  close(code?: number): void {
    this.closedWith = code ?? 1000
  }

  // 서버 쪽 동작. 연결 모듈이 읽는 필드만 채운다.
  open(): void {
    this.onopen?.({} as Event)
  }

  receive(msg: unknown): void {
    this.receiveRaw(JSON.stringify(msg))
  }

  receiveRaw(data: unknown): void {
    this.onmessage?.({ data } as MessageEvent)
  }

  serverClose(code: number): void {
    this.onclose?.({ code } as CloseEvent)
  }

  sentOf(t: string): Record<string, unknown>[] {
    return this.sent.filter((m) => m.t === t)
  }
}

export class FakeTimers implements Timers {
  #nextId = 1
  pending = new Map<number, { fn: () => void; ms: number }>()

  setTimeout(fn: () => void, ms: number): unknown {
    const id = this.#nextId++
    this.pending.set(id, { fn, ms })
    return id
  }

  clearTimeout(handle: unknown): void {
    this.pending.delete(handle as number)
  }

  /** 대기 시간이 ms인 타이머 하나를 실행한다. */
  fire(ms: number): void {
    for (const [id, timer] of this.pending) {
      if (timer.ms === ms) {
        this.pending.delete(id)
        timer.fn()
        return
      }
    }
    throw new Error(`${ms}ms 타이머가 없습니다. 대기 중: ${this.delays().join(', ')}`)
  }

  delays(): number[] {
    return [...this.pending.values()].map((t) => t.ms)
  }
}

export class FakeVisibility implements VisibilitySource {
  visible = true
  listeners = new Set<() => void>()

  isVisible(): boolean {
    return this.visible
  }

  subscribe(onChange: () => void): () => void {
    this.listeners.add(onChange)
    return () => this.listeners.delete(onChange)
  }

  set(visible: boolean): void {
    this.visible = visible
    for (const listener of this.listeners) listener()
  }
}

export function fakeEnv() {
  const sockets: FakeSocket[] = []
  const timers = new FakeTimers()
  const visibility = new FakeVisibility()
  const clock = { now: 0 }
  const options: ConnectionOptions = {
    createSocket: (url) => {
      const socket = new FakeSocket(url)
      sockets.push(socket)
      return socket
    },
    socketUrl: (session) => `ws://test/pick-api/ws?session=${session}`,
    now: () => clock.now,
    timers,
    visibility,
  }
  return { sockets, timers, visibility, clock, options, last: () => sockets[sockets.length - 1] }
}
