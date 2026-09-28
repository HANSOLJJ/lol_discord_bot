// 전적 원본 데이터의 구조와 무결성을 검증하는 모듈
import type { CorrectedInfo, Game, HistoryData, PlayerSlot } from './types.ts'

export function isValidPlayerSlot(slot: unknown): slot is PlayerSlot {
  if (typeof slot !== 'object' || slot === null) return false
  const s = slot as Record<string, unknown>
  return typeof s.id === 'string' && typeof s.champ === 'string'
}

export function isValidCorrected(corrected: unknown): corrected is CorrectedInfo {
  if (typeof corrected !== 'object' || corrected === null) return false
  const c = corrected as Record<string, unknown>
  return (c.from === 'team1' || c.from === 'team2') && typeof c.at === 'string'
}

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

export function validateHistoryData(data: unknown): HistoryData {
  if (!isValidHistoryData(data)) {
    throw new Error('유효하지 않은 전적 데이터 형식입니다.')
  }
  const games: Game[] = data.games.map((g) => {
    let season = g.season
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
