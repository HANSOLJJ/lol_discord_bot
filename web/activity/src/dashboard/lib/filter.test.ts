// filter.ts 모듈의 챔피언 검색, 같은 팀 필터, 승패 요약 및 정렬 단위 테스트
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  calculateTeamRecord,
  filterGames,
  isChampionMatch,
  isRowHighlighted,
  matchChampionSearch,
  matchSameTeamPlayers,
  normalizeChampionName,
  sortGames,
} from './filter.ts'
import type { Game, Session } from './types.ts'

const sampleGames: Game[] = [
  {
    round: 1,
    season: 1,
    time: '2025-03-28T12:00:00Z',
    winner: 'team1',
    team1: [
      { id: 'p1', champ: '갈리오' },
      { id: 'p2', champ: '리 신' },
      { id: 'p3', champ: '트위스티드 페이트' },
    ],
    team2: [
      { id: 'p4', champ: '야스오' },
      { id: 'p5', champ: '아리' },
      { id: 'p6', champ: '징크스' },
    ],
  },
  {
    round: 2,
    season: 2,
    time: '2026-06-27T12:00:00Z',
    winner: 'team2',
    team1: [
      { id: 'p1', champ: '베인' },
      { id: 'p3', champ: '스웨인' },
      { id: 'p5', champ: '아칼리' },
    ],
    team2: [
      { id: 'p2', champ: '갈리오' },
      { id: 'p4', champ: '제라스' },
      { id: 'p6', champ: '문도 박사' },
    ],
  },
  {
    round: 3,
    season: 2,
    time: '2026-06-28T12:00:00Z',
    winner: 'team1',
    team1: [
      { id: 'p4', champ: '아트록스' },
      { id: 'p5', champ: '리 신' },
      { id: 'p6', champ: '카이사' },
    ],
    team2: [
      { id: 'p1', champ: '가렌' },
      { id: 'p2', champ: '럭스' },
      { id: 'p3', champ: '오리아나' },
    ],
  },
]

describe('챔피언 검색 및 공백 무시 부분 일치', () => {
  it('공백을 무시하고 정규화한다', () => {
    assert.equal(normalizeChampionName('리 신'), '리신')
    assert.equal(normalizeChampionName(' 트위스티드 페이트 '), '트위스티드페이트')
    assert.equal(normalizeChampionName('Ahri'), 'ahri')
  })

  it('공백을 무시하고 부분 일치 여부를 판별한다', () => {
    // "리신"으로 "리 신" 일치
    assert.equal(isChampionMatch('리 신', '리신'), true)
    // "트위"로 "트위스티드 페이트" 일치
    assert.equal(isChampionMatch('트위스티드 페이트', '트위'), true)
    // "아"로 "아리", "아칼리" 부분 일치
    assert.equal(isChampionMatch('아리', '아'), true)
    assert.equal(isChampionMatch('아칼리', '아'), true)
    // 빈 검색어는 false
    assert.equal(isChampionMatch('아리', ''), false)
    assert.equal(isChampionMatch('아리', '   '), false)
  })

  it('판의 6명 중 한 명이라도 일치하면 판이 남는다', () => {
    // 1라운드에 "리 신"이 있으므로 "리신" 검색 시 true
    assert.equal(matchChampionSearch(sampleGames[0], '리신'), true)
    // 1라운드에 없는 챔피언 검색 시 false
    assert.equal(matchChampionSearch(sampleGames[0], '문도'), false)
    // 빈 검색어는 전체 일치(true)
    assert.equal(matchChampionSearch(sampleGames[0], ''), true)
  })
})

describe('같은 팀 필터 (matchSameTeamPlayers)', () => {
  it('0명 또는 1명 선택 시 모든 판을 유지한다', () => {
    assert.equal(matchSameTeamPlayers(sampleGames[0], []), true)
    assert.equal(matchSameTeamPlayers(sampleGames[0], ['p1']), true)
    assert.equal(matchSameTeamPlayers(sampleGames[1], ['p1']), true)
  })

  it('2명이 같은 팀인 판만 남기고, 다른 팀으로 갈린 판은 제외한다', () => {
    // 1라운드: p1과 p2는 둘 다 team1 -> 같은 팀 true
    assert.equal(matchSameTeamPlayers(sampleGames[0], ['p1', 'p2']), true)
    // 2라운드: p1은 team1, p2는 team2 -> 다른 팀 false
    assert.equal(matchSameTeamPlayers(sampleGames[1], ['p1', 'p2']), false)
  })

  it('3명이 모두 team1에 있거나 모두 team2에 있는 판만 남긴다', () => {
    // 1라운드: p1, p2, p3 모두 team1 -> true
    assert.equal(matchSameTeamPlayers(sampleGames[0], ['p1', 'p2', 'p3']), true)
    // 3라운드: p1, p2, p3 모두 team2 -> true
    assert.equal(matchSameTeamPlayers(sampleGames[2], ['p1', 'p2', 'p3']), true)
    // 2라운드: p1, p3은 team1이고 p2는 team2 -> false
    assert.equal(matchSameTeamPlayers(sampleGames[1], ['p1', 'p2', 'p3']), false)
  })
})

describe('승패 요약 계산 (calculateTeamRecord)', () => {
  it('0명 선택 시 null을 반환한다', () => {
    assert.equal(calculateTeamRecord(sampleGames, []), null)
  })

  it('1명 선택 시 "같은 팀" 접두사 없이 승패와 승률을 계산한다', () => {
    // p1의 전적:
    // 1라운드: team1 (승)
    // 2라운드: team1 (패)
    // 3라운드: team2 (패)
    // 총 3판 1승 2패, 승률 33.3%
    const record = calculateTeamRecord(sampleGames, ['p1'])
    assert.notEqual(record, null)
    assert.equal(record?.total, 3)
    assert.equal(record?.wins, 1)
    assert.equal(record?.losses, 2)
    assert.equal(record?.formatted, '3판 · 1승 2패 (승률 33.3%)')
  })

  it('2명 이상 선택 시 "같은 팀" 접두사를 붙여 승패와 승률을 계산한다', () => {
    // p1, p2가 같은 팀인 판 필터링 (1라운드: team1 승, 3라운드: team2 패)
    const sameTeamGames = sampleGames.filter((g) => matchSameTeamPlayers(g, ['p1', 'p2']))
    const record = calculateTeamRecord(sameTeamGames, ['p1', 'p2'])
    assert.notEqual(record, null)
    assert.equal(record?.total, 2)
    assert.equal(record?.wins, 1)
    assert.equal(record?.losses, 1)
    assert.equal(record?.formatted, '같은 팀 2판 · 1승 1패 (승률 50.0%)')
  })

  it('0판일 때는 승률 괄호를 표시하지 않는다', () => {
    const record1 = calculateTeamRecord([], ['p1'])
    assert.equal(record1?.formatted, '0판 · 0승 0패')

    const record2 = calculateTeamRecord([], ['p1', 'p2'])
    assert.equal(record2?.formatted, '같은 팀 0판 · 0승 0패')
  })
})

describe('정렬 (sortGames)', () => {
  it('최신순(desc)과 오래된 순(asc)으로 올바르게 정렬한다', () => {
    const desc = sortGames(sampleGames, 'desc')
    assert.equal(desc[0].round, 3)
    assert.equal(desc[2].round, 1)

    const asc = sortGames(sampleGames, 'asc')
    assert.equal(asc[0].round, 1)
    assert.equal(asc[2].round, 3)
  })
})

describe('줄 강조 판별 (isRowHighlighted)', () => {
  it('선택된 플레이어 또는 검색된 챔피언과 일치할 때 true를 반환한다', () => {
    const slot = { id: 'p1', champ: '리 신' }

    // 플레이어 일치
    assert.equal(isRowHighlighted(slot, ['p1'], ''), true)
    // 챔피언 검색 일치 (공백 무시)
    assert.equal(isRowHighlighted(slot, [], '리신'), true)
    // 둘 다 불일치
    assert.equal(isRowHighlighted(slot, ['p2'], '야스오'), false)
  })
})

describe('filterGames 종합 파이프라인', () => {
  const sessions: Session[] = [
    {
      id: 's0',
      index: 1,
      label: 'S01',
      date: '2025-03-28',
      roundMin: 1,
      roundMax: 1,
      games: [sampleGames[0]],
    },
  ]

  it('기간, 같은 팀, 챔피언 검색, 정렬이 결합되어 동작한다', () => {
    const result = filterGames(
      sampleGames,
      {
        period: 'all',
        selectedPlayerIds: ['p1', 'p2'],
        championQuery: '갈리오',
        sortOrder: 'asc',
      },
      sessions,
    )
    // p1과 p2가 같은 팀이고(1, 3라운드), 갈리오가 등장한 판(1라운드 갈리오): 1라운드만 해당
    assert.equal(result.length, 1)
    assert.equal(result[0].round, 1)
  })
})
