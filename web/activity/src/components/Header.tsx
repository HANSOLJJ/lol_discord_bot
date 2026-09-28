// 픽 화면 상단 헤더: 연결 상태, 라운드/시즌, 사용자 이름
import type { ConnectionStatus } from '../lib/connection.ts'
import type { DiscordUser, StateMessage } from '../lib/protocol.ts'
import styles from './Header.module.css'

interface Props {
  status: ConnectionStatus
  user: DiscordUser | null
  state: StateMessage | null
  isPc?: boolean
}

type Tone = 'ok' | 'wait' | 'bad'

function statusLabel(status: ConnectionStatus): { label: string; tone: Tone } {
  switch (status) {
    case 'connected':
      return { label: '연결됨', tone: 'ok' }
    case 'disconnected':
      return { label: '연결 끊김', tone: 'bad' }
    case 'update_required':
      return { label: '업데이트 필요', tone: 'bad' }
    case 'reauth_required':
      return { label: '다시 로그인 필요', tone: 'bad' }
    default:
      return { label: '연결 중', tone: 'wait' }
  }
}

export function Header({ status, user, state, isPc = false }: Props) {
  const { label, tone } = statusLabel(status)
  const roundText =
    state?.round !== null && state?.round !== undefined && state?.season !== null && state?.season !== undefined
      ? `ROUND ${state.round} · 시즌 ${state.season}`
      : ''
  const displayName = user ? user.global_name ?? user.username : ''

  return (
    <header className={styles.header}>
      <div className={styles.left}>
        <span className={styles.dot} data-tone={tone} aria-hidden="true" />
        <span className={styles.statusText}>{label}</span>
        {isPc && roundText && <span className={styles.roundInfoPc}>{roundText}</span>}
      </div>
      {!isPc && roundText && <span className={styles.roundInfo}>{roundText}</span>}
      <span className={styles.userName}>{displayName}</span>
    </header>
  )
}
