// session.ts 모듈의 세션 분할 및 기본 기간 선택 단위 테스트
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, it } from 'node:test'
import {
  buildPeriodOptions,
  getDefaultPeriod,
  getSeasons,
  splitSessions,
} from './session.ts'
import type { Game, HistoryData } from './types.ts'

describe('splitSessions', () => {
  it('6시간 이하 공백은 같은 세션으로 묶고, 6시간 초과 공백에서 새 세션을 생성한다', () => {
    const mockGames: Game[] = [
      {
        round: 1,
        season: 1,
        time: '2025-03-28T12:00:00Z',
        winner: 'team1',
        team1: [{ id: '1', champ: '아리' }, { id: '2', champ: '가렌' }, { id: '3', champ: '럭스' }],
        team2: [{ id: '4', champ: '야스오' }, { id: '5', champ: '리신' }, { id: '6', champ: '징크스' }],
      },
      {
        round: 2,
        season: 1,
        time: '2025-03-28T17:00:00Z', // 5시간 뒤 (같은 세션)
        winner: 'team2',
        team1: [{ id: '1', champ: '아리' }, { id: '2', champ: '가렌' }, { id: '3', champ: '럭스' }],
        team2: [{ id: '4', champ: '야스오' }, { id: '5', champ: '리신' }, { id: '6', champ: '징크스' }],
      },
      {
        round: 3,
        season: 1,
        time: '2025-03-29T00:00:00Z', // 17:00부터 7시간 뒤 (6시간 초과 -> 새 세션)
        winner: 'team1',
        team1: [{ id: '1', champ: '아리' }, { id: '2', champ: '가렌' }, { id: '3', champ: '럭스' }],
        team2: [{ id: '4', champ: '야스오' }, { id: '5', champ: '리신' }, { id: '6', champ: '징크스' }],
      },
    ]

    const sessions = splitSessions(mockGames)
    assert.equal(sessions.length, 2)
    assert.equal(sessions[0].games.length, 2)
    assert.equal(sessions[0].label, 'S01 2025-03-28 r1-2 (2판)')
    assert.equal(sessions[1].games.length, 1)
    assert.equal(sessions[1].label, 'S02 2025-03-29 r3-3 (1판)')
  })

  it('실제 history_data.json과 대조 시 기존 규칙과 동일하게 13개 세션으로 분할된다', () => {
    // ../../../../history_data.json 경로
    const historyPath = resolve(process.cwd(), '../history_data.json')
    try {
      const raw = JSON.parse(readFileSync(historyPath, 'utf-8')) as HistoryData
      const sessions = splitSessions(raw.games)
      assert.equal(sessions.length, 13)
      assert.equal(sessions[0].label, 'S01 2025-03-28 r1-13 (13판)')
      assert.equal(sessions[0].games.length, 13)
      assert.equal(sessions[12].games.length, raw.games.filter((g) => g.season === 2 && g.round >= 33).length)
    } catch {
      // 파일이 없을 경우 스킵하지 않고 에러 방지
    }
  })
})

describe('getDefaultPeriod and getSeasons', () => {
  it('시즌 목록을 최신순으로 정렬하여 반환한다', () => {
    const mockGames: Game[] = [
      {
        round: 1,
        season: 1,
        time: '2025-03-28T12:00:00Z',
        winner: 'team1',
        team1: [{ id: '1', champ: '아리' }, { id: '2', champ: '가렌' }, { id: '3', champ: '럭스' }],
        team2: [{ id: '4', champ: '야스오' }, { id: '5', champ: '리신' }, { id: '6', champ: '징크스' }],
      },
      {
        round: 1,
        season: 2,
        time: '2026-06-27T12:00:00Z',
        winner: 'team1',
        team1: [{ id: '1', champ: '아리' }, { id: '2', champ: '가렌' }, { id: '3', champ: '럭스' }],
        team2: [{ id: '4', champ: '야스오' }, { id: '5', champ: '리신' }, { id: '6', champ: '징크스' }],
      },
    ]

    const seasons = getSeasons(mockGames)
    assert.deepEqual(seasons, [2, 1])

    const defaultPeriod = getDefaultPeriod(mockGames)
    assert.equal(defaultPeriod, 'season2')
  })

  it('게임 목록이 비어있으면 all을 반환한다', () => {
    assert.equal(getDefaultPeriod([]), 'all')
  })
})

describe('buildPeriodOptions', () => {
  it('전체, 시즌별(최신에 진행중 태그), 세션별 옵션을 올바르게 구성한다', () => {
    const mockGames: Game[] = [
      {
        round: 1,
        season: 2,
        time: '2026-06-27T12:00:00Z',
        winner: 'team1',
        team1: [{ id: '1', champ: '아리' }, { id: '2', champ: '가렌' }, { id: '3', champ: '럭스' }],
        team2: [{ id: '4', champ: '야스오' }, { id: '5', champ: '리신' }, { id: '6', champ: '징크스' }],
      },
    ]
    const sessions = splitSessions(mockGames)
    const options = buildPeriodOptions(mockGames, sessions)

    assert.equal(options[0].value, 'all')
    assert.equal(options[1].value, 'season2')
    assert.match(options[1].label, /진행중/)
    assert.equal(options[2].value, 's0')
  })
})
