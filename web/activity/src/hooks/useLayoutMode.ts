// 화면 크기에 따라 반응형 레이아웃 모드(mobile, pc, pip)를 판정하는 훅
import { useEffect, useState } from 'react'

export type LayoutMode = 'mobile' | 'pc' | 'pip'

function getMode(): LayoutMode {
  if (typeof window === 'undefined') return 'mobile'
  const w = window.innerWidth
  const h = window.innerHeight
  if (w <= 480 && h <= 320) return 'pip'
  if (w >= 720) return 'pc'
  return 'mobile'
}

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
