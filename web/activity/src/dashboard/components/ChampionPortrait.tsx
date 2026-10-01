// 챔피언 원형 초상화 및 실패 시 첫 글자 폴백 렌더링 컴포넌트
import { useState } from 'react'
import { getChampionFallbackInitial } from '../lib/ddragon.ts'
import styles from './ChampionPortrait.module.css'

export interface ChampionPortraitProps {
  championName: string
  /** Data Dragon 초상화 주소. 없거나 불러오지 못하면 이름 첫 글자 원으로 대신한다. */
  imageUrl?: string
}

/** 대전 기록 카드에 쓰는 원형 챔피언 초상화. 마우스를 올리면 챔피언 이름이 뜬다. */
export function ChampionPortrait({ championName, imageUrl }: ChampionPortraitProps) {
  const [loadFailed, setLoadFailed] = useState(false)

  const initial = getChampionFallbackInitial(championName)

  if (!imageUrl || loadFailed) {
    return (
      <div className={styles.portraitWrapper} title={championName}>
        <div className={styles.fallbackCircle} aria-hidden="true">
          {initial}
        </div>
      </div>
    )
  }

  return (
    <div className={styles.portraitWrapper} title={championName}>
      <img
        src={imageUrl}
        alt={championName}
        className={styles.portraitImg}
        loading="lazy"
        onError={() => setLoadFailed(true)}
      />
    </div>
  )
}
