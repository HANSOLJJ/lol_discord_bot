// 화면 하단 알림 토스트 컴포넌트
import styles from './Toast.module.css'

interface Props {
  message: string | null
}

export function Toast({ message }: Props) {
  if (!message) return null
  return (
    <div role="status" className={styles.toast}>
      {message}
    </div>
  )
}
