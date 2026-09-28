// 경기 기록을 6시간 공백 기준으로 세션으로 분할하고 라벨을 생성하는 모듈
import type { Game, PeriodOption, Session } from './types.ts'

export const SIX_HOURS_MS = 6 * 60 * 60 * 1000

/**
 * 6시간 초과 공백을 기준으로 경기 목록을 세션 목록으로 분할합니다.
 * 입력된 games는 시간순(오름차순)으로 처리됩니다.
 */
export function splitSessions(games: Game[]): Session[] {
  if (!games.length) {
    return []
  }

  const sorted = [...games].sort(
    (a, b) => new Date(a.time).getTime() - new Date(b.time).getTime(),
  )

  const rawSessions: Game[][] = []
  for (const g of sorted) {
    const lastSession = rawSessions[rawSessions.length - 1]
    if (
      !lastSession ||
      new Date(g.time).getTime() -
        new Date(lastSession[lastSession.length - 1].time).getTime() >
        SIX_HOURS_MS
    ) {
      rawSessions.push([g])
    } else {
      lastSession.push(g)
    }
  }

  return rawSessions.map((sessionGames, i) => {
    const index = i + 1
    const id = `s${i}`
    const date = sessionGames[0].time.slice(0, 10)
    const firstRound = sessionGames[0].round
    const lastRound = sessionGames[sessionGames.length - 1].round
    const label = `S${String(index).padStart(2, '0')} ${date} r${firstRound}-${lastRound} (${sessionGames.length}판)`
    return {
      id,
      index,
      label,
      date,
      roundMin: firstRound,
      roundMax: lastRound,
      games: sessionGames,
    }
  })
}

/**
 * 게임 목록에서 존재하는 시즌 번호 목록을 최신순(내림차순)으로 반환합니다.
 */
export function getSeasons(games: Game[]): number[] {
  const set = new Set<number>()
  for (const g of games) {
    if (typeof g.season === 'number') {
      set.add(g.season)
    }
  }
  return [...set].sort((a, b) => b - a)
}

/**
 * 기본 기간 선택값을 반환합니다. (최신 시즌 우선, 없으면 'all')
 */
export function getDefaultPeriod(games: Game[]): string {
  const seasons = getSeasons(games)
  if (seasons.length > 0) {
    return `season${seasons[0]}`
  }
  return 'all'
}

/**
 * 드롭다운에 표시할 기간 옵션 목록을 생성합니다.
 */
export function buildPeriodOptions(
  games: Game[],
  sessions: Session[],
): PeriodOption[] {
  const options: PeriodOption[] = [
    { value: 'all', label: `전체 (${games.length}판)` },
  ]

  const seasons = getSeasons(games)
  for (let i = 0; i < seasons.length; i++) {
    const season = seasons[i]
    const count = games.filter((g) => g.season === season).length
    const isCurrent = i === 0
    const label = isCurrent
      ? `시즌 ${season} · 진행중 (${count}판)`
      : `시즌 ${season} (${count}판)`
    options.push({
      value: `season${season}`,
      label,
      group: 'season',
    })
  }

  for (const s of sessions) {
    options.push({
      value: s.id,
      label: s.label,
      group: 'session',
    })
  }

  return options
}
