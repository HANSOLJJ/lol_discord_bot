// Data Dragon 챔피언 초상화 URL 매핑 및 폴백 모듈

export const DEFAULT_DDRAGON_BASE_URL = 'https://ddragon.leagueoflegends.com'

export type ChampionPortraitMap = Record<string, string>

/**
 * Data Dragon API를 호출하여 한글 챔피언명 -> 초상화 이미지 URL 매핑을 반환합니다.
 * @param baseUrl Data Dragon 베이스 주소 (기본값 https://ddragon.leagueoflegends.com)
 * @param customFetch 주입 가능한 fetch 함수 (테스트 및 목용)
 */
export async function fetchChampionPortraitMap(
  baseUrl: string = DEFAULT_DDRAGON_BASE_URL,
  customFetch: typeof fetch = fetch,
): Promise<ChampionPortraitMap> {
  const cleanBase = baseUrl.replace(/\/+$/, '')
  const versionsRes = await customFetch(`${cleanBase}/api/versions.json`)
  if (!versionsRes.ok) {
    throw new Error(`Data Dragon 버전 조회 실패: ${versionsRes.status}`)
  }
  const versions = (await versionsRes.json()) as string[]
  const latestVersion = versions[0]
  if (!latestVersion) {
    throw new Error('Data Dragon 버전 목록이 비어 있습니다.')
  }

  const champRes = await customFetch(
    `${cleanBase}/cdn/${latestVersion}/data/ko_KR/champion.json`,
  )
  if (!champRes.ok) {
    throw new Error(`Data Dragon 챔피언 데이터 조회 실패: ${champRes.status}`)
  }
  const json = (await champRes.json()) as {
    data: Record<string, { id: string; name: string }>
  }

  const map: ChampionPortraitMap = {}
  for (const c of Object.values(json.data)) {
    map[c.name] = `${cleanBase}/cdn/${latestVersion}/img/champion/${c.id}.png`
  }
  return map
}

/**
 * 초상화 로드 실패 시 표시할 챔피언 이름의 첫 글자를 반환합니다.
 */
export function getChampionFallbackInitial(name: string): string {
  const trimmed = (name || '').trim()
  return trimmed ? trimmed.charAt(0) : '?'
}
