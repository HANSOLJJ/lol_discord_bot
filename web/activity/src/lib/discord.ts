// Discord 실행 여부 판별과 Embedded App SDK 인증·/pick-api/token 세션 교환
import { DiscordSDK } from '@discord/embedded-app-sdk'
import { parseTokenResponse, type DiscordUser } from './protocol.ts'

export interface AuthResult {
  session: string
  sessionExpiresMs: number
  user: DiscordUser
}

/** 사용자가 로그인 버튼을 눌러 다시 시도해야 하는 실패 */
export class LoginRequiredError extends Error {}

/** frame_id는 Discord 안에서 열렸는지 화면을 나누는 용도로만 쓴다. 인증 근거가 아니다. */
export function isDiscordLaunch(search: string = location.search): boolean {
  return new URLSearchParams(search).has('frame_id')
}

let sdk: DiscordSDK | null = null
let ready: Promise<void> | null = null

function clientId(): string {
  return import.meta.env.VITE_DISCORD_CLIENT_ID
}

/** 현재 실행 중인 길드 ID를 반환한다. */
export function getGuildId(): string | null {
  return sdk?.guildId ?? null
}

function readySdk(): { sdk: DiscordSDK; ready: Promise<void> } {
  if (sdk === null || ready === null) {
    sdk = new DiscordSDK(clientId())
    ready = sdk.ready()
  }
  return { sdk, ready }
}

let inflight: Promise<AuthResult> | null = null

/**
 * ready → authorize → POST /pick-api/token → authenticate 순서로 인증한다.
 * interactive가 false면 prompt: 'none'으로 조용히 시도하고, 버튼으로 다시 시도할 때는 동의 창을 허용한다.
 * 진행 중인 인증이 있으면 그 결과를 함께 기다린다.
 */
export function authenticate(interactive: boolean): Promise<AuthResult> {
  if (inflight === null) {
    inflight = runAuthenticate(interactive).finally(() => {
      inflight = null
    })
  }
  return inflight
}

async function runAuthenticate(interactive: boolean): Promise<AuthResult> {
  const { sdk, ready } = readySdk()
  await ready

  let code: string
  try {
    const result = await sdk.commands.authorize({
      client_id: clientId(),
      response_type: 'code',
      state: '',
      scope: ['identify'],
      ...(interactive ? {} : { prompt: 'none' as const }),
    })
    code = result.code
  } catch {
    throw new LoginRequiredError('Discord 로그인이 필요합니다.')
  }

  let res: Response
  try {
    res = await fetch('/pick-api/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code }),
    })
  } catch {
    throw new LoginRequiredError('서버에 연결하지 못했습니다.')
  }
  const body: unknown = await res.json().catch(() => null)
  const token = res.ok ? parseTokenResponse(body) : null
  if (token === null) {
    throw new LoginRequiredError(res.status === 429 ? '요청이 많습니다. 잠시 뒤 다시 시도하세요.' : '로그인에 실패했습니다.')
  }

  try {
    await sdk.commands.authenticate({ access_token: token.access_token })
  } catch {
    throw new LoginRequiredError('Discord 인증에 실패했습니다.')
  }
  return { session: token.session, sessionExpiresMs: token.session_expires_ms, user: token.user }
}
