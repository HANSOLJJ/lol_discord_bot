// Data Dragon으로부터 챔피언 초상화 URL 매핑을 가져오는 커스텀 훅
import { useEffect, useState } from 'react'
import {
  DEFAULT_DDRAGON_BASE_URL,
  fetchChampionPortraitMap,
  type ChampionPortraitMap,
} from '../lib/ddragon.ts'

export function useChampionPortraits(baseUrl = DEFAULT_DDRAGON_BASE_URL): ChampionPortraitMap {
  const [portraits, setPortraits] = useState<ChampionPortraitMap>({})

  useEffect(() => {
    let active = true
    fetchChampionPortraitMap(baseUrl)
      .then((map) => {
        if (active) {
          setPortraits(map)
        }
      })
      .catch(() => {
        // 로드 실패 시 빈 매핑 유지 (텍스트/원형 폴백 사용)
      })
    return () => {
      active = false
    }
  }, [baseUrl])

  return portraits
}
