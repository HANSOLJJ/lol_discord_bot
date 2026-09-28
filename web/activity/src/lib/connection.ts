// 액티비티 서버 WebSocket 연결·재접속·요청 대응·상태 적용·시계 측정을 맡는 모듈 (React 비의존)
import {
  needsResync,
  pickAnchor,
  PING_SAMPLE_COUNT,
  RESYNC_INTERVAL_MS,
  rttStats,
  type ClockAnchor,
  type MonotonicClock,
  type PingSample,
  type RttStats,
} from './clock.ts'
import {
  decodeServerMessage,
  PROTOCOL_VERSION,
  type ClientMessage,
  type DiscordUser,
  type HelloMessage,
  type PongMessage,
  type ReplyMessage,
  type StateMessage,
  type Team,
} from './protocol.ts'

export const RECONNECT_DELAYS_MS = [500, 1000, 2000, 5000] as const

export const CLOSE_REAUTH = 4401
export const CLOSE_PROTOCOL_VIOLATION = 4400

export type ConnectionStatus =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'reauth_required'
  | 'update_required'

/** 브라우저 WebSocket 중 이 모듈이 쓰는 부분. 테스트에서 가짜를 주입한다. */
export interface SocketLike {
  send(data: string): void
  close(code?: number): void
  onopen: ((ev: Event) => void) | null
  onmessage: ((ev: MessageEvent) => void) | null
  onclose: ((ev: CloseEvent) => void) | null
  onerror: ((ev: Event) => void) | null
}

export interface Timers {
  setTimeout(fn: () => void, ms: number): unknown
  clearTimeout(handle: unknown): void
}

export interface VisibilitySource {
  isVisible(): boolean
  subscribe(onChange: () => void): () => void
}

export interface ConnectionOptions {
  createSocket: (url: string) => SocketLike
  socketUrl: (session: string) => string
  now: MonotonicClock
  timers: Timers
  visibility: VisibilitySource
}

export interface ConnectionSnapshot {
  status: ConnectionStatus
  user: DiscordUser | null
  state: StateMessage | null
  anchor: ClockAnchor | null
  rtt: RttStats
}

interface PendingRequest {
  resolve: (reply: ReplyMessage) => void
  reject: (err: Error) => void
}

/** 현재 페이지 주소 기준의 /pick-api/ws 주소. 세션이 query에 들어가므로 로그에 남기지 않는다. */
export function buildSocketUrl(session: string, loc: { protocol: string; host: string } = location): string {
  const scheme = loc.protocol === 'https:' ? 'wss' : 'ws'
  return `${scheme}://${loc.host}/pick-api/ws?session=${encodeURIComponent(session)}`
}

export const browserTimers: Timers = {
  setTimeout: (fn, ms) => globalThis.setTimeout(fn, ms),
  clearTimeout: (handle) => globalThis.clearTimeout(handle as ReturnType<typeof setTimeout>),
}

export const documentVisibility: VisibilitySource = {
  isVisible: () => document.visibilityState === 'visible',
  subscribe(onChange) {
    document.addEventListener('visibilitychange', onChange)
    return () => document.removeEventListener('visibilitychange', onChange)
  },
}

export function browserConnectionOptions(): ConnectionOptions {
  return {
    createSocket: (url) => new WebSocket(url),
    socketUrl: (session) => buildSocketUrl(session),
    now: () => performance.now(),
    timers: browserTimers,
    visibility: documentVisibility,
  }
}

export class Connection {
  readonly #opts: ConnectionOptions
  #disposed = false
  #session: string | null = null
  #socket: SocketLike | null = null
  #open = false
  #reconnectAttempt = 0
  #reconnectTimer: unknown = null
  #resyncTimer: unknown = null
  #stopVisibility: () => void

  // 서버 프로세스와 상태
  #epoch: string | null = null
  #allowSameVersion = false

  // 현재 연결에서 끝낸 준비 단계
  #gotHello = false
  #gotState = false
  #clockSynced = false

  // 요청 ID
  #seq = 0
  #pendingPings = new Map<string, number>()
  #pendingRequests = new Map<string, PendingRequest>()
  #batch: PingSample[] | null = null
  #lastBatchStartedAt: number | null = null
  #rtts: number[] = []

  #snapshot: ConnectionSnapshot = {
    status: 'idle',
    user: null,
    state: null,
    anchor: null,
    rtt: rttStats([]),
  }
  #listeners = new Set<(s: ConnectionSnapshot) => void>()
  #reauthListeners = new Set<() => void>()

  constructor(opts: ConnectionOptions) {
    this.#opts = opts
    this.#stopVisibility = opts.visibility.subscribe(() => this.#onVisibilityChange())
  }

  getSnapshot = (): ConnectionSnapshot => this.#snapshot

  subscribe = (listener: (s: ConnectionSnapshot) => void): (() => void) => {
    this.#listeners.add(listener)
    return () => this.#listeners.delete(listener)
  }

  /** 4401로 세션을 잃었을 때 호출된다. 새 세션으로 start()를 다시 부르면 된다. */
  onReauth(listener: () => void): () => void {
    this.#reauthListeners.add(listener)
    return () => this.#reauthListeners.delete(listener)
  }

  /** 세션으로 연결을 시작한다. 재인증 뒤에도 새 세션으로 다시 부른다. */
  start(session: string): void
  /** 게임 시작을 요청한다. */
  start(game_id: string | null, guild_id: string | null): Promise<ReplyMessage>
  start(arg1: string | null, arg2?: string | null): Promise<ReplyMessage> | void {
    if (arg2 === undefined && typeof arg1 === 'string' && !arg1.startsWith('g-')) {
      if (this.#disposed) return
      this.#session = arg1
      this.#reconnectAttempt = 0
      this.#connect()
      return
    }
    return this.requestStart(arg1, arg2 ?? null)
  }

  requestStart(game_id: string | null, guild_id: string | null): Promise<ReplyMessage> {
    if (!this.#open) return Promise.reject(new Error('연결되어 있지 않습니다.'))
    const id = this.#nextId('g')
    return new Promise((resolve, reject) => {
      this.#pendingRequests.set(id, { resolve, reject })
      this.#send({ t: 'start', id, game_id, guild_id })
    })
  }

  pick(game_id: string, turn_id: string, champion_id: string): Promise<ReplyMessage> {
    return this.requestPick(game_id, turn_id, champion_id)
  }

  requestPick(game_id: string, turn_id: string, champion_id: string): Promise<ReplyMessage> {
    if (!this.#open) return Promise.reject(new Error('연결되어 있지 않습니다.'))
    const id = this.#nextId('k')
    return new Promise((resolve, reject) => {
      this.#pendingRequests.set(id, { resolve, reject })
      this.#send({ t: 'pick', id, game_id, turn_id, champion_id })
    })
  }

  result(game_id: string, winner: Team): Promise<ReplyMessage> {
    return this.requestResult(game_id, winner)
  }

  requestResult(game_id: string, winner: Team): Promise<ReplyMessage> {
    if (!this.#open) return Promise.reject(new Error('연결되어 있지 않습니다.'))
    const id = this.#nextId('r')
    return new Promise((resolve, reject) => {
      this.#pendingRequests.set(id, { resolve, reject })
      this.#send({ t: 'result', id, game_id, winner })
    })
  }

  reverse(game_id: string, expected_winner: Team): Promise<ReplyMessage> {
    return this.requestReverse(game_id, expected_winner)
  }

  requestReverse(game_id: string, expected_winner: Team): Promise<ReplyMessage> {
    if (!this.#open) return Promise.reject(new Error('연결되어 있지 않습니다.'))
    const id = this.#nextId('v')
    return new Promise((resolve, reject) => {
      this.#pendingRequests.set(id, { resolve, reject })
      this.#send({ t: 'reverse', id, game_id, expected_winner })
    })
  }

  /** 소켓·타이머·리스너를 모두 정리한다. 이후에는 다시 쓸 수 없다. */
  dispose(): void {
    if (this.#disposed) return
    this.#disposed = true
    this.#stopVisibility()
    this.#clearTimer('reconnect')
    this.#dropSocket()
    this.#listeners.clear()
    this.#reauthListeners.clear()
  }

  #connect(): void {
    this.#clearTimer('reconnect')
    this.#dropSocket()
    if (this.#session === null) return
    this.#gotHello = false
    this.#gotState = false
    this.#clockSynced = false
    this.#update({ status: 'connecting' })

    const socket = this.#opts.createSocket(this.#opts.socketUrl(this.#session))
    this.#socket = socket
    // 이전 소켓에서 늦게 도착한 이벤트는 무시한다.
    socket.onopen = () => {
      if (socket === this.#socket) this.#open = true
    }
    socket.onmessage = (ev) => {
      if (socket === this.#socket) this.#onMessage(ev.data)
    }
    socket.onclose = (ev) => {
      if (socket === this.#socket) this.#onClose(ev.code)
    }
  }

  /** 현재 소켓을 떼어 내고 연결별 대기 상태를 정리한다. */
  #dropSocket(): void {
    const socket = this.#socket
    this.#socket = null
    this.#open = false
    this.#clearTimer('resync')
    this.#pendingPings.clear()
    this.#batch = null
    for (const pending of this.#pendingRequests.values()) pending.reject(new Error('연결이 끊겼습니다.'))
    this.#pendingRequests.clear()
    if (socket) {
      socket.onopen = socket.onmessage = socket.onclose = socket.onerror = null
      socket.close(1000)
    }
  }

  #onClose(code: number): void {
    this.#dropSocket()
    if (code === CLOSE_REAUTH) {
      this.#update({ status: 'reauth_required' })
      for (const listener of [...this.#reauthListeners]) listener()
      return
    }
    if (code === CLOSE_PROTOCOL_VIOLATION) {
      this.#update({ status: 'update_required' })
      return
    }
    this.#update({ status: 'disconnected' })
    const delays = RECONNECT_DELAYS_MS
    const delay = delays[Math.min(this.#reconnectAttempt, delays.length - 1)]
    this.#reconnectAttempt += 1
    this.#reconnectTimer = this.#opts.timers.setTimeout(() => {
      this.#reconnectTimer = null
      this.#connect()
    }, delay)
  }

  #onMessage(data: unknown): void {
    const msg = decodeServerMessage(data)
    if (msg === null) return
    switch (msg.t) {
      case 'hello':
        return this.#onHello(msg)
      case 'state':
        return this.#onState(msg)
      case 'pong':
        return this.#onPong(msg)
      case 'reply': {
        const pending = msg.id === null ? undefined : this.#pendingRequests.get(msg.id)
        if (pending && msg.id !== null) {
          this.#pendingRequests.delete(msg.id)
          pending.resolve(msg)
        }
      }
    }
  }

  #onHello(msg: HelloMessage): void {
    if (msg.protocol_version !== PROTOCOL_VERSION) return this.#stopForUpdate()
    this.#reconnectAttempt = 0
    this.#gotHello = true
    // 연결 직후 오는 state는 가진 것과 같은 버전이어도 적용한다.
    this.#allowSameVersion = true
    if (msg.server_epoch !== this.#epoch) {
      this.#epoch = msg.server_epoch
      this.#update({ user: msg.user, state: null })
    } else {
      this.#update({ user: msg.user })
    }
    this.#startPingBatch()
  }

  #onState(msg: StateMessage): void {
    if (!this.#gotHello || msg.server_epoch !== this.#epoch) return
    if (msg.protocol_version !== PROTOCOL_VERSION) return this.#stopForUpdate()
    const current = this.#snapshot.state
    const allowSame = this.#allowSameVersion
    this.#allowSameVersion = false
    this.#gotState = true
    if (current !== null) {
      const v = msg.state_version
      if (v < current.state_version || (v === current.state_version && !allowSame)) {
        return this.#refreshStatus()
      }
    }
    this.#update({ state: msg })
  }

  #onPong(msg: PongMessage): void {
    const p0 = this.#pendingPings.get(msg.id)
    if (p0 === undefined || this.#batch === null) return
    this.#pendingPings.delete(msg.id)
    const p1 = this.#opts.now()
    this.#batch.push({ p0, p1, s: msg.s })
    this.#rtts.push(p1 - p0)
    if (this.#batch.length < PING_SAMPLE_COUNT) {
      this.#sendPing()
      this.#update({ rtt: rttStats(this.#rtts) })
      return
    }
    const anchor = pickAnchor(this.#batch) ?? this.#snapshot.anchor
    this.#batch = null
    this.#clockSynced = true
    this.#update({ anchor, rtt: rttStats(this.#rtts) })
  }

  #startPingBatch(): void {
    if (!this.#open) return
    this.#pendingPings.clear()
    this.#batch = []
    this.#lastBatchStartedAt = this.#opts.now()
    this.#sendPing()
    this.#scheduleResync(RESYNC_INTERVAL_MS)
  }

  #sendPing(): void {
    const id = this.#nextId('p')
    const c = this.#opts.now()
    this.#pendingPings.set(id, c)
    this.#send({ t: 'ping', id, c })
  }

  #scheduleResync(ms: number): void {
    this.#clearTimer('resync')
    this.#resyncTimer = this.#opts.timers.setTimeout(() => {
      this.#resyncTimer = null
      this.#onResyncTick()
    }, ms)
  }

  /** 전경에서만 30초마다 다시 잰다. 배경이면 전경 복귀 때 잰다. */
  #onResyncTick(): void {
    if (!this.#open || !this.#opts.visibility.isVisible()) return
    const now = this.#opts.now()
    if (needsResync(this.#lastBatchStartedAt, now)) {
      this.#startPingBatch()
    } else {
      this.#scheduleResync(RESYNC_INTERVAL_MS - (now - (this.#lastBatchStartedAt ?? now)))
    }
  }

  #onVisibilityChange(): void {
    if (this.#disposed || !this.#open || !this.#gotHello || !this.#opts.visibility.isVisible()) return
    this.#allowSameVersion = true
    this.#send({ t: 'sync', id: this.#nextId('s') })
    this.#startPingBatch()
  }

  #stopForUpdate(): void {
    this.#update({ status: 'update_required' })
    this.#dropSocket()
  }

  #send(msg: ClientMessage): void {
    if (this.#open && this.#socket) this.#socket.send(JSON.stringify(msg))
  }

  #nextId(prefix: string): string {
    this.#seq += 1
    return `${prefix}-${this.#seq}`
  }

  #clearTimer(which: 'reconnect' | 'resync'): void {
    const handle = which === 'reconnect' ? this.#reconnectTimer : this.#resyncTimer
    if (handle !== null) this.#opts.timers.clearTimeout(handle)
    if (which === 'reconnect') this.#reconnectTimer = null
    else this.#resyncTimer = null
  }

  #refreshStatus(): void {
    this.#update({})
  }

  /** 스냅샷을 바꾸고 달라졌을 때만 알린다. 연결 중에 hello·state·시계 동기화가 모두 끝나면 연결됨으로 바꾼다. */
  #update(patch: Partial<ConnectionSnapshot>): void {
    const prev = this.#snapshot
    const next = { ...prev, ...patch }
    if (next.status === 'connecting' && this.#gotHello && this.#gotState && this.#clockSynced) {
      next.status = 'connected'
    }
    const keys = Object.keys(next) as (keyof ConnectionSnapshot)[]
    if (keys.every((k) => next[k] === prev[k])) return
    this.#snapshot = next
    for (const listener of [...this.#listeners]) listener(next)
  }
}
