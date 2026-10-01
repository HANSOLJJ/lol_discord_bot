// 전적 대시보드와 대전 기록 화면에서 사용하는 데이터 타입 정의

/** 한 판에서 한 사람의 자리. id는 디스코드 사용자 ID, champ는 한국어 챔피언 이름이다. */
export interface PlayerSlot {
  id: string
  champ: string
}

/** 결과 번복 기록. from은 번복 직전의 승리 팀, at은 번복한 시각(UTC ISO 문자열)이다. */
export interface CorrectedInfo {
  from: 'team1' | 'team2'
  at: string
}

/** history_data.json의 판 하나. 봇의 game_recorder.py가 기록한다. */
export interface Game {
  /** 시즌 안의 라운드 번호(1부터). */
  round: number
  /** 시즌1 라운드를 다시 매기기 전의 원래 번호. 채널에서 복구한 판에만 있다. */
  round_orig?: number
  /** 시즌 번호. 옛 데이터에 없으면 validateHistoryData가 날짜로 채운다. */
  season: number
  /** 판 시각(UTC ISO 문자열). 화면에는 time.ts가 KST로 바꿔 보인다. */
  time: string
  winner: 'team1' | 'team2'
  team1: PlayerSlot[]
  team2: PlayerSlot[]
  corrected?: CorrectedInfo
  /** 기록 출처. 채널 복구본은 T1·T2·CMD, 봇이 직접 기록한 판은 BOT이다. */
  sources?: string[]
}

/**
 * history_data.json 전체. 대시보드 화면은 players와 games를 쓰고,
 * 나머지는 봇과 복구 도구(parse_all_history.py)가 남기는 메타데이터다.
 */
export interface HistoryData {
  generated_at?: string
  channels?: string[]
  total_games?: number
  /** 디스코드 사용자 ID → 표시 이름. */
  players: Record<string, string>
  current_season?: number
  games: Game[]
  sessions_summary?: unknown[]
}

/** 6시간 넘게 쉬지 않고 이어진 판 묶음. session.ts가 만들고, id는 기간 선택 값으로 쓴다. */
export interface Session {
  id: string
  index: number
  label: string
  date: string
  roundMin: number
  roundMax: number
  games: Game[]
}

/** 기간 드롭다운 항목. value는 'all', 'season<N>', 세션 ID 중 하나이고, group으로 시즌·세션 묶음을 나눈다. */
export interface PeriodOption {
  value: string
  label: string
  group?: 'season' | 'session'
}

/** 대전 기록 정렬. desc는 최신순, asc는 오래된 순이다. */
export type SortOrder = 'desc' | 'asc'

/** 고른 플레이어가 속한 팀의 승패 요약(calculateTeamRecord). 해당하는 판이 없으면 winRate가 null이다. */
export interface RecordSummary {
  total: number
  wins: number
  losses: number
  winRate: number | null
  formatted: string
}

/** 대전 기록 탭의 필터 조건. filterGames에 넘긴다. */
export interface FilterState {
  period: string
  selectedPlayerIds: string[]
  championQuery: string
  sortOrder?: SortOrder
}

/** 번복 정보를 화면 문구로 바꾼 결과(formatCorrectedInfo). */
export interface FormattedCorrected {
  previousWinnerLabel: string
  formattedAt: string
  summary: string
}

