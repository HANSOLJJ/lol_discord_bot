// Discord 안에서 동작하는 픽 화면(반응형 3가지 뷰, phase별 화면, 통신 연동)
import { useActivity } from '../hooks/useActivity.ts'
import { useLayoutMode } from '../hooks/useLayoutMode.ts'
import styles from './ActivityScreen.module.css'
import { ChampionGrid } from './ChampionGrid.tsx'
import { Header } from './Header.tsx'
import { PhaseActions } from './PhaseActions.tsx'
import { PickOrderList } from './PickOrderList.tsx'
import { PipView } from './PipView.tsx'
import { TeamRoster } from './TeamRoster.tsx'
import { Toast } from './Toast.tsx'
import { TurnCountdown } from './TurnCountdown.tsx'

interface Props {
  previewPhase?: string | null
}

export function ActivityScreen({ previewPhase }: Props) {
  const { auth, snapshot, state, isPending, toast, login, start, pick, result, reverse } = useActivity(previewPhase)
  const layoutMode = useLayoutMode()

  // 인증 필요 화면
  if (auth.kind === 'login_required') {
    return (
      <main className={styles.screenMobile}>
        <div className={styles.centerMessage}>
          <div className={styles.centerTitle}>{auth.message}</div>
          <div className={styles.centerSub}>Discord 계정으로 로그인해야 픽 화면을 볼 수 있습니다.</div>
          <button type="button" className={styles.btnPrimary} onClick={login}>
            Discord로 로그인
          </button>
        </div>
      </main>
    )
  }

  // 업데이트 필요 화면 (프로토콜 버전 불일치 또는 4400)
  if (snapshot?.status === 'update_required') {
    return (
      <main className={styles.screenMobile}>
        <div className={styles.centerMessage}>
          <div className={styles.centerTitle}>새 버전이 나왔습니다</div>
          <div className={styles.centerSub}>액티비티를 닫았다가 다시 열어 주세요.</div>
        </div>
      </main>
    )
  }

  // Pip (작은 창) 모드
  if (layoutMode === 'pip') {
    return (
      <div className={styles.screenPip}>
        <PipView state={state} anchor={snapshot?.anchor ?? null} />
        <Toast message={toast} />
      </div>
    )
  }

  const isConnected = snapshot?.status === 'connected'
  const isPc = layoutMode === 'pc'
  const isTurnPhase = state?.phase === 'starting' || state?.phase === 'picking'
  const user = snapshot?.user ?? (auth.kind === 'ok' ? auth.user : null)

  const handlePick = (championId: string) => {
    if (!state || !state.game_id || !state.turn_id) return
    pick(state.game_id, state.turn_id, championId)
  }

  if (isPc) {
    return (
      <main className={styles.screenPc}>
        <Header status={snapshot?.status ?? 'idle'} user={user} state={state} isPc={true} />
        <TeamRoster state={state} isPc={true} />

        <div className={styles.pcBodyGrid}>
          <div className={styles.pcLeftCol}>
            {isTurnPhase && state ? (
              <TurnCountdown state={state} anchor={snapshot?.anchor ?? null} />
            ) : (
              <PhaseActions
                state={state}
                isConnected={isConnected}
                isPending={isPending}
                onStart={start}
                onReport={result}
                onReverse={reverse}
              />
            )}
            <PickOrderList state={state} isPc={true} />
          </div>

          <ChampionGrid state={state} isPending={isPending} isPc={true} onPick={handlePick} />
        </div>

        <Toast message={toast} />
      </main>
    )
  }

  return (
    <main className={styles.screenMobile}>
      <Header status={snapshot?.status ?? 'idle'} user={user} state={state} isPc={false} />
      <TeamRoster state={state} isPc={false} />

      {isTurnPhase && state ? (
        <TurnCountdown state={state} anchor={snapshot?.anchor ?? null} />
      ) : (
        <PhaseActions
          state={state}
          isConnected={isConnected}
          isPending={isPending}
          onStart={start}
          onReport={result}
          onReverse={reverse}
        />
      )}

      <PickOrderList state={state} isPc={false} />
      <ChampionGrid state={state} isPending={isPending} isPc={false} onPick={handlePick} />

      <Toast message={toast} />
    </main>
  )
}
