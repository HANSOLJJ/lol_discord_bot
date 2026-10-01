// 전적 원본 데이터의 구조와 무결성을 검증하는 모듈
import type { CorrectedInfo, Game, HistoryData, PlayerSlot } from './types.ts'

/** 자리 하나가 id·champ 문자열을 갖는지 본다. */
export function isValidPlayerSlot(slot: unknown): slot is PlayerSlot {
  if (typeof slot !== 'object' || slot === null) return false
  const s = slot as Record<string, unknown>
  return typeof s.id === 'string' && typeof s.champ === 'string'
}

/** 번복 기록의 from이 팀 값이고 at이 문자열인지 본다. */
export function isValidCorrected(corrected: unknown): corrected is CorrectedInfo {
  if (typeof corrected !== 'object' || corrected === null) return false
  const c = corrected as Record<string, unknown>
  return (c.from === 'team1' || c.from === 'team2') && typeof c.at === 'string'
}

/**
 * 판 하나를 검사한다. 라운드 숫자, 해석할 수 있는 시각, 승리 팀, 팀당 정확히 3명, 번복 기록 형식을 본다.
 * season은 여기서 보지 않는다. 없는 옛 판은 validateHistoryData가 채운다.
 */
export function isValidGame(game: unknown): game is Game {
  if (typeof game !== 'object' || game === null) return false
  const g = game as Record<string, unknown>

  if (typeof g.round !== 'number' || Number.isNaN(g.round)) return false
  if (typeof g.time !== 'string' || Number.isNaN(new Date(g.time).getTime())) return false
  if (g.winner !== 'team1' && g.winner !== 'team2') return false
  if (!Array.isArray(g.team1) || !Array.isArray(g.team2)) return false
  if (g.team1.length !== 3 || g.team2.length !== 3) return false
  if (!g.team1.every(isValidPlayerSlot) || !g.team2.every(isValidPlayerSlot)) return false

  if (g.corrected !== undefined && !isValidCorrected(g.corrected)) {
    return false
  }

  return true
}

/** 전체 구조를 검사한다. players가 문자열 → 문자열 객체이고 games의 모든 판이 올바른지 본다. 한 판이라도 틀리면 전체를 거부한다. */
export function isValidHistoryData(data: unknown): data is HistoryData {
  if (typeof data !== 'object' || data === null) return false
  const d = data as Record<string, unknown>

  if (typeof d.players !== 'object' || d.players === null || Array.isArray(d.players)) {
    return false
  }
  for (const [key, value] of Object.entries(d.players)) {
    if (typeof key !== 'string' || typeof value !== 'string') {
      return false
    }
  }

  if (!Array.isArray(d.games)) {
    return false
  }

  return d.games.every(isValidGame)
}

/** 검사를 통과하면 season을 채운 데이터를 돌려주고, 통과하지 못하면 예외를 던진다(useHistoryData가 오류 화면으로 보인다). */
export function validateHistoryData(data: unknown): HistoryData {
  if (!isValidHistoryData(data)) {
    throw new Error('유효하지 않은 전적 데이터 형식입니다.')
  }
  const games: Game[] = data.games.map((g) => {
    let season = g.season
    // season이 없는 옛 판은 시즌2 시작일(2026-06-26)을 기준으로 1·2를 정한다.
    if (typeof season !== 'number') {
      const dateStr = g.time.slice(0, 10)
      season = dateStr >= '2026-06-26' ? 2 : 1
    }
    return {
      ...g,
      season,
    }
  })

  return {
    ...data,
    games,
  }
}
