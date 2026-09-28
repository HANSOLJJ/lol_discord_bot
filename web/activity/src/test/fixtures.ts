// 테스트에서 쓰는 규격 예시 메시지 생성기 (ACTIVITY_PROTOCOL.md protocol_version 2)
import type { HelloMessage, StateMessage } from '../lib/protocol.ts'

export const USER = { id: '365414320332472332', username: 'hansol', global_name: '정한솔', avatar: 'a1b2c3' }

export const SAMPLE_PLAYERS = [
  { id: '365414320332472332', name: '정한솔', team: 'team1' as const, wins: 12 },
  { id: '111111111111111111', name: '사무엘', team: 'team1' as const, wins: 9 },
  { id: '222222222222222222', name: '유성호', team: 'team1' as const, wins: 15 },
  { id: '333333333333333333', name: '청명사냥꾼', team: 'team2' as const, wins: 7 },
  { id: '444444444444444444', name: '보링', team: 'team2' as const, wins: 11 },
  { id: '555555555555555555', name: '윤재철', team: 'team2' as const, wins: 10 },
]

export const SAMPLE_PICK_ORDER = [
  '333333333333333333',
  '111111111111111111',
  '555555555555555555',
  '444444444444444444',
  '365414320332472332',
  '222222222222222222',
]

export const SAMPLE_CHAMPIONS = [
  { id: 'Ahri', name: '아리' },
  { id: 'MonkeyKing', name: '오공' },
  { id: 'TwistedFate', name: '트위스티드 페이트' },
  { id: 'Leona', name: '레오나' },
  { id: 'Zed', name: '제드' },
  { id: 'Annie', name: '애니' },
  { id: 'Garen', name: '가렌' },
  { id: 'Sona', name: '소나' },
]

export function hello(overrides: Record<string, unknown> = {}): HelloMessage {
  return {
    t: 'hello',
    protocol_version: 2,
    server_epoch: 'epoch-a',
    server_ms: 1790000000000,
    user: USER,
    ...overrides,
  } as HelloMessage
}

export function state(overrides: Record<string, unknown> = {}): StateMessage {
  return {
    t: 'state',
    protocol_version: 2,
    server_epoch: 'epoch-a',
    game_id: null,
    state_version: 0,
    phase: 'none',
    round: null,
    season: null,
    server_ms: 1790000000000,
    start_at_ms: null,
    deadline_ms: null,
    grace_ms: null,
    turn_id: null,
    current_index: null,
    ddragon_version: null,
    players: [],
    pick_order: [],
    champions: [],
    selections: {},
    auto_assigned: [],
    result: null,
    me: {
      id: USER.id,
      role: 'spectator',
      team: null,
      can_start: true,
      can_pick: false,
      can_report: false,
      can_reverse: false,
    },
    ...overrides,
  } as StateMessage
}

export function noneState(overrides: Record<string, unknown> = {}): StateMessage {
  return state(overrides)
}

export function startingState(overrides: Record<string, unknown> = {}): StateMessage {
  return state({
    game_id: 'g-1790000000000',
    state_version: 1,
    phase: 'starting',
    round: 87,
    season: 2,
    server_ms: 1790000000000,
    start_at_ms: 1790000015000,
    deadline_ms: null,
    grace_ms: null,
    turn_id: null,
    current_index: null,
    ddragon_version: '15.19.1',
    players: SAMPLE_PLAYERS,
    pick_order: SAMPLE_PICK_ORDER,
    champions: SAMPLE_CHAMPIONS,
    selections: {},
    auto_assigned: [],
    result: null,
    me: {
      id: SAMPLE_PLAYERS[0].id, // 정한솔
      role: 'player',
      team: 'team1',
      can_start: false,
      can_pick: false,
      can_report: false,
      can_reverse: false,
    },
    ...overrides,
  })
}

export function pickingMyTurnState(overrides: Record<string, unknown> = {}): StateMessage {
  // 정한솔 차례 (current_index = 4)
  return state({
    game_id: 'g-1790000000000',
    state_version: 43,
    phase: 'picking',
    round: 87,
    season: 2,
    server_ms: 1790000040000,
    start_at_ms: null,
    deadline_ms: 1790000054000,
    grace_ms: 2000,
    turn_id: 'g-1790000000000:4',
    current_index: 4,
    ddragon_version: '15.19.1',
    players: SAMPLE_PLAYERS,
    pick_order: SAMPLE_PICK_ORDER,
    champions: SAMPLE_CHAMPIONS,
    selections: {
      '333333333333333333': 'Zed',
      '111111111111111111': 'Sona',
      '555555555555555555': 'Ahri',
      '444444444444444444': 'Leona',
    },
    auto_assigned: ['111111111111111111'],
    result: null,
    me: {
      id: SAMPLE_PLAYERS[0].id, // 정한솔
      role: 'player',
      team: 'team1',
      can_start: false,
      can_pick: true,
      can_report: false,
      can_reverse: false,
    },
    ...overrides,
  })
}

export function pickingOtherTurnState(overrides: Record<string, unknown> = {}): StateMessage {
  // 청명사냥꾼 차례 (current_index = 0)
  return state({
    game_id: 'g-1790000000000',
    state_version: 10,
    phase: 'picking',
    round: 87,
    season: 2,
    server_ms: 1790000005000,
    start_at_ms: null,
    deadline_ms: 1790000020000,
    grace_ms: 2000,
    turn_id: 'g-1790000000000:0',
    current_index: 0,
    ddragon_version: '15.19.1',
    players: SAMPLE_PLAYERS,
    pick_order: SAMPLE_PICK_ORDER,
    champions: SAMPLE_CHAMPIONS,
    selections: {},
    auto_assigned: [],
    result: null,
    me: {
      id: SAMPLE_PLAYERS[0].id, // 정한솔 (대기 중)
      role: 'player',
      team: 'team1',
      can_start: false,
      can_pick: false,
      can_report: false,
      can_reverse: false,
    },
    ...overrides,
  })
}

export function pickingWarningState(overrides: Record<string, unknown> = {}): StateMessage {
  // 내 차례이며 남은 시간이 4초인 상태
  return pickingMyTurnState({
    server_ms: 1790000050000,
    deadline_ms: 1790000054000, // 4초 남음
    ...overrides,
  })
}

export function awaitingResultState(overrides: Record<string, unknown> = {}): StateMessage {
  return state({
    game_id: 'g-1790000000000',
    state_version: 50,
    phase: 'awaiting_result',
    round: 87,
    season: 2,
    server_ms: 1790000080000,
    start_at_ms: null,
    deadline_ms: null,
    grace_ms: null,
    turn_id: null,
    current_index: null,
    ddragon_version: '15.19.1',
    players: SAMPLE_PLAYERS,
    pick_order: SAMPLE_PICK_ORDER,
    champions: SAMPLE_CHAMPIONS,
    selections: {
      '333333333333333333': 'Zed',
      '111111111111111111': 'Sona',
      '555555555555555555': 'Ahri',
      '444444444444444444': 'Leona',
      '365414320332472332': 'MonkeyKing',
      '222222222222222222': 'Annie',
    },
    auto_assigned: ['111111111111111111'],
    result: null,
    me: {
      id: SAMPLE_PLAYERS[0].id,
      role: 'player',
      team: 'team1',
      can_start: true,
      can_pick: false,
      can_report: true,
      can_reverse: false,
    },
    ...overrides,
  })
}

export function completedState(overrides: Record<string, unknown> = {}): StateMessage {
  return state({
    game_id: 'g-1790000000000',
    state_version: 60,
    phase: 'completed',
    round: 87,
    season: 2,
    server_ms: 1790000905000,
    start_at_ms: null,
    deadline_ms: null,
    grace_ms: null,
    turn_id: null,
    current_index: null,
    ddragon_version: '15.19.1',
    players: SAMPLE_PLAYERS,
    pick_order: SAMPLE_PICK_ORDER,
    champions: SAMPLE_CHAMPIONS,
    selections: {
      '333333333333333333': 'Zed',
      '111111111111111111': 'Sona',
      '555555555555555555': 'Ahri',
      '444444444444444444': 'Leona',
      '365414320332472332': 'MonkeyKing',
      '222222222222222222': 'Annie',
    },
    auto_assigned: ['111111111111111111'],
    result: {
      winner: 'team1',
      recorded_ms: 1790000900000,
      corrected: null,
    },
    me: {
      id: SAMPLE_PLAYERS[0].id,
      role: 'player',
      team: 'team1',
      can_start: true,
      can_pick: false,
      can_report: false,
      can_reverse: true,
    },
    ...overrides,
  })
}

export function completedReversedState(overrides: Record<string, unknown> = {}): StateMessage {
  return completedState({
    result: {
      winner: 'team2',
      recorded_ms: 1790000900000,
      corrected: {
        from: 'team1',
        at_ms: 1790000960000,
      },
    },
    ...overrides,
  })
}

export function samplePickingState(overrides: Record<string, unknown> = {}): StateMessage {
  return state({
    game_id: 'g-1790000000000',
    state_version: 41,
    phase: 'picking',
    round: 87,
    season: 2,
    server_ms: 1790000031000,
    start_at_ms: null,
    deadline_ms: 1790000045000,
    grace_ms: 2000,
    turn_id: 'g-1790000000000:2',
    current_index: 2,
    ddragon_version: '15.19.1',
    players: SAMPLE_PLAYERS,
    pick_order: SAMPLE_PICK_ORDER,
    champions: SAMPLE_CHAMPIONS,
    selections: {
      '333333333333333333': 'Zed',
      '111111111111111111': 'Sona',
    },
    auto_assigned: ['111111111111111111'],
    result: null,
    me: {
      id: '555555555555555555',
      role: 'player',
      team: 'team2',
      can_start: false,
      can_pick: true,
      can_report: false,
      can_reverse: false,
    },
    ...overrides,
  })
}
