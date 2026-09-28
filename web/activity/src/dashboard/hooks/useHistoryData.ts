// 전적 데이터 로드, 20초 주기 HEAD 변경 감지 폴링 및 자동 갱신 커스텀 훅
import { useCallback, useEffect, useRef, useState } from 'react'
import type { HistoryData } from '../lib/types.ts'
import { validateHistoryData } from '../lib/validation.ts'

export const POLL_INTERVAL_MS = 20_000

export interface UseHistoryDataResult {
  data: HistoryData | null
  loading: boolean
  error: string | null
  lastUpdated: Date | null
  refresh: () => Promise<void>
}

export function useHistoryData(dataUrl = '/history_data.json'): UseHistoryDataResult {
  const [data, setData] = useState<HistoryData | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const lastEtagRef = useRef<string | null>(null)
  const lastModifiedRef = useRef<string | null>(null)
  const lastBodyTextRef = useRef<string | null>(null)
  const isFetchingRef = useRef<boolean>(false)

  const fetchFullData = useCallback(async () => {
    if (isFetchingRef.current) return
    isFetchingRef.current = true
    try {
      const res = await fetch(`${dataUrl}?t=${Date.now()}`, {
        cache: 'no-cache',
      })
      if (!res.ok) {
        throw new Error(`데이터 요청 실패: ${res.status}`)
      }
      lastEtagRef.current = res.headers.get('etag')
      lastModifiedRef.current = res.headers.get('last-modified')

      const text = await res.text()
      lastBodyTextRef.current = text
      const parsed = JSON.parse(text)
      const validated = validateHistoryData(parsed)

      setData(validated)
      setError(null)
      setLastUpdated(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : '데이터를 불러오지 못했습니다.')
    } finally {
      setLoading(false)
      isFetchingRef.current = false
    }
  }, [dataUrl])

  const initialLoad = useCallback(() => {
    isFetchingRef.current = true
    fetch(`${dataUrl}?t=${Date.now()}`, { cache: 'no-cache' })
      .then(async (res) => {
        if (!res.ok) throw new Error(`데이터 요청 실패: ${res.status}`)
        lastEtagRef.current = res.headers.get('etag')
        lastModifiedRef.current = res.headers.get('last-modified')
        const text = await res.text()
        lastBodyTextRef.current = text
        const parsed = JSON.parse(text)
        const validated = validateHistoryData(parsed)
        setData(validated)
        setError(null)
        setLastUpdated(new Date())
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : '데이터를 불러오지 못했습니다.')
      })
      .finally(() => {
        setLoading(false)
        isFetchingRef.current = false
      })
  }, [dataUrl])

  const checkForUpdates = useCallback(async () => {
    if (isFetchingRef.current || document.visibilityState !== 'visible') {
      return
    }

    try {
      const headRes = await fetch(`${dataUrl}?t=${Date.now()}`, {
        method: 'HEAD',
        cache: 'no-cache',
      })

      if (!headRes.ok) {
        return
      }

      const etag = headRes.headers.get('etag')
      const modified = headRes.headers.get('last-modified')

      if (etag !== null && lastEtagRef.current !== null) {
        if (etag !== lastEtagRef.current) {
          await fetchFullData()
        }
        return
      }

      if (modified !== null && lastModifiedRef.current !== null) {
        if (modified !== lastModifiedRef.current) {
          await fetchFullData()
        }
        return
      }

      // ETag와 Last-Modified가 모두 없는 경우 GET 내용 비교
      const getRes = await fetch(`${dataUrl}?t=${Date.now()}`, {
        cache: 'no-cache',
      })
      if (getRes.ok) {
        const text = await getRes.text()
        if (text !== lastBodyTextRef.current) {
          lastBodyTextRef.current = text
          lastEtagRef.current = getRes.headers.get('etag')
          lastModifiedRef.current = getRes.headers.get('last-modified')
          const parsed = JSON.parse(text)
          const validated = validateHistoryData(parsed)
          setData(validated)
          setError(null)
          setLastUpdated(new Date())
        }
      }
    } catch {
      // 폴링 중 일시적 네트워크 오류는 무시하고 다음 주기에 재시도
    }
  }, [dataUrl, fetchFullData])

  // 최초 로드
  useEffect(() => {
    initialLoad()
  }, [initialLoad])

  // visibilitychange 및 20초 폴링
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchFullData()
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    const timer = setInterval(() => {
      checkForUpdates()
    }, POLL_INTERVAL_MS)

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      clearInterval(timer)
    }
  }, [checkForUpdates, fetchFullData])

  return {
    data,
    loading,
    error,
    lastUpdated,
    refresh: fetchFullData,
  }
}
