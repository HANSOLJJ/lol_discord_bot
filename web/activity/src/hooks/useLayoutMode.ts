// 화면 크기에 따라 반응형 레이아웃 모드(mobile, pc, pip)를 판정하는 훅
import { useEffect, useState } from 'react'

/** mobile은 위에서 아래로 쌓는 배치, pc는 두 열 배치, pip는 작은 창 요약 화면(PipView)이다. */
export type LayoutMode = 'mobile' | 'pc' | 'pip'

/** 창 크기로 모드를 정한다. 가로 480 이하이면서 세로 320 이하면 pip, 가로 720 이상이면 pc, 나머지는 mobile이다. */
function getMode(): LayoutMode {
  if (typeof window === 'undefined') return 'mobile'
  const w = window.innerWidth
  const h = window.innerHeight
  if (w <= 480 && h <= 320) return 'pip'
  if (w >= 720) return 'pc'
  return 'mobile'
}

/** 창 크기가 바뀔 때마다 모드를 다시 정한다. resize 이벤트가 몰려도 한 프레임에 한 번만 갱신한다. */
export function useLayoutMode(): LayoutMode {
  const [mode, setMode] = useState<LayoutMode>(getMode)

  useEffect(() => {
    let handle: number
    const onResize = () => {
      cancelAnimationFrame(handle)
      handle = requestAnimationFrame(() => {
        setMode(getMode())
      })
    }
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      cancelAnimationFrame(handle)
    }
  }, [])

  return mode
}
