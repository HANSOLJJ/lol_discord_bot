// 대시보드 5개 탭(개인, 시너지, 챔피언, 매치업)의 순수 통계 계산 및 정렬 모듈
import type { Game } from './types.ts'

export interface WinRateResult {
  rate: number
  formatted: string
  color: string
}

export interface EarningsResult {
  man: number
  formatted: string
  sign: 'positive' | 'negative' | 'neutral'
}

export interface PlayerChampStat {
  champ: string
  n: number
  w: number
  l: number
  winRate: number
}

export interface PlayerOverviewRow {
  id: string
  name: string
  n: number
  w: number
  l: number
  champN: number
  winRate: number
  earnings: EarningsResult
  top5: PlayerChampStat[]
  _n: number
}

export interface PlayerDrilldownHeader {
  who: string
  picks: number
  wins: number
  losses: number
  uniqueChampCount: number
}

export interface ChampRow {
  champ: string
  n: number
  w: number
  l: number
  winRate: number
  _n: number
}

export interface ComboRow {
  ids: string[]
  name: string
  n: number
  w: number
  l: number
  winRate: number
  _n: number
}

export interface MatchupRow {
  n: number
  _n: number
  a: string[]
  b: string[]
  aName: string
  bName: string
  aw: number
  al: number
  bw: number
  bl: number
  aWinRate: number
  bWinRate: number
}

export type SortDir = 'asc' | 'desc'

export interface SortState {
  col: number
  dir: SortDir
}

export interface ColumnDef<T> {
  label: string
  num: boolean
  mob: boolean
  sortable?: boolean
  val: (row: T) => number | string
}

/**
 * 승률(%)을 계산합니다. n이 0이면 0을 반환합니다.
 */
export function calculateWinRate(w: number, n: number): number {
  return n > 0 ? (w / n) * 100 : 0
}

/**
 * 승률 기반 HSL 색상 코드를 반환합니다. (0% 빨강 ~ 100% 초록)
 */
export function getWinRateColor(rate: number): string {
  return `hsl(${Math.round(rate * 1.2)} 62% 45%)`
}

/**
 * 승률과 포맷팅 문자열, 색상 코드를 반환합니다.
 */
export function formatWinRate(w: number, n: number): WinRateResult {
  const rate = calculateWinRate(w, n)
  return {
    rate,
    formatted: `${rate.toFixed(0)}%`,
    color: getWinRateColor(rate),
  }
}

/**
 * 번 돈(만원 단위)을 계산하고 표기 문자열과 부호를 반환합니다.
 * 공식: (2 * w - n) * 0.5
 */
export function calculateEarnings(w: number, n: number): EarningsResult {
  const man = (2 * w - n) * 0.5
  const formattedNumber = Number.isInteger(man) ? String(man) : man.toFixed(1)
  const signPrefix = man > 0 ? '+' : ''
  const sign: 'positive' | 'negative' | 'neutral' =
    man > 0 ? 'positive' : man < 0 ? 'negative' : 'neutral'
  return {
    man,
    formatted: `${signPrefix}${formattedNumber}만`,
    sign,
  }
}

/**
 * 플레이어 ID 배열을 정렬합니다.
 * 선택된 플레이어가 우선하고, 나머지는 한글 이름순으로 정렬됩니다.
 */
export function orderPlayerIds(
  idList: string[],
  selectedIds: Set<string> | string[],
  players: Record<string, string>,
): string[] {
  const selSet = selectedIds instanceof Set ? selectedIds : new Set(selectedIds)
  return [...idList].sort((a, b) => {
    const sa = selSet.has(a)
    const sb = selSet.has(b)
    if (sa !== sb) return sa ? -1 : 1
    const nameA = players[a] || a
    const nameB = players[b] || b
    return nameA.localeCompare(nameB, 'ko')
  })
}

/**
 * 3:3 매치업 팀 이름 문자열을 생성합니다. (공백 없이 +로 연결)
 */
export function getTeamName(
  idList: string[],
  selectedIds: Set<string> | string[],
  players: Record<string, string>,
): string {
  return orderPlayerIds(idList, selectedIds, players)
    .map((id) => players[id] || id)
    .join('+')
}

/**
 * 배열에서 k개를 선택하는 모든 조합을 반환합니다.
 */
export function getCombinations<T>(arr: T[], k: number): T[][] {
  const res: T[][] = []
  const rec = (start: number, cur: T[]) => {
    if (cur.length === k) {
      res.push([...cur])
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

/**
 * 조합 키를 생성합니다. (ID 정렬 후 |로 연결)
 */
export function getCombinationKey(ids: string[]): string {
  return [...ids].sort().join('|')
}

/**
 * 조합(idList)이 선택된 플레이어들을 모두 포함하는지 검사합니다.
 */
export function matchesSelection(
  idList: string[],
  selectedIds: Set<string> | string[],
): boolean {
  const selSet = selectedIds instanceof Set ? selectedIds : new Set(selectedIds)
  for (const s of selSet) {
    if (!idList.includes(s)) return false
  }
  return true
}

/**
 * 옛 index.html의 table() 정렬 규칙에 따라 배열을 제자리 정렬(또는 정렬 복사)합니다.
 * 동률일 경우 _n(판수) 기준 보조 정렬(desc는 큰 판수 우선, asc는 작은 판수 우선)을 적용합니다.
 */
export function sortStatsRows<T extends { _n?: number }>(
  rows: T[],
  getVal: (row: T) => number | string,
  dir: SortDir,
): T[] {
  return [...rows].sort((a, b) => {
    const va = getVal(a)
    const vb = getVal(b)
    let c = typeof va === 'string' ? va.localeCompare(vb as string) : (va as number) - (vb as number)
    if (c === 0) {
      const na = a._n || 0
      const nb = b._n || 0
      c = na - nb
    }
    return dir === 'asc' ? c : -c
  })
}

/**
 * 챔피언별 픽 수 및 승수를 집계합니다.
 */
export function calculateChampStats(
  games: Game[],
  minGames: number = 1,
  predicate?: (slot: { id: string; champ: string }) => boolean,
): ChampRow[] {
  const map = new Map<string, { champ: string; n: number; w: number }>()

  for (const g of games) {
    const teams: [{ id: string; champ: string }[], boolean][] = [
      [g.team1, g.winner === 'team1'],
      [g.team2, g.winner === 'team2'],
    ]
    for (const [team, won] of teams) {
      for (const p of team) {
        if (predicate && !predicate(p)) continue
        let entry = map.get(p.champ)
        if (!entry) {
          entry = { champ: p.champ, n: 0, w: 0 }
          map.set(p.champ, entry)
        }
        entry.n++
        if (won) entry.w++
      }
    }
  }

  return [...map.values()]
    .filter((e) => e.n >= minGames)
    .map((e) => ({
      champ: e.champ,
      n: e.n,
      w: e.w,
      l: e.n - e.w,
      winRate: calculateWinRate(e.w, e.n),
      _n: e.n,
    }))
}

/**
 * 개인 탭 미선택 모드의 플레이어별 개요 목록(6명)을 집계합니다.
 */
export function calculatePlayerOverview(
  games: Game[],
  players: Record<string, string>,
): PlayerOverviewRow[] {
  const ids = Object.keys(players)

  return ids.map((id) => {
    let w = 0
    const champStats: Record<string, { n: number; w: number }> = {}

    for (const g of games) {
      const isTeam1 = g.team1.some((p) => p.id === id)
      const isTeam2 = g.team2.some((p) => p.id === id)
      const won = (isTeam1 && g.winner === 'team1') || (isTeam2 && g.winner === 'team2')
      if (won) w++

      const allPlayers = g.team1.concat(g.team2)
      for (const p of allPlayers) {
        if (p.id !== id) continue
        const e = champStats[p.champ] || (champStats[p.champ] = { n: 0, w: 0 })
        e.n++
        if (won) e.w++
      }
    }

    // 주력 TOP5: 승수 많은 순 -> 판수 많은 순 -> 승률 높은 순
    const top5: PlayerChampStat[] = Object.entries(champStats)
      .sort((a, b) => {
        return (
          b[1].w - a[1].w ||
          b[1].n - a[1].n ||
          calculateWinRate(b[1].w, b[1].n) - calculateWinRate(a[1].w, a[1].n)
        )
      })
      .slice(0, 5)
      .map(([champ, s]) => ({
        champ,
        n: s.n,
        w: s.w,
        l: s.n - s.w,
        winRate: calculateWinRate(s.w, s.n),
      }))

    const n = games.length
    const winRate = calculateWinRate(w, n)
    const earnings = calculateEarnings(w, n)

    return {
      id,
      name: players[id] || id,
      n,
      w,
      l: n - w,
      champN: Object.keys(champStats).length,
      winRate,
      earnings,
      top5,
      _n: n,
    }
  })
}

/**
 * 개인 탭 드릴다운(특정 플레이어 선택 시)의 상단 요약 헤더를 집계합니다.
 * minGames와 무관하게 해당 인원의 전체 경기 데이터를 집계합니다.
 */
export function calculatePlayerDrilldownHeader(
  games: Game[],
  playerId: string,
  players: Record<string, string>,
): PlayerDrilldownHeader {
  const who = players[playerId] || playerId
  const champSet = new Set<string>()
  let picks = 0
  let wins = 0

  for (const g of games) {
    const isTeam1 = g.team1.some((p) => p.id === playerId)
    const isTeam2 = g.team2.some((p) => p.id === playerId)
    const won = (isTeam1 && g.winner === 'team1') || (isTeam2 && g.winner === 'team2')

    const allPlayers = g.team1.concat(g.team2)
    for (const p of allPlayers) {
      if (p.id === playerId) {
        champSet.add(p.champ)
        picks++
        if (won) wins++
      }
    }
  }

  return {
    who,
    picks,
    wins,
    losses: picks - wins,
    uniqueChampCount: champSet.size,
  }
}

/**
 * 2인 / 3인 시너지 조합 통계를 집계합니다.
 * @param k 2 (페어) 또는 3 (트리오)
 */
export function calculateComboStats(
  games: Game[],
  players: Record<string, string>,
  k: number,
  selectedIds: Set<string> | string[] = new Set(),
  minGames: number = 1,
): ComboRow[] {
  const map = new Map<string, { ids: string[]; n: number; w: number }>()

  for (const g of games) {
    const teams: [string[], boolean][] = [
      [g.team1.map((p) => p.id), g.winner === 'team1'],
      [g.team2.map((p) => p.id), g.winner === 'team2'],
    ]
    for (const [team, won] of teams) {
      const comboList = getCombinations(team, k)
      for (const c of comboList) {
        const key = getCombinationKey(c)
        let entry = map.get(key)
        if (!entry) {
          entry = { ids: [...c].sort(), n: 0, w: 0 }
          map.set(key, entry)
        }
        entry.n++
        if (won) entry.w++
      }
    }
  }

  const selSet = selectedIds instanceof Set ? selectedIds : new Set(selectedIds)

  return [...map.values()]
    .filter((e) => e.n >= minGames && matchesSelection(e.ids, selSet))
    .map((e) => {
      const name = orderPlayerIds(e.ids, selSet, players)
        .map((id) => players[id] || id)
        .join(' + ')
      return {
        ids: e.ids,
        name,
        n: e.n,
        w: e.w,
        l: e.n - e.w,
        winRate: calculateWinRate(e.w, e.n),
        _n: e.n,
      }
    })
}

/**
 * 3:3 매치업 구도를 집계합니다.
 * 2번 이상 반복된 대진(Math.max(2, minGames))만 반환합니다.
 */
export function calculateMatchupStats(
  games: Game[],
  players: Record<string, string>,
  focusPlayerId: string | null = null,
  minGames: number = 1,
): MatchupRow[] {
  const map = new Map<
    string,
    { a: string[]; b: string[]; n: number; aw: number; bw: number }
  >()

  for (const g of games) {
    const t1 = g.team1.map((p) => p.id).sort()
    const t2 = g.team2.map((p) => p.id).sort()
    const k1 = t1.join('|')
    const k2 = t2.join('|')
    const aIsT1 = k1 < k2
    const [a, b, key] = aIsT1
      ? [t1, t2, `${k1} vs ${k2}`]
      : [t2, t1, `${k2} vs ${k1}`]
    const aWon = aIsT1 ? g.winner === 'team1' : g.winner === 'team2'

    let entry = map.get(key)
    if (!entry) {
      entry = { a, b, n: 0, aw: 0, bw: 0 }
      map.set(key, entry)
    }
    entry.n++
    if (aWon) entry.aw++
    else entry.bw++
  }

  const selSet = focusPlayerId ? new Set([focusPlayerId]) : new Set<string>()

  return [...map.values()]
    .filter((e) => e.n >= Math.max(2, minGames))
    .map((e) => {
      const flip = Boolean(focusPlayerId && e.b.includes(focusPlayerId))
      const a = flip ? e.b : e.a
      const b = flip ? e.a : e.b
      const aw = flip ? e.bw : e.aw
      const bw = flip ? e.aw : e.bw
      const aName = getTeamName(a, selSet, players)
      const bName = getTeamName(b, selSet, players)
      return {
        n: e.n,
        _n: e.n,
        a,
        b,
        aName,
        bName,
        aw,
        al: e.n - aw,
        bw,
        bl: e.n - bw,
        aWinRate: calculateWinRate(aw, e.n),
        bWinRate: calculateWinRate(bw, e.n),
      }
    })
}
