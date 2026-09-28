// 옛 index.html 계산 로직과 신규 stats.ts 순수 함수의 전 기간·전 조건 결과 대조 테스트
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, it } from 'node:test'
import { splitSessions } from './session.ts'
import {
  calculateChampStats,
  calculateComboStats,
  calculateMatchupStats,
  calculatePlayerDrilldownHeader,
  calculatePlayerOverview,
  getCombinations,
  sortStatsRows,
} from './stats.ts'
import type { Game, HistoryData } from './types.ts'

// --- 옛 index.html 참조 구현 (DOM 코드 제외한 원본 계산 로직 그대로 보존) ---

function legacyWr(w: number, n: number): number {
  return n ? (w / n) * 100 : 0
}

function legacyOrderIds(
  idList: string[],
  sel: Set<string>,
  players: Record<string, string>,
): string[] {
  return [...idList].sort((a, b) => {
    const sa = sel.has(a)
    const sb = sel.has(b)
    if (sa !== sb) return sa ? -1 : 1
    const nameA = players[a] || a
    const nameB = players[b] || b
    return nameA.localeCompare(nameB, 'ko')
  })
}

function legacyTeamName(
  idList: string[],
  sel: Set<string>,
  players: Record<string, string>,
): string {
  return legacyOrderIds(idList, sel, players)
    .map((id) => players[id] || id)
    .join('+')
}

function legacyCombos<T>(arr: T[], k: number): T[][] {
  const res: T[][] = []
  const rec = (start: number, cur: T[]) => {
    if (cur.length === k) {
      res.push(cur.slice())
      return
    }
    for (let i = start; i < arr.length; i++) {
      cur.push(arr[i])
      rec(i + 1, cur)
      cur.pop()
    }
  }
  rec(0, [])
  return res
}

function legacyTrioKey(arr: string[]): string {
  return [...arr].sort().join('|')
}

function legacyChampData(
  games: Game[],
  min: number,
  pred?: (p: { id: string; champ: string }) => boolean,
) {
  const map = new Map<string, { champ: string; n: number; w: number; _n: number }>()
  games.forEach((g) => {
    ;[
      [g.team1, g.winner === 'team1'] as const,
      [g.team2, g.winner === 'team2'] as const,
    ].forEach(([team, won]) => {
      team.forEach((p) => {
        if (pred && !pred(p)) return
        let e = map.get(p.champ)
        if (!e) {
          e = { champ: p.champ, n: 0, w: 0, _n: 0 }
          map.set(p.champ, e)
        }
        e.n++
        if (won) e.w++
      })
    })
  })
  return [...map.values()]
    .filter((e) => e.n >= min)
    .map((e) => ({ ...e, _n: e.n }))
}

function legacyPlayerOverview(games: Game[], players: Record<string, string>) {
  const ids = Object.keys(players)
  return ids.map((id) => {
    let w = 0
    const cs: Record<string, { n: number; w: number }> = {}
    games.forEach((g) => {
      const winIds = g.winner === 'team1' ? g.team1.map((p) => p.id) : g.team2.map((p) => p.id)
      const winSet = new Set(winIds)
      const won = winSet.has(id)
      if (won) w++
      g.team1.concat(g.team2).forEach((p) => {
        if (p.id !== id) return
        const e = cs[p.champ] || (cs[p.champ] = { n: 0, w: 0 })
        e.n++
        if (won) e.w++
      })
    })
    const top5 = Object.entries(cs)
      .sort(
        (a, b) =>
          b[1].w - a[1].w ||
          b[1].n - a[1].n ||
          legacyWr(b[1].w, b[1].n) - legacyWr(a[1].w, a[1].n),
      )
      .slice(0, 5)
    return {
      id,
      name: players[id] || id,
      n: games.length,
      w,
      champN: Object.keys(cs).length,
      top5,
      _n: games.length,
    }
  })
}

function legacyPlayerDrilldownHeader(
  games: Game[],
  playerId: string,
  players: Record<string, string>,
) {
  const who = players[playerId] || playerId
  const champSet = new Set<string>()
  let picks = 0
  let wins = 0
  games.forEach((g) => {
    const winIds = g.winner === 'team1' ? g.team1.map((p) => p.id) : g.team2.map((p) => p.id)
    const winSet = new Set(winIds)
    g.team1.concat(g.team2).forEach((p) => {
      if (p.id === playerId) {
        champSet.add(p.champ)
        picks++
        if (winSet.has(p.id)) wins++
      }
    })
  })
  return { who, picks, wins, champCount: champSet.size }
}

function legacyCombo(
  games: Game[],
  players: Record<string, string>,
  k: number,
  sel: Set<string>,
  min: number,
) {
  const map = new Map<string, { ids: string[]; n: number; w: number }>()
  games.forEach((g) => {
    const t1 = g.team1.map((p) => p.id)
    const t2 = g.team2.map((p) => p.id)
    ;[
      [t1, g.winner === 'team1'] as const,
      [t2, g.winner === 'team2'] as const,
    ].forEach(([team, won]) => {
      legacyCombos(team, k).forEach((c) => {
        const key = legacyTrioKey(c)
        let e = map.get(key)
        if (!e) {
          e = { ids: [...c].sort(), n: 0, w: 0 }
          map.set(key, e)
        }
        e.n++
        if (won) e.w++
      })
    })
  })
  const selMatch = (idList: string[]) => {
    for (const s of sel) if (!idList.includes(s)) return false
    return true
  }
  return [...map.values()]
    .filter((e) => e.n >= min && selMatch(e.ids))
    .map((e) => ({
      ...e,
      name: legacyOrderIds(e.ids, sel, players)
        .map((id) => players[id] || id)
        .join(' + '),
      _n: e.n,
    }))
}

function legacyMatchup(
  games: Game[],
  players: Record<string, string>,
  focus: string | null,
  min: number,
) {
  const map = new Map<
    string,
    { a: string[]; b: string[]; n: number; aw: number; bw: number }
  >()
  games.forEach((g) => {
    const t1 = g.team1.map((p) => p.id).sort()
    const t2 = g.team2.map((p) => p.id).sort()
    const k1 = t1.join('|')
    const k2 = t2.join('|')
    const aIsT1 = k1 < k2
    const [a, b, key] = aIsT1
      ? [t1, t2, k1 + ' vs ' + k2]
      : [t2, t1, k2 + ' vs ' + k1]
    const aWon = aIsT1 ? g.winner === 'team1' : g.winner === 'team2'
    let e = map.get(key)
    if (!e) {
      e = { a, b, n: 0, aw: 0, bw: 0 }
      map.set(key, e)
    }
    e.n++
    if (aWon) e.aw++
    else e.bw++
  })

  const sel = focus ? new Set([focus]) : new Set<string>()
  return [...map.values()]
    .filter((e) => e.n >= Math.max(2, min))
    .map((e) => {
      const flip = Boolean(focus && e.b.includes(focus))
      const a = flip ? e.b : e.a
      const b = flip ? e.a : e.b
      const aw = flip ? e.bw : e.aw
      const bw = flip ? e.aw : e.bw
      return {
        n: e.n,
        _n: e.n,
        aw,
        bw,
        a,
        b,
        aName: legacyTeamName(a, sel, players),
        bName: legacyTeamName(b, sel, players),
      }
    })
}

function legacyTableSort<T extends { _n?: number }>(
  rows: T[],
  valFn: (row: T) => number | string,
  dir: 'asc' | 'desc',
): T[] {
  return [...rows].sort((a, b) => {
    const va = valFn(a)
    const vb = valFn(b)
    let c = typeof va === 'string' ? va.localeCompare(vb as string) : (va as number) - (vb as number)
    if (c === 0) {
      const na = a._n || 0
      const nb = b._n || 0
      c = na - nb
    }
    return dir === 'asc' ? c : -c
  })
}

// --- 대조 테스트 스위트 ---

function loadHistoryData(): HistoryData {
  const candidates = [
    resolve(process.cwd(), '../history_data.json'),
    resolve(process.cwd(), 'history_data.json'),
  ]
  for (const p of candidates) {
    if (existsSync(p)) {
      return JSON.parse(readFileSync(p, 'utf-8')) as HistoryData
    }
  }
  throw new Error('history_data.json을 찾을 수 없습니다.')
}

describe('옛 index.html과 신규 stats.ts 전수 대조 테스트', () => {
  const data = loadHistoryData()
  const players = data.players
  const playerIds = Object.keys(players)
  const allGames = data.games

  // 시즌 보정
  allGames.forEach((g) => {
    if (g.season == null) {
      g.season = g.time.slice(0, 10) >= '2026-06-26' ? 2 : 1
    }
  })

  const sessions = splitSessions(allGames)

  // 검증할 기간 묶음: 전체, 시즌1, 시즌2, 그리고 모든 세션(13개)
  const periodsToTest: { label: string; games: Game[] }[] = [
    { label: '전체', games: allGames },
    { label: '시즌 1', games: allGames.filter((g) => g.season === 1) },
    { label: '시즌 2', games: allGames.filter((g) => g.season === 2) },
    ...sessions.map((s) => ({ label: s.label, games: s.games })),
  ]

  for (const { label: periodLabel, games: periodGames } of periodsToTest) {
    describe(`기간: ${periodLabel} (${periodGames.length}판)`, () => {
      // 1. 개인 탭 개요 대조
      it('개인 탭 미선택 6명 전원 통계와 순위가 옛 대시보드와 완벽히 일치한다', () => {
        const legacyRows = legacyPlayerOverview(periodGames, players)
        const newRows = calculatePlayerOverview(periodGames, players)

        assert.equal(newRows.length, legacyRows.length)

        for (let i = 0; i < legacyRows.length; i++) {
          const l = legacyRows[i]
          const n = newRows[i]

          assert.equal(n.id, l.id)
          assert.equal(n.name, l.name)
          assert.equal(n.n, l.n)
          assert.equal(n.w, l.w)
          assert.equal(n.l, l.n - l.w)
          assert.equal(n.champN, l.champN)
          assert.equal(n.winRate, legacyWr(l.w, l.n))
          assert.equal(n.top5.length, l.top5.length)

          for (let t = 0; t < l.top5.length; t++) {
            assert.equal(n.top5[t].champ, l.top5[t][0])
            assert.equal(n.top5[t].n, l.top5[t][1].n)
            assert.equal(n.top5[t].w, l.top5[t][1].w)
            assert.equal(
              n.top5[t].winRate,
              legacyWr(l.top5[t][1].w, l.top5[t][1].n),
            )
          }

          // 번 돈 검증
          const expectedMan = (2 * l.w - l.n) * 0.5
          assert.equal(n.earnings.man, expectedMan)
        }

        // 기본 정렬: 승률 내림차순 대조
        const sortedLegacy = [...legacyRows].sort((a, b) => {
          const c = legacyWr(a.w, a.n) - legacyWr(b.w, b.n)
          if (c === 0) return (a._n || 0) - (b._n || 0)
          return -c
        })
        const sortedNew = sortStatsRows(newRows, (r) => r.winRate, 'desc')
        assert.deepEqual(
          sortedNew.map((r) => r.id),
          sortedLegacy.map((r) => r.id),
        )
      })

      // 2. 개인 탭 드릴다운 6명 전원 대조
      it('개인 탭 6명 각각의 챔피언별 전적 및 상단 요약 헤더가 완벽히 일치한다', () => {
        for (const playerId of playerIds) {
          const legacyHeader = legacyPlayerDrilldownHeader(
            periodGames,
            playerId,
            players,
          )
          const newHeader = calculatePlayerDrilldownHeader(
            periodGames,
            playerId,
            players,
          )

          assert.equal(newHeader.who, legacyHeader.who)
          assert.equal(newHeader.picks, legacyHeader.picks)
          assert.equal(newHeader.wins, legacyHeader.wins)
          assert.equal(newHeader.losses, legacyHeader.picks - legacyHeader.wins)
          assert.equal(newHeader.uniqueChampCount, legacyHeader.champCount)

          // 챔피언 목록 (minGames = 1 및 2)
          for (const min of [1, 2]) {
            const legacyChamps = legacyChampData(
              periodGames,
              min,
              (p) => p.id === playerId,
            )
            const newChamps = calculateChampStats(
              periodGames,
              min,
              (p) => p.id === playerId,
            )

            assert.equal(newChamps.length, legacyChamps.length)

            const sortedLegacy = legacyTableSort(legacyChamps, (r) => r.n, 'desc')
            const sortedNew = sortStatsRows(newChamps, (r) => r.n, 'desc')

            assert.deepEqual(
              sortedNew.map((r) => ({
                champ: r.champ,
                n: r.n,
                w: r.w,
                winRate: r.winRate,
              })),
              sortedLegacy.map((r) => ({
                champ: r.champ,
                n: r.n,
                w: r.w,
                winRate: legacyWr(r.w, r.n),
              })),
            )
          }
        }
      })

      // 3. 2인 시너지 대조 (0명 선택, 1명 선택 6종, 2명 선택 15종)
      it('2인 시너지 모든 조합 및 선택 필터링 결과가 완벽히 일치한다', () => {
        const testSelections: string[][] = [
          [], // 0명 선택
          ...playerIds.map((id) => [id]), // 1명 선택 (6명)
          ...getCombinations(playerIds, 2), // 2명 선택 (15조합)
        ]

        for (const sel of testSelections) {
          const selSet = new Set(sel)
          const legacyRows = legacyCombo(periodGames, players, 2, selSet, 1)
          const newRows = calculateComboStats(
            periodGames,
            players,
            2,
            selSet,
            1,
          )

          assert.equal(newRows.length, legacyRows.length)

          // 기본 정렬: 승률 내림차순 대조
          const sortedLegacy = legacyTableSort(
            legacyRows,
            (r) => legacyWr(r.w, r.n),
            'desc',
          )
          const sortedNew = sortStatsRows(newRows, (r) => r.winRate, 'desc')

          assert.deepEqual(
            sortedNew.map((r) => ({
              name: r.name,
              ids: r.ids,
              n: r.n,
              w: r.w,
              winRate: r.winRate,
            })),
            sortedLegacy.map((r) => ({
              name: r.name,
              ids: r.ids,
              n: r.n,
              w: r.w,
              winRate: legacyWr(r.w, r.n),
            })),
          )
        }
      })

      // 4. 3인 시너지 대조 (0명 선택, 1명 선택, 2명 선택, 3명 선택 20종)
      it('3인 시너지 모든 조합 및 선택 필터링 결과가 완벽히 일치한다', () => {
        const testSelections: string[][] = [
          [], // 0명 선택
          ...playerIds.map((id) => [id]), // 1명 선택
          ...getCombinations(playerIds, 2), // 2명 선택
          ...getCombinations(playerIds, 3), // 3명 선택 (20조합)
        ]

        for (const sel of testSelections) {
          const selSet = new Set(sel)
          const legacyRows = legacyCombo(periodGames, players, 3, selSet, 1)
          const newRows = calculateComboStats(
            periodGames,
            players,
            3,
            selSet,
            1,
          )

          assert.equal(newRows.length, legacyRows.length)

          // 기본 정렬: 승률 내림차순 대조
          const sortedLegacy = legacyTableSort(
            legacyRows,
            (r) => legacyWr(r.w, r.n),
            'desc',
          )
          const sortedNew = sortStatsRows(newRows, (r) => r.winRate, 'desc')

          assert.deepEqual(
            sortedNew.map((r) => ({
              name: r.name,
              ids: r.ids,
              n: r.n,
              w: r.w,
              winRate: r.winRate,
            })),
            sortedLegacy.map((r) => ({
              name: r.name,
              ids: r.ids,
              n: r.n,
              w: r.w,
              winRate: legacyWr(r.w, r.n),
            })),
          )
        }
      })

      // 5. 챔피언 탭 대조 (min = 1, 2, 3)
      it('챔피언 탭 전체 픽 수와 승률 및 정렬 결과가 완벽히 일치한다', () => {
        for (const min of [1, 2, 3]) {
          const legacyRows = legacyChampData(periodGames, min)
          const newRows = calculateChampStats(periodGames, min)

          assert.equal(newRows.length, legacyRows.length)

          // 기본 정렬: 픽 내림차순 대조
          const sortedLegacy = legacyTableSort(legacyRows, (r) => r.n, 'desc')
          const sortedNew = sortStatsRows(newRows, (r) => r.n, 'desc')

          assert.deepEqual(
            sortedNew.map((r) => ({
              champ: r.champ,
              n: r.n,
              w: r.w,
              winRate: r.winRate,
            })),
            sortedLegacy.map((r) => ({
              champ: r.champ,
              n: r.n,
              w: r.w,
              winRate: legacyWr(r.w, r.n),
            })),
          )
        }
      })

      // 6. 3:3 매치업 탭 대조 (포커스 없음 + 6명 각각 포커스)
      it('3:3 매치업 구도와 플립 로직, 정렬 결과가 완벽히 일치한다', () => {
        const focuses: (string | null)[] = [null, ...playerIds]

        for (const focus of focuses) {
          const legacyRows = legacyMatchup(periodGames, players, focus, 1)
          const newRows = calculateMatchupStats(periodGames, players, focus, 1)

          assert.equal(newRows.length, legacyRows.length)

          // 기본 정렬: focus 없으면 n 내림차순, focus 있으면 A팀 승률 내림차순
          const sortedLegacy = legacyTableSort(
            legacyRows,
            (r) => (focus ? legacyWr(r.aw, r.n) : r.n),
            'desc',
          )
          const sortedNew = sortStatsRows(
            newRows,
            (r) => (focus ? r.aWinRate : r.n),
            'desc',
          )

          assert.deepEqual(
            sortedNew.map((r) => ({
              n: r.n,
              aName: r.aName,
              bName: r.bName,
              aw: r.aw,
              bw: r.bw,
              aWinRate: r.aWinRate,
              bWinRate: r.bWinRate,
            })),
            sortedLegacy.map((r) => ({
              n: r.n,
              aName: r.aName,
              bName: r.bName,
              aw: r.aw,
              bw: r.bw,
              aWinRate: legacyWr(r.aw, r.n),
              bWinRate: legacyWr(r.bw, r.n),
            })),
          )
        }
      })
    })
  }
})
