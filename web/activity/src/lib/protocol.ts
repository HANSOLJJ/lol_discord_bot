// 액티비티 서버와 주고받는 메시지 타입과 수신 JSON 런타임 검증 (ACTIVITY_PROTOCOL.md protocol_version 4)

export const PROTOCOL_VERSION = 4

export const PHASES = ['none', 'starting', 'advantage', 'picking', 'awaiting_result', 'completed', 'aborted'] as const
export type Phase = (typeof PHASES)[number]

export type Role = 'player' | 'spectator'
export type Team = 'team1' | 'team2'

export type AdvantageKind = 'ban' | 'force'
export type AdvantageStatus = 'pending' | 'chosen' | 'skipped'

export interface AdvantageState {
  kind: AdvantageKind
  team: Team
  status: AdvantageStatus
  champion_id: string | null
}

export interface PausedState {
  by: string
  // starting 입장 대기 중(카운트다운 없음)에 정지하면 null이다.
  remaining_ms: number | null
}

export interface DiscordUser {
  id: string
  username: string
  global_name: string | null
  avatar: string | null
}

export interface Player {
  id: string
  name: string
  team: Team
  wins: number
}

export interface Champion {
  id: string
  name: string
}

export interface CorrectedResult {
  from: Team
  at_ms: number
}

export interface GameResult {
  winner: Team
  recorded_ms: number
  corrected: CorrectedResult | null
}

export interface Me {
  id: string
  role: Role
  team: Team | null
  can_start: boolean
  can_pick: boolean
  can_report: boolean
  can_reverse: boolean
  can_advantage: boolean
  can_start_now: boolean
  can_pause: boolean
  can_resume: boolean
}

export interface HelloMessage {
  t: 'hello'
  protocol_version: number
  server_epoch: string
  server_ms: number
  user: DiscordUser
}

export interface PongMessage {
  t: 'pong'
  id: string
  c: number
  s: number
}

export interface StateMessage {
  t: 'state'
  protocol_version: number
  server_epoch: string
  game_id: string | null
  state_version: number
  phase: Phase
  round: number | null
  season: number | null
  server_ms: number
  start_at_ms: number | null
  deadline_ms: number | null
  grace_ms: number | null
  turn_id: string | null
  current_index: number | null
  ddragon_version: string | null
  players: Player[]
  pick_order: string[]
  champions: Champion[]
  selections: Record<string, string>
  auto_assigned: string[]
  advantage: AdvantageState | null
  result: GameResult | null
  present: string[]
  paused: PausedState | null
  me: Me
}

export interface ReplyMessage {
  t: 'reply'
  // JSON 오류처럼 서버가 요청 ID를 읽지 못한 경우에는 null일 수 있다.
  id: string | null
  ok: boolean
  code: string
  message: string | null
  state_version: number | null
}

export type ServerMessage = HelloMessage | PongMessage | StateMessage | ReplyMessage

export type ClientMessage =
  | { t: 'ping'; id: string; c: number }
  | { t: 'sync'; id: string }
  | { t: 'ready' }
  | { t: 'start'; id: string; game_id: string | null; guild_id: string | null }
  | { t: 'advantage'; id: string; game_id: string; champion_id: string }
  | { t: 'pick'; id: string; game_id: string; turn_id: string; champion_id: string }
  | { t: 'result'; id: string; game_id: string; winner: Team }
  | { t: 'reverse'; id: string; game_id: string; expected_winner: Team }
  | { t: 'start_now'; id: string; game_id: string }
  | { t: 'pause'; id: string; game_id: string }
  | { t: 'resume'; id: string; game_id: string }

export interface TokenResponse {
  access_token: string
  session: string
  session_expires_ms: number
  user: DiscordUser
}

type Obj = Record<string, unknown>

const isObj = (v: unknown): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v)
const isStr = (v: unknown): v is string => typeof v === 'string'
const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const isInt = (v: unknown): v is number => Number.isInteger(v)
const isBool = (v: unknown): v is boolean => typeof v === 'boolean'
const isArr = (v: unknown): v is unknown[] => Array.isArray(v)
const orNull =
  <T>(check: (v: unknown) => v is T) =>
  (v: unknown): v is T | null =>
    v === null || check(v)

function isUser(v: unknown): v is DiscordUser {
  return (
    isObj(v) &&
    isStr(v.id) &&
    isStr(v.username) &&
    orNull(isStr)(v.global_name) &&
    orNull(isStr)(v.avatar)
  )
}

function isHello(m: Obj): boolean {
  return isInt(m.protocol_version) && isStr(m.server_epoch) && isInt(m.server_ms) && isUser(m.user)
}

function isPong(m: Obj): boolean {
  return isStr(m.id) && isNum(m.c) && isInt(m.s)
}

function isPlayer(v: unknown): v is Player {
  return (
    isObj(v) &&
    isStr(v.id) &&
    isStr(v.name) &&
    (v.team === 'team1' || v.team === 'team2') &&
    isInt(v.wins)
  )
}

function isChampion(v: unknown): v is Champion {
  return isObj(v) && isStr(v.id) && isStr(v.name)
}

function isGameResult(v: unknown): v is GameResult {
  if (!isObj(v)) return false
  if (v.winner !== 'team1' && v.winner !== 'team2') return false
  if (!isInt(v.recorded_ms)) return false
  if (v.corrected === null) return true
  return (
    isObj(v.corrected) &&
    (v.corrected.from === 'team1' || v.corrected.from === 'team2') &&
    isInt(v.corrected.at_ms)
  )
}

function isAdvantage(v: unknown): v is AdvantageState {
  if (!isObj(v)) return false
  if (v.kind !== 'ban' && v.kind !== 'force') return false
  if (v.team !== 'team1' && v.team !== 'team2') return false
  if (v.status === 'chosen') {
    return isStr(v.champion_id)
  }
  if (v.status === 'pending' || v.status === 'skipped') {
    return v.champion_id === null
  }
  return false
}

function isPaused(v: unknown): v is PausedState {
  return isObj(v) && isStr(v.by) && orNull(isInt)(v.remaining_ms)
}

function isMe(v: unknown): v is Me {
  return (
    isObj(v) &&
    isStr(v.id) &&
    (v.role === 'player' || v.role === 'spectator') &&
    (v.team === null || v.team === 'team1' || v.team === 'team2') &&
    isBool(v.can_start) &&
    isBool(v.can_pick) &&
    isBool(v.can_report) &&
    isBool(v.can_reverse) &&
    isBool(v.can_advantage) &&
    isBool(v.can_start_now) &&
    isBool(v.can_pause) &&
    isBool(v.can_resume)
  )
}

function isState(m: Obj): boolean {
  const me = m.me
  return (
    isInt(m.protocol_version) &&
    m.protocol_version === PROTOCOL_VERSION &&
    isStr(m.server_epoch) &&
    orNull(isStr)(m.game_id) &&
    isInt(m.state_version) &&
    (PHASES as readonly unknown[]).includes(m.phase) &&
    orNull(isInt)(m.round) &&
    orNull(isInt)(m.season) &&
    isInt(m.server_ms) &&
    orNull(isInt)(m.start_at_ms) &&
    orNull(isInt)(m.deadline_ms) &&
    orNull(isInt)(m.grace_ms) &&
    orNull(isStr)(m.turn_id) &&
    orNull(isInt)(m.current_index) &&
    orNull(isStr)(m.ddragon_version) &&
    isArr(m.players) &&
    m.players.every(isPlayer) &&
    isArr(m.pick_order) &&
    m.pick_order.every(isStr) &&
    isArr(m.champions) &&
    m.champions.every(isChampion) &&
    isObj(m.selections) &&
    Object.values(m.selections).every(isStr) &&
    isArr(m.auto_assigned) &&
    m.auto_assigned.every(isStr) &&
    orNull(isAdvantage)(m.advantage) &&
    orNull(isGameResult)(m.result) &&
    isArr(m.present) &&
    m.present.every(isStr) &&
    orNull(isPaused)(m.paused) &&
    isMe(me)
  )
}

function isReply(m: Obj): boolean {
  return (
    orNull(isStr)(m.id) &&
    isBool(m.ok) &&
    isStr(m.code) &&
    orNull(isStr)(m.message) &&
    orNull(isInt)(m.state_version)
  )
}

const validators: Record<ServerMessage['t'], (m: Obj) => boolean> = {
  hello: isHello,
  pong: isPong,
  state: isState,
  reply: isReply,
}

/** 서버 메시지 형식이 맞으면 그대로 돌려주고, 필수 필드 누락·타입 오류·모르는 t면 null을 돌려준다. 모르는 추가 필드는 허용한다. */
export function parseServerMessage(raw: unknown): ServerMessage | null {
  if (!isObj(raw) || !isStr(raw.t) || !Object.hasOwn(validators, raw.t)) return null
  return validators[raw.t as ServerMessage['t']](raw) ? (raw as unknown as ServerMessage) : null
}

/** WebSocket 텍스트 프레임을 해석한다. JSON 오류도 null이다. */
export function decodeServerMessage(text: unknown): ServerMessage | null {
  if (!isStr(text)) return null
  try {
    return parseServerMessage(JSON.parse(text))
  } catch {
    return null
  }
}

/** POST /pick-api/token 성공 응답을 검증한다. */
export function parseTokenResponse(raw: unknown): TokenResponse | null {
  if (
    isObj(raw) &&
    isStr(raw.access_token) &&
    isStr(raw.session) &&
    isInt(raw.session_expires_ms) &&
    isUser(raw.user)
  ) {
    return raw as unknown as TokenResponse
  }
  return null
}

/** Reply 메시지의 한국어 안내 문구를 돌려준다. 서버 message가 없으면 code별 기본 한국어 문구를 제공한다. */
export function getReplyMessage(reply: ReplyMessage): string {
  if (reply.message) return reply.message
  switch (reply.code) {
    case 'champion_banned':
      return '이번 판에서 밴된 챔피언입니다.'
    case 'champion_reserved':
      return '상대 팀만 고를 수 있는 강제픽 챔피언입니다.'
    case 'must_pick_forced':
      return '강제픽 챔피언을 골라야 합니다.'
    case 'stale_game':
      return '이미 끝났거나 바뀐 판입니다.'
    case 'wrong_phase':
      return '지금 단계에서 할 수 없는 요청입니다.'
    case 'not_your_turn':
      return '내 차례가 아닙니다.'
    case 'timeout':
      return '마감 시간이 지났습니다.'
    case 'not_candidate':
      return '이번 판 후보가 아닌 챔피언입니다.'
    case 'champion_taken':
      return '이미 뽑힌 챔피언입니다.'
    case 'not_allowed':
      return '권한이 없습니다.'
    case 'paused':
      return '일시정지 중에는 할 수 없습니다.'
    case 'already_paused':
      return '이미 일시정지되어 있습니다.'
    case 'not_paused':
      return '일시정지 상태가 아닙니다.'
    default:
      return '요청 처리에 실패했습니다.'
  }
}
