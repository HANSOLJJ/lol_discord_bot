// 화면 하단 알림 토스트 컴포넌트
import styles from './Toast.module.css'

interface Props {
  message: string | null
}

/** 하단 알림 한 줄. message가 없으면 그리지 않는다. 띄우고 지우는 시점(3초)은 useActivity의 showToast가 정한다. */
export function Toast({ message }: Props) {
  if (!message) return null
  return (
    <div role="status" className={styles.toast}>
      {message}
    </div>
  )
}
