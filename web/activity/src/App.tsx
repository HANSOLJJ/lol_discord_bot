// 실행 위치(Discord 액티비티 여부) 또는 개발 미리보기에 따라 화면을 나누는 최상위 컴포넌트
import { ActivityScreen } from './components/ActivityScreen.tsx'
import { BrowserNotice } from './components/BrowserNotice.tsx'
import { isDiscordLaunch } from './lib/discord.ts'
import { getPreviewPhase } from './lib/preview.ts'

// 실행 위치와 미리보기 여부는 페이지가 열린 뒤 바뀌지 않으므로 모듈을 불러올 때 한 번만 판정한다.
const inDiscord = isDiscordLaunch()
const previewPhase = import.meta.env.DEV ? getPreviewPhase() : null

/**
 * 개발 서버의 ?preview=를 먼저 보고, 다음으로 디스코드 안이면 픽 화면, 아니면 실행 안내를 그린다.
 * 운영 빌드에서는 import.meta.env.DEV가 false라 미리보기 분기가 빠진다.
 */
export default function App() {
  if (import.meta.env.DEV && previewPhase !== null) {
    return <ActivityScreen previewPhase={previewPhase} />
  }
  return inDiscord ? <ActivityScreen /> : <BrowserNotice />
}
