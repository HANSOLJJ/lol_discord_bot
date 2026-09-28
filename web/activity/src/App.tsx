// 실행 위치(Discord 액티비티 여부) 또는 개발 미리보기에 따라 화면을 나누는 최상위 컴포넌트
import { ActivityScreen } from './components/ActivityScreen.tsx'
import { BrowserNotice } from './components/BrowserNotice.tsx'
import { isDiscordLaunch } from './lib/discord.ts'
import { getPreviewPhase } from './lib/preview.ts'

const inDiscord = isDiscordLaunch()
const previewPhase = import.meta.env.DEV ? getPreviewPhase() : null

export default function App() {
  if (import.meta.env.DEV && previewPhase !== null) {
    return <ActivityScreen previewPhase={previewPhase} />
  }
  return inDiscord ? <ActivityScreen /> : <BrowserNotice />
}
