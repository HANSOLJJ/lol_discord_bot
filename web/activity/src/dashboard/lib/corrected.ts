// 경기 번복 정보 포맷팅 및 요약 생성 모듈
import { formatKoreanDateTime } from './time.ts'
import type { CorrectedInfo, FormattedCorrected } from './types.ts'

/**
 * 번복 정보(corrected)를 화면 표시에 맞게 정돈된 객체로 포맷팅합니다.
 */
export function formatCorrectedInfo(corrected: CorrectedInfo): FormattedCorrected {
  const previousWinnerLabel = corrected.from === 'team1' ? 'TEAM 1' : 'TEAM 2'
  const formattedAt = formatKoreanDateTime(corrected.at) || corrected.at
  const summary = `이전 승자: ${previousWinnerLabel}, ${formattedAt} 정정`

  return {
    previousWinnerLabel,
    formattedAt,
    summary,
  }
}
