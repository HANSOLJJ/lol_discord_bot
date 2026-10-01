// Discord 인증과 액티비티 서버 연결을 한 번만 만들고 React 상태로 구독하는 훅
import { useCallback, useEffect, useRef, useState } from 'react'
import { browserConnectionOptions, Connection, type ConnectionSnapshot } from '../lib/connection.ts'
import { authenticate, getGuildId, LoginRequiredError } from '../lib/discord.ts'
import { getPreviewState } from '../lib/preview.ts'
import { getReplyMessage, type DiscordUser, type ReplyMessage, type StateMessage, type Team } from '../lib/protocol.ts'
import { getPresenceAlerts } from '../lib/view-logic.ts'
import { USER } from '../test/fixtures.ts'

/** 로그인 진행 상태. login_required면 ActivityScreen이 "Discord로 로그인" 버튼을 보인다. */
export type AuthState =
  | { kind: 'pending' }
  | { kind: 'login_required'; message: string }
  | { kind: 'ok'; user: DiscordUser }

/** 화면이 쓰는 값과 요청 함수 묶음. 요청 함수는 서버의 reply를 돌려주고, 실패하면 토스트도 띄운다. */
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

/**
 * 인증과 서버 연결(Connection)을 컴포넌트가 살아 있는 동안 한 번만 만들고, 바뀐 상태를 React 상태로 내려 준다.
 * previewPhase가 있으면(개발 서버의 ?preview=) 서버에 연결하지 않고 고정 상태와 가짜 응답을 쓴다.
 */
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

  // 토스트는 3초 뒤 사라진다. 새 토스트가 오면 앞의 타이머를 지우고 다시 센다.
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

  // 인증한 뒤 받은 세션으로 연결을 시작한다. interactive가 false면 동의 창 없이 조용히 시도한다(처음 열 때·재인증).
  // 인증을 기다리는 사이 연결 객체가 새로 만들어졌으면 낡은 결과는 버린다.
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

  // 연결 객체를 만들고 상태 변화를 구독한다. 서버가 재인증을 요구하면(4401 종료) 조용히 다시 로그인한다.
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

  // 요청 공통 처리. 앞 요청이 끝나기 전에는 새 요청을 막고(isPending), 실패 응답과 예외는 토스트로 알린다.
  // 미리보기에서는 서버 대신 150ms 뒤 previewReply의 가짜 응답을 준다.
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

  // 시작 요청에는 규격 9절대로 SDK의 guildId를 함께 보낸다.
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

  // start_now·pause·resume처럼 미리보기에서 토스트 없이 성공 응답만 주면 되는 요청의 공통 함수.
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
