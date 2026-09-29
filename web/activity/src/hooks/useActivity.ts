// Discord 인증과 액티비티 서버 연결을 한 번만 만들고 React 상태로 구독하는 훅
import { useCallback, useEffect, useRef, useState } from 'react'
import { browserConnectionOptions, Connection, type ConnectionSnapshot } from '../lib/connection.ts'
import { authenticate, getGuildId, LoginRequiredError } from '../lib/discord.ts'
import { getPreviewState } from '../lib/preview.ts'
import { getReplyMessage, type DiscordUser, type ReplyMessage, type StateMessage, type Team } from '../lib/protocol.ts'
import { getPresenceAlerts } from '../lib/view-logic.ts'
import { USER } from '../test/fixtures.ts'

export type AuthState =
  | { kind: 'pending' }
  | { kind: 'login_required'; message: string }
  | { kind: 'ok'; user: DiscordUser }

export interface Activity {
  auth: AuthState
  snapshot: ConnectionSnapshot | null
  state: StateMessage | null
  isPending: boolean
  toast: string | null
  login: () => void
  showToast: (msg: string) => void
  start: (game_id: string | null) => Promise<ReplyMessage>
  advantage: (game_id: string, champion_id: string) => Promise<ReplyMessage>
  pick: (game_id: string, turn_id: string, champion_id: string) => Promise<ReplyMessage>
  result: (game_id: string, winner: Team) => Promise<ReplyMessage>
  reverse: (game_id: string, expected_winner: Team) => Promise<ReplyMessage>
  startNow: (game_id: string) => Promise<ReplyMessage>
  pause: (game_id: string) => Promise<ReplyMessage>
  resume: (game_id: string) => Promise<ReplyMessage>
}

export function useActivity(previewPhase?: string | null): Activity {
  const isPreview = Boolean(import.meta.env.DEV && previewPhase)
  const previewState = isPreview ? getPreviewState(previewPhase!) : null

  const [auth, setAuth] = useState<AuthState>(() =>
    isPreview ? { kind: 'ok', user: USER } : { kind: 'pending' },
  )
  const [snapshot, setSnapshot] = useState<ConnectionSnapshot | null>(() => {
    if (isPreview && previewState) {
      return {
        status: 'connected',
        user: USER,
        state: previewState,
        anchor: { rttMs: 20, perfMs: performance.now(), serverMs: previewState.server_ms },
        rtt: { count: 5, p50: 20, p95: 25, max: 30 },
      }
    }
    return null
  })

  const [isPending, setIsPending] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const toastTimerRef = useRef<number | null>(null)
  const connRef = useRef<Connection | null>(null)

  const showToast = useCallback((msg: string) => {
    if (toastTimerRef.current !== null) {
      window.clearTimeout(toastTimerRef.current)
    }
    setToast(msg)
    toastTimerRef.current = window.setTimeout(() => {
      setToast(null)
      toastTimerRef.current = null
    }, 3000)
  }, [])

  const signIn = useCallback((interactive: boolean) => {
    if (isPreview) return
    const conn = connRef.current
    if (conn === null) return
    setAuth({ kind: 'pending' })
    authenticate(interactive).then(
      (result) => {
        if (connRef.current !== conn) return
        setAuth({ kind: 'ok', user: result.user })
        conn.start(result.session)
      },
      (err: unknown) => {
        if (connRef.current !== conn) return
        const message = err instanceof LoginRequiredError ? err.message : '로그인에 실패했습니다.'
        setAuth({ kind: 'login_required', message })
      },
    )
  }, [isPreview])

  useEffect(() => {
    if (isPreview) return
    const conn = new Connection(browserConnectionOptions())
    connRef.current = conn
    const offChange = conn.subscribe(setSnapshot)
    const offReauth = conn.onReauth(() => signIn(false))
    signIn(false)
    return () => {
      offChange()
      offReauth()
      conn.dispose()
      if (connRef.current === conn) connRef.current = null
    }
  }, [signIn, isPreview])

  // 받은 state가 화면에 반영된 뒤 서버에 입장을 알린다. 연결 모듈이 연결마다 한 번만 보낸다.
  useEffect(() => {
    connRef.current?.notifyRendered()
  }, [snapshot])

  // 다른 참가자가 나가거나 다시 들어오면 알린다. 자동 일시정지는 하지 않는다.
  const state = snapshot?.state ?? null
  const prevStateRef = useRef<StateMessage | null>(null)
  const departedRef = useRef<string[]>([])
  useEffect(() => {
    if (state === null) return
    const alerts = getPresenceAlerts(prevStateRef.current, state, departedRef.current)
    prevStateRef.current = state
    departedRef.current = alerts.departed
    if (alerts.messages.length > 0) showToast(alerts.messages.join(' · '))
  }, [state, showToast])

  const login = useCallback(() => signIn(true), [signIn])

  const wrapAction = useCallback(
    (fn: () => Promise<ReplyMessage>, previewReply: () => ReplyMessage): Promise<ReplyMessage> => {
      if (isPending) return Promise.reject(new Error('이전 요청 처리 중입니다.'))
      setIsPending(true)

      if (isPreview) {
        return new Promise<ReplyMessage>((resolve) => {
          setTimeout(() => {
            setIsPending(false)
            const reply = previewReply()
            if (!reply.ok && reply.message) showToast(reply.message)
            resolve(reply)
          }, 150)
        })
      }

      const conn = connRef.current
      if (!conn) {
        setIsPending(false)
        showToast('연결되어 있지 않습니다.')
        return Promise.reject(new Error('연결되어 있지 않습니다.'))
      }

      return fn()
        .then((reply) => {
          if (!reply.ok) {
            showToast(getReplyMessage(reply))
          }
          return reply
        })
        .catch((err: unknown) => {
          const msg = err instanceof Error ? err.message : '요청 처리에 실패했습니다.'
          showToast(msg)
          throw err
        })
        .finally(() => {
          setIsPending(false)
        })
    },
    [isPending, isPreview, showToast],
  )

  const start = useCallback(
    (game_id: string | null) => {
      const guild_id = getGuildId()
      return wrapAction(
        () => {
          const conn = connRef.current!
          return conn.start(game_id, guild_id)
        },
        () => ({
          t: 'reply',
          id: 'preview-start',
          ok: true,
          code: 'ok',
          message: null,
          state_version: 1,
        }),
      )
    },
    [wrapAction],
  )

  const advantageAction = useCallback(
    (game_id: string, champion_id: string) => {
      return wrapAction(
        () => {
          const conn = connRef.current!
          return conn.advantage(game_id, champion_id)
        },
        () => {
          showToast(`${champion_id} 선택 완료`)
          return {
            t: 'reply',
            id: 'preview-advantage',
            ok: true,
            code: 'ok',
            message: null,
            state_version: 1,
          }
        },
      )
    },
    [wrapAction, showToast],
  )

  const pick = useCallback(
    (game_id: string, turn_id: string, champion_id: string) => {
      return wrapAction(
        () => {
          const conn = connRef.current!
          return conn.pick(game_id, turn_id, champion_id)
        },
        () => {
          showToast(`${champion_id} 선택 완료`)
          return {
            t: 'reply',
            id: 'preview-pick',
            ok: true,
            code: 'ok',
            message: null,
            state_version: 1,
          }
        },
      )
    },
    [wrapAction, showToast],
  )

  const resultAction = useCallback(
    (game_id: string, winner: Team) => {
      return wrapAction(
        () => {
          const conn = connRef.current!
          return conn.result(game_id, winner)
        },
        () => {
          showToast(`${winner === 'team1' ? 'TEAM 1' : 'TEAM 2'} 승리 기록 완료`)
          return {
            t: 'reply',
            id: 'preview-result',
            ok: true,
            code: 'ok',
            message: null,
            state_version: 1,
          }
        },
      )
    },
    [wrapAction, showToast],
  )

  const reverseAction = useCallback(
    (game_id: string, expected_winner: Team) => {
      return wrapAction(
        () => {
          const conn = connRef.current!
          return conn.reverse(game_id, expected_winner)
        },
        () => {
          showToast('번복 완료')
          return {
            t: 'reply',
            id: 'preview-reverse',
            ok: true,
            code: 'ok',
            message: null,
            state_version: 1,
          }
        },
      )
    },
    [wrapAction, showToast],
  )

  const gameAction = useCallback(
    (request: (conn: Connection) => Promise<ReplyMessage>, previewId: string) => {
      return wrapAction(
        () => request(connRef.current!),
        () => ({
          t: 'reply',
          id: previewId,
          ok: true,
          code: 'ok',
          message: null,
          state_version: 1,
        }),
      )
    },
    [wrapAction],
  )

  const startNow = useCallback(
    (game_id: string) => gameAction((conn) => conn.requestStartNow(game_id), 'preview-start-now'),
    [gameAction],
  )
  const pauseAction = useCallback(
    (game_id: string) => gameAction((conn) => conn.requestPause(game_id), 'preview-pause'),
    [gameAction],
  )
  const resumeAction = useCallback(
    (game_id: string) => gameAction((conn) => conn.requestResume(game_id), 'preview-resume'),
    [gameAction],
  )

  return {
    auth,
    snapshot,
    state,
    isPending,
    toast,
    login,
    showToast,
    start,
    advantage: advantageAction,
    pick,
    result: resultAction,
    reverse: reverseAction,
    startNow,
    pause: pauseAction,
    resume: resumeAction,
  }
}
