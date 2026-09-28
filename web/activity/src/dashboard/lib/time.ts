// UTC 시각 문자열을 한국 표준시(KST) 및 지정 형식으로 변환하는 모듈

const KST_OFFSET_MS = 9 * 60 * 60 * 1000
const KOREAN_DAYS = ['일', '월', '화', '수', '목', '금', '토'] as const

/**
 * UTC 시각 입력을 '9월 27일 (일) 03:31' 형식의 한국 시간 문자열로 변환합니다.
 */
export function formatKoreanDateTime(utcInput: string | Date | number): string {
  const d = typeof utcInput === 'object' && utcInput instanceof Date
    ? utcInput
    : new Date(utcInput)
  if (Number.isNaN(d.getTime())) {
    return ''
  }
  const kst = new Date(d.getTime() + KST_OFFSET_MS)
  const month = kst.getUTCMonth() + 1
  const day = kst.getUTCDate()
  const dayOfWeek = KOREAN_DAYS[kst.getUTCDay()]
  const hours = String(kst.getUTCHours()).padStart(2, '0')
  const minutes = String(kst.getUTCMinutes()).padStart(2, '0')
  return `${month}월 ${day}일 (${dayOfWeek}) ${hours}:${minutes}`
}

/**
 * UTC 시각 입력을 '26년 9월 27일 (일)' 형식의 한국 날짜 문자열로 변환합니다.
 */
export function formatKoreanDate(utcInput: string | Date | number): string {
  const d = typeof utcInput === 'object' && utcInput instanceof Date
    ? utcInput
    : new Date(utcInput)
  if (Number.isNaN(d.getTime())) {
    return ''
  }
  const kst = new Date(d.getTime() + KST_OFFSET_MS)
  const year = String(kst.getUTCFullYear() % 100).padStart(2, '0')
  const month = kst.getUTCMonth() + 1
  const day = kst.getUTCDate()
  const dayOfWeek = KOREAN_DAYS[kst.getUTCDay()]
  return `${year}년 ${month}월 ${day}일 (${dayOfWeek})`
}

/**
 * UTC 시각 입력을 'HH:MM' 형식의 한국 시간 문자열로 변환합니다.
 */
export function formatTimeHHMM(utcInput: string | Date | number): string {
  const d = typeof utcInput === 'object' && utcInput instanceof Date
    ? utcInput
    : new Date(utcInput)
  if (Number.isNaN(d.getTime())) {
    return ''
  }
  const kst = new Date(d.getTime() + KST_OFFSET_MS)
  const hours = String(kst.getUTCHours()).padStart(2, '0')
  const minutes = String(kst.getUTCMinutes()).padStart(2, '0')
  return `${hours}:${minutes}`
}

/**
 * UTC 시각 입력을 'YYYY-MM-DD' 형식의 한국 시간 날짜 문자열로 변환합니다.
 */
export function getKstDateString(utcInput: string | Date | number): string {
  const d = typeof utcInput === 'object' && utcInput instanceof Date
    ? utcInput
    : new Date(utcInput)
  if (Number.isNaN(d.getTime())) {
    return ''
  }
  const kst = new Date(d.getTime() + KST_OFFSET_MS)
  const y = kst.getUTCFullYear()
  const m = String(kst.getUTCMonth() + 1).padStart(2, '0')
  const day = String(kst.getUTCDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}
