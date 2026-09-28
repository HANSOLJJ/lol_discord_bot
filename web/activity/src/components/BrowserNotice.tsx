// Discord 밖(일반 브라우저)에서 열었을 때 보여주는 실행 안내
import styles from './BrowserNotice.module.css'

export function BrowserNotice() {
  return (
    <main className={styles.screen}>
      <h1 className={styles.title}>Discord 액티비티에서 실행하세요</h1>
      <p className={styles.body}>이 화면은 Discord 음성 채널의 액티비티 안에서만 동작합니다.</p>
      <p className={styles.body}>게임이 시작되면 채널 메시지의 액티비티 실행 버튼을 눌러 주세요.</p>
    </main>
  )
}
