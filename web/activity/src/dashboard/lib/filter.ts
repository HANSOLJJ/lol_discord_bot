// 기간, 같은 팀 플레이어, 챔피언 검색 및 정렬에 따라 경기 목록을 필터링하는 모듈
import type { FilterState, Game, RecordSummary, Session, SortOrder } from './types.ts'

/**
 * 챔피언 이름 및 검색어에서 모든 공백을 제거하고 소문자로 정규화합니다.
 */
export function normalizeChampionName(name: string): string {
  return (name || '').replace(/\s+/g, '').toLowerCase()
}

/**
 * 특정 챔피언이 검색어와 일치하는지(공백 제거 부분 일치) 검사합니다.
 * 검색어가 비어 있으면 false를 반환합니다.
 */
export function isChampionMatch(championName: string, query: string): boolean {
  const cleanQuery = normalizeChampionName(query)
  if (!cleanQuery) return false
  const cleanName = normalizeChampionName(championName)
  return cleanName.includes(cleanQuery)
}

/**
 * 게임의 참가자 6명 중 한 명이라도 챔피언 검색어와 일치하는지 검사합니다.
 * 검색어가 비어 있으면 true를 반환합니다.
 */
export function matchChampionSearch(game: Game, query: string): boolean {
  const cleanQuery = normalizeChampionName(query)
  if (!cleanQuery) return true

  return (
    game.team1.some((p) => isChampionMatch(p.champ, cleanQuery)) ||
    game.team2.some((p) => isChampionMatch(p.champ, cleanQuery))
  )
}

/**
 * 선택된 플레이어들이 같은 팀(team1 또는 team2)에 모두 속해 있는지 검사합니다.
 * - 0명 또는 1명: 조건 없음(모든 판 유지).
 * - 2명 이상: 선택된 모든 ID가 team1에 있거나, 또는 team2에 있어야 함.
 */
export function matchSameTeamPlayers(game: Game, selectedPlayerIds: string[]): boolean {
  if (selectedPlayerIds.length <= 1) {
    return true
  }

  const team1Set = new Set(game.team1.map((p) => p.id))
  const team2Set = new Set(game.team2.map((p) => p.id))

  const allInTeam1 = selectedPlayerIds.every((id) => team1Set.has(id))
  if (allInTeam1) return true

  const allInTeam2 = selectedPlayerIds.every((id) => team2Set.has(id))
  return allInTeam2
}

/**
 * 플레이어 줄이 강조되어야 하는지(선택 플레이어 또는 검색 일치 챔피언) 검사합니다.
 */
export function isRowHighlighted(
  slot: { id: string; champ: string },
  selectedPlayerIds: string[],
  championQuery: string,
): boolean {
  if (selectedPlayerIds.includes(slot.id)) {
    return true
  }
  if (isChampionMatch(slot.champ, championQuery)) {
    return true
  }
  return false
}

/**
 * 선택된 플레이어(들)가 속한 팀의 전적(판 수, 승, 패, 승률 및 포맷팅된 문자열)을 계산합니다.
 * 0명 선택 시 null을 반환합니다.
 */
export function calculateTeamRecord(
  games: Game[],
  selectedPlayerIds: string[],
): RecordSummary | null {
  if (selectedPlayerIds.length === 0) {
    return null
  }

  const focusId = selectedPlayerIds[0]
  let wins = 0
  let losses = 0

  for (const g of games) {
    const isTeam1 = g.team1.some((p) => p.id === focusId)
    const isTeam2 = g.team2.some((p) => p.id === focusId)
    if (!isTeam1 && !isTeam2) continue

    const won = (isTeam1 && g.winner === 'team1') || (isTeam2 && g.winner === 'team2')
    if (won) {
      wins++
    } else {
      losses++
    }
  }

  const total = wins + losses
  const winRate = total > 0 ? (wins / total) * 100 : null

  const prefix = selectedPlayerIds.length >= 2 ? '같은 팀 ' : ''
  const winRatePart = winRate !== null ? ` (승률 ${winRate.toFixed(1)}%)` : ''
  const formatted = `${prefix}${total}판 · ${wins}승 ${losses}패${winRatePart}`

  return {
    total,
    wins,
    losses,
    winRate,
    formatted,
  }
}

/**
 * 판 목록을 time 기준으로 최신순('desc') 또는 오래된 순('asc')으로 정렬합니다.
 */
export function sortGames(games: Game[], order: SortOrder = 'desc'): Game[] {
  return [...games].sort((a, b) => {
    const timeA = new Date(a.time).getTime()
    const timeB = new Date(b.time).getTime()
    return order === 'asc' ? timeA - timeB : timeB - timeA
  })
}

/**
 * 기간 조건에 따라 게임 목록을 필터링합니다.
 */
export function filterByPeriod(
  games: Game[],
  period: string,
  sessions: Session[],
): Game[] {
  if (!period || period === 'all') {
    return games
  }
  if (period.startsWith('season')) {
    const seasonNum = Number(period.slice(6))
    return games.filter((g) => g.season === seasonNum)
  }
  if (period.startsWith('s')) {
    const session = sessions.find((s) => s.id === period)
    return session ? session.games : games
  }
  return games
}

/**
 * 기간, 같은 팀 플레이어(최대 3명), 챔피언 검색, 정렬 조건을 모두 적용하여 필터링합니다.
 */
export function filterGames(
  games: Game[],
  filter: FilterState,
  sessions: Session[],
): Game[] {
  const periodFiltered = filterByPeriod(games, filter.period, sessions)

  const filtered = periodFiltered.filter((game) => {
    if (!matchSameTeamPlayers(game, filter.selectedPlayerIds)) {
      return false
    }
    if (!matchChampionSearch(game, filter.championQuery)) {
      return false
    }
    return true
  })

  return sortGames(filtered, filter.sortOrder ?? 'desc')
}
