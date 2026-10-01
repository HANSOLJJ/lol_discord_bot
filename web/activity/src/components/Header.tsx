// 픽 화면 상단 헤더: 연결 상태, 라운드/시즌, 사용자 이름
import type { ConnectionStatus } from '../lib/connection.ts'
import type { DiscordUser, StateMessage } from '../lib/protocol.ts'
import { getHeaderPresence } from '../lib/view-logic.ts'
import styles from './Header.module.css'

interface Props {
  status: ConnectionStatus
  user: DiscordUser | null
  state: StateMessage | null
  /** PC면 라운드·입장 표시를 왼쪽 연결 상태 옆에 붙이고, 모바일이면 가운데에 따로 둔다. */
  isPc?: boolean
}

/** 연결 상태 점의 색. 스타일 시트가 data-tone 값으로 색을 고른다. */
type Tone = 'ok' | 'wait' | 'bad'

/** 연결 상태를 헤더 문구와 점 색으로 바꾼다. 목록에 없는 상태는 모두 "연결 중"으로 본다. */
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

/** 픽 화면 맨 위 줄. 왼쪽에 연결 상태, 가운데에 라운드·시즌과 입장 인원, 오른쪽에 내 이름을 보인다. */
export function Header({ status, user, state, isPc = false }: Props) {
  const { label, tone } = statusLabel(status)
  const roundText =
    state?.round !== null && state?.round !== undefined && state?.season !== null && state?.season !== undefined
      ? `ROUND ${state.round} · 시즌 ${state.season}`
      : ''
  const displayName = user ? user.global_name ?? user.username : ''
  // "입장 n/6" 배지. 어느 단계에서 보일지는 getHeaderPresence가 정하고, 전원 입장(data-full)이면 스타일이 바뀐다.
  const presence = getHeaderPresence(state)
  const presenceBadge = presence && (
    <span className={isPc ? styles.presencePc : styles.presence} data-full={presence.present === presence.total}>
      입장 {presence.present}/{presence.total}
    </span>
  )

  return (
    <header className={styles.header}>
      <div className={styles.left}>
        <span className={styles.dot} data-tone={tone} aria-hidden="true" />
        <span className={styles.statusText}>{label}</span>
        {isPc && roundText && <span className={styles.roundInfoPc}>{roundText}</span>}
        {isPc && presenceBadge}
      </div>
      {!isPc && (roundText || presenceBadge) && (
        <span className={styles.middle}>
          {roundText && <span className={styles.roundInfo}>{roundText}</span>}
          {presenceBadge}
        </span>
      )}
      <span className={styles.userName}>{displayName}</span>
    </header>
  )
}
