// stats.ts 모듈의 순수 통계 함수 단위 테스트 (빈 데이터, 한 판, 동률 정렬)
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  calculateChampStats,
  calculateComboStats,
  calculateEarnings,
  calculateMatchupStats,
  calculatePlayerDrilldownHeader,
  calculatePlayerOverview,
  calculateWinRate,
  formatWinRate,
  getCombinations,
  getTeamName,
  orderPlayerIds,
  sortStatsRows,
} from './stats.ts'
import type { Game } from './types.ts'

describe('stats.ts 단위 테스트', () => {
  const mockPlayers: Record<string, string> = {
    p1: '플레이어1',
    p2: '플레이어2',
    p3: '플레이어3',
    p4: '플레이어4',
    p5: '플레이어5',
    p6: '플레이어6',
  }

  const sampleGame: Game = {
    round: 1,
    season: 1,
    time: '2026-06-26T21:00:00Z',
    winner: 'team1',
    team1: [
      { id: 'p1', champ: '아리' },
      { id: 'p2', champ: '가렌' },
      { id: 'p3', champ: '럭스' },
    ],
    team2: [
      { id: 'p4', champ: '야스오' },
      { id: 'p5', champ: '리신' },
      { id: 'p6', champ: '징크스' },
    ],
  }

  describe('calculateWinRate & formatWinRate', () => {
    it('0판일 때는 승률 0을 반환한다', () => {
      assert.equal(calculateWinRate(0, 0), 0)
      const formatted = formatWinRate(0, 0)
      assert.equal(formatted.rate, 0)
      assert.equal(formatted.formatted, '0%')
    })

    it('승수와 판수에 따라 승률과 HSL 색상을 계산한다', () => {
      const res = formatWinRate(1, 2)
      assert.equal(res.rate, 50)
      assert.equal(res.formatted, '50%')
      assert.equal(res.color, 'hsl(60 62% 45%)')
    })
  })

  describe('calculateEarnings', () => {
    it('양수 수익일 때는 +부호와 정수/소수점을 올바르게 포맷팅한다', () => {
      // 3승 1패: (2 * 3 - 4) * 0.5 = 1만
      const e1 = calculateEarnings(3, 4)
      assert.equal(e1.man, 1)
      assert.equal(e1.formatted, '+1만')
      assert.equal(e1.sign, 'positive')

      // 2승 1패: (4 - 3) * 0.5 = 0.5만
      const e2 = calculateEarnings(2, 3)
      assert.equal(e2.man, 0.5)
      assert.equal(e2.formatted, '+0.5만')
      assert.equal(e2.sign, 'positive')
    })

    it('음수 손실일 때는 -부호와 정수/소수점을 포맷팅한다', () => {
      // 1승 3패: (2 - 4) * 0.5 = -1만
      const e1 = calculateEarnings(1, 4)
      assert.equal(e1.man, -1)
      assert.equal(e1.formatted, '-1만')
      assert.equal(e1.sign, 'negative')

      // 0승 1패: (0 - 1) * 0.5 = -0.5만
      const e2 = calculateEarnings(0, 1)
      assert.equal(e2.man, -0.5)
      assert.equal(e2.formatted, '-0.5만')
      assert.equal(e2.sign, 'negative')
    })

    it('0원일 때는 부호 없이 0만을 반환하고 neutral 부호를 가진다', () => {
      // 1승 1패: (2 - 2) * 0.5 = 0만
      const e = calculateEarnings(1, 2)
      assert.equal(e.man, 0)
      assert.equal(e.formatted, '0만')
      assert.equal(e.sign, 'neutral')
    })
  })

  describe('orderPlayerIds & getTeamName', () => {
    it('선택된 플레이어를 맨 앞에 두고 나머지는 한글 이름순으로 정렬한다', () => {
      const ids = ['p1', 'p2', 'p3']
      const ordered = orderPlayerIds(ids, ['p3'], mockPlayers)
      assert.equal(ordered[0], 'p3')
      assert.equal(ordered[1], 'p1') // 플레이어1(p1)이 플레이어2(p2)보다 가나다순 앞
      assert.deepEqual(ordered, ['p3', 'p1', 'p2'])
    })

    it('getTeamName은 +로 연결된 문자열을 반환한다', () => {
      const name = getTeamName(['p1', 'p2'], ['p2'], mockPlayers)
      assert.equal(name, '플레이어2+플레이어1')
    })
  })

  describe('getCombinations', () => {
    it('3개 원소에서 2개 조합을 생성한다', () => {
      const combos = getCombinations(['a', 'b', 'c'], 2)
      assert.equal(combos.length, 3)
      assert.deepEqual(combos, [
        ['a', 'b'],
        ['a', 'c'],
        ['b', 'c'],
      ])
    })
  })

  describe('sortStatsRows 동률 보조 정렬', () => {
    it('1차 정렬 값이 같을 때 desc 정렬이면 판수(_n)가 큰 순서로 정렬한다', () => {
      const rows = [
        { id: 'a', rate: 50, _n: 5 },
        { id: 'b', rate: 50, _n: 20 },
        { id: 'c', rate: 70, _n: 2 },
      ]
      const sorted = sortStatsRows(rows, (r) => r.rate, 'desc')
      assert.equal(sorted[0].id, 'c')
      assert.equal(sorted[1].id, 'b') // _n=20
      assert.equal(sorted[2].id, 'a') // _n=5
    })

    it('1차 정렬 값이 같을 때 asc 정렬이면 판수(_n)가 작은 순서로 정렬한다', () => {
      const rows = [
        { id: 'a', rate: 50, _n: 5 },
        { id: 'b', rate: 50, _n: 20 },
        { id: 'c', rate: 30, _n: 2 },
      ]
      const sorted = sortStatsRows(rows, (r) => r.rate, 'asc')
      assert.equal(sorted[0].id, 'c')
      assert.equal(sorted[1].id, 'a') // _n=5
      assert.equal(sorted[2].id, 'b') // _n=20
    })
  })

  describe('빈 데이터 및 한 판 데이터 처리', () => {
    it('게임이 빈 배열일 때 안전하게 기본값들을 반환한다', () => {
      const overview = calculatePlayerOverview([], mockPlayers)
      assert.equal(overview.length, 6)
      for (const row of overview) {
        assert.equal(row.n, 0)
        assert.equal(row.w, 0)
        assert.equal(row.l, 0)
        assert.equal(row.winRate, 0)
        assert.equal(row.top5.length, 0)
      }

      const drilldownHeader = calculatePlayerDrilldownHeader([], 'p1', mockPlayers)
      assert.equal(drilldownHeader.picks, 0)
      assert.equal(drilldownHeader.wins, 0)
      assert.equal(drilldownHeader.uniqueChampCount, 0)

      const champs = calculateChampStats([])
      assert.equal(champs.length, 0)

      const pairs = calculateComboStats([], mockPlayers, 2)
      assert.equal(pairs.length, 0)

      const matchups = calculateMatchupStats([], mockPlayers)
      assert.equal(matchups.length, 0)
    })

    it('한 판 데이터가 주어졌을 때 정확하게 집계된다', () => {
      const games = [sampleGame]
      const overview = calculatePlayerOverview(games, mockPlayers)
      const p1 = overview.find((r) => r.id === 'p1')!
      assert.equal(p1.n, 1)
      assert.equal(p1.w, 1)
      assert.equal(p1.l, 0)
      assert.equal(p1.winRate, 100)
      assert.equal(p1.champN, 1)
      assert.equal(p1.top5[0].champ, '아리')

      const p4 = overview.find((r) => r.id === 'p4')!
      assert.equal(p4.n, 1)
      assert.equal(p4.w, 0)
      assert.equal(p4.l, 1)
      assert.equal(p4.winRate, 0)

      const champs = calculateChampStats(games, 1)
      assert.equal(champs.length, 6)

      // 1판만 있으므로 3:3 매치업은 2판 미만이라 반환되지 않아야 함
      const matchups = calculateMatchupStats(games, mockPlayers, null, 1)
      assert.equal(matchups.length, 0)
    })
  })
})
