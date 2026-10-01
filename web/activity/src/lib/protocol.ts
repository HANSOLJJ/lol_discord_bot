// 액티비티 서버와 주고받는 메시지 타입과 수신 JSON 런타임 검증 (ACTIVITY_PROTOCOL.md protocol_version 4)

/** 서버와 맞춰야 하는 규격 버전. hello의 값이 다르면 connection.ts가 입력을 막고 업데이트 안내(update_required)로 바꾼다. */
export const PROTOCOL_VERSION = 4

/** 게임 단계. aborted는 예약값이라 서버가 보내지 않고, 화면은 none처럼 다룬다. */
export const PHASES = ['none', 'starting', 'advantage', 'picking', 'awaiting_result', 'completed', 'aborted'] as const
export type Phase = (typeof PHASES)[number]

/** player는 이번 판의 6명, spectator는 그 밖의 접속자다. */
export type Role = 'player' | 'spectator'
export type Team = 'team1' | 'team2'

/** ban은 양 팀 모두 못 고르게 막고, force는 상대 팀만 고를 수 있게 지정한다(ACTIVITY_PROTOCOL.md 14절). */
export type AdvantageKind = 'ban' | 'force'
/** pending은 고르는 중, chosen은 확정, skipped는 시간 초과로 이점 없음이다. */
export type AdvantageStatus = 'pending' | 'chosen' | 'skipped'

/** 5·6위 어드밴티지. 이점 판은 starting부터 결과까지 남고, champion_id는 chosen일 때만 채워진다. */
export interface AdvantageState {
  kind: AdvantageKind
  team: Team
  status: AdvantageStatus
  champion_id: string | null
}

/** 일시정지 상태. by는 멈춘 사람의 ID, remaining_ms는 멈출 때 남아 있던 시간이다. 정지 중에는 deadline_ms·start_at_ms가 null이다. */
export interface PausedState {
  by: string
  // starting 입장 대기 중(카운트다운 없음)에 정지하면 null이다.
  remaining_ms: number | null
}

/** 로그인한 디스코드 사용자. 화면은 global_name을 먼저, 없으면 username을 표시 이름으로 쓴다. */
export interface DiscordUser {
  id: string
  username: string
  global_name: string | null
  avatar: string | null
}

/** 이번 판 참가자. name은 서버 별명(없으면 사용자 이름), wins는 이번 시즌 누적 승수다(픽 순서의 근거라 보여 준다). */
export interface Player {
  id: string
  name: string
  team: Team
  wins: number
}

/** 후보 챔피언. id는 Data Dragon 영문 ID로 요청과 selections에 쓰고, name은 한국어 이름이다. */
export interface Champion {
  id: string
  name: string
}

/** 마지막 번복. from은 그 번복 직전의 승리 팀이다. */
export interface CorrectedResult {
  from: Team
  at_ms: number
}

/** 기록된 결과. completed에서만 온다. 번복된 적이 없으면 corrected는 null이다. */
export interface GameResult {
  winner: Team
  recorded_ms: number
  corrected: CorrectedResult | null
}

/**
 * 받는 사람마다 다른 권한(서버가 소켓마다 따로 만든다). 화면은 버튼 활성화를 이 값으로만 정한다.
 * 참이어도 그사이 상태가 바뀌면 서버가 거절할 수 있으므로 결과는 reply로 확인한다.
 */
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

/** 연결 직후 서버가 보내는 인사. server_epoch는 서버 프로세스마다 새로 만들며, 바뀌면 이전 상태를 모두 버린다. */
export interface HelloMessage {
  t: 'hello'
  protocol_version: number
  server_epoch: string
  server_ms: number
  user: DiscordUser
}

/** ping 응답. id·c는 보낸 값 그대로이고, s는 서버가 pong을 만든 순간의 시각(ms)이다. clock.ts가 시계 보정에 쓴다. */
export interface PongMessage {
  t: 'pong'
  id: string
  c: number
  s: number
}

/** 게임 상태 전체. 바뀔 때마다 통째로 온다. 지금 단계에 해당하지 않는 필드는 null 또는 빈 값이다(ACTIVITY_PROTOCOL.md 8절). */
export interface StateMessage {
  t: 'state'
  protocol_version: number
  server_epoch: string
  /** 판마다 서버가 만드는 ID. 같은지 비교만 하고, 요청에 실어 보내 지난 판에 대한 요청을 서버가 거르게 한다. */
  game_id: string | null
  /** 상태가 바뀔 때마다 1씩 오른다. 같은 server_epoch에서 이보다 작거나 같은 state는 적용하지 않는다. */
  state_version: number
  phase: Phase
  /** 이 판이 기록될 라운드와 시즌. 판을 시작할 때 정해진다. */
  round: number | null
  season: number | null
  /** 이 state를 만든 순간의 서버 시각. deadline_ms와 같은 순간을 기준으로 계산한다. */
  server_ms: number
  /** starting 카운트다운이 끝나는 시각. 입장 대기 중이거나 정지 중이면 null이다. */
  start_at_ms: number | null
  /** 지금 차례(advantage 단계면 이점 선택)의 마감. 차례 안에서 바뀌지 않고, 정지 중이면 null이다. */
  deadline_ms: number | null
  /** 마감 뒤 늦게 도착한 요청을 서버가 더 받아 주는 시간. 화면은 마감에 0을 보이고 그 뒤 "마감 확인 중"을 띄운다. */
  grace_ms: number | null
  /** 차례마다 바뀌는 ID. pick 요청에 실어 보내 지난 차례의 클릭을 서버가 거르게 한다. */
  turn_id: string | null
  /** pick_order에서 지금 고르는 사람의 위치(0~5). */
  current_index: number | null
  /** 초상화 주소(/ddragon/cdn/{버전}/img/champion/{챔피언 id}.png)에 쓰는 Data Dragon 버전. */
  ddragon_version: string | null
  /** 6명. TEAM 1 세 명 다음에 TEAM 2 세 명 순서다. */
  players: Player[]
  /** 픽 순서대로 담은 참가자 ID. 승수가 낮은 사람부터이고 같으면 무작위다. */
  pick_order: string[]
  /** 이번 판 후보 8개. */
  champions: Champion[]
  /** 참가자 ID → 고른 챔피언 ID. 자동 배정도 들어간다. */
  selections: Record<string, string>
  /** 시간 초과로 서버가 대신 고른 참가자 ID. */
  auto_assigned: string[]
  advantage: AdvantageState | null
  result: GameResult | null
  /** 지금 액티비티에 입장한(ready를 보낸) 참가자 ID. 관전자는 넣지 않는다. */
  present: string[]
  paused: PausedState | null
  me: Me
}

/** 요청에 대한 응답. code는 분기용 값이고, message는 화면 문구다(없으면 getReplyMessage가 기본 문구를 준다). */
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

/**
 * 클라이언트가 보내는 메시지. ready를 뺀 모든 메시지에 id가 있고, 그 id로 답과 짝짓는다.
 * ping에는 pong, sync에는 state, 나머지 요청에는 reply가 온다. ready는 첫 state를 그린 뒤 한 번 보내며 답이 없다.
 */
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

/** POST /pick-api/token 성공 응답. session으로 WebSocket에 접속하고, access_token은 SDK authenticate에 넘긴다. */
export interface TokenResponse {
  access_token: string
  session: string
  session_expires_ms: number
  user: DiscordUser
}

// 아래는 수신 JSON의 런타임 형식 검사용 판별 함수들이다. 시각·버전 같은 정수 필드는 isInt로 본다.
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

/** chosen이면 champion_id가 문자열이어야 하고, pending·skipped면 null이어야 한다. */
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

/** state의 모든 필드를 검사한다. protocol_version이 PROTOCOL_VERSION과 다른 state도 여기서 걸러진다. */
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

// t별 검사 함수. 여기에 없는 t는 parseServerMessage가 null로 돌려준다.
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
