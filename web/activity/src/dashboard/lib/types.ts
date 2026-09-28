// 전적 대시보드와 대전 기록 화면에서 사용하는 데이터 타입 정의
export interface PlayerSlot {
  id: string
  champ: string
}

export interface CorrectedInfo {
  from: 'team1' | 'team2'
  at: string
}

export interface Game {
  round: number
  round_orig?: number
  season: number
  time: string
  winner: 'team1' | 'team2'
  team1: PlayerSlot[]
  team2: PlayerSlot[]
  corrected?: CorrectedInfo
  sources?: string[]
}

export interface HistoryData {
  generated_at?: string
  channels?: string[]
  total_games?: number
  players: Record<string, string>
  current_season?: number
  games: Game[]
  sessions_summary?: unknown[]
}

export interface Session {
  id: string
  index: number
  label: string
  date: string
  roundMin: number
  roundMax: number
  games: Game[]
}

export interface PeriodOption {
  value: string
  label: string
  group?: 'season' | 'session'
}

export type SortOrder = 'desc' | 'asc'

export interface RecordSummary {
  total: number
  wins: number
  losses: number
  winRate: number | null
  formatted: string
}

export interface FilterState {
  period: string
  selectedPlayerIds: string[]
  championQuery: string
  sortOrder?: SortOrder
}

export interface FormattedCorrected {
  previousWinnerLabel: string
  formattedAt: string
  summary: string
}

