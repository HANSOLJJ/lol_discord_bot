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
  /** 개발 서버의 ?preview= 값. 있으면 서버에 연결하지 않고 고정 상태로 그린다(App.tsx가 넘긴다). */
  previewPhase?: string | null
}

/**
 * 픽 화면 본체. 로그인·버전 확인 화면을 먼저 걸러 낸 뒤, 화면 크기(useLayoutMode)에 따라
 * PiP·PC·모바일 배치 중 하나로 그린다. 서버와의 통신은 모두 useActivity가 맡는다.
 */
export function ActivityScreen({ previewPhase }: Props) {
  const { auth, snapshot, state, isPending, toast, login, start, advantage, pick, result, reverse, startNow, pause, resume } =
    useActivity(previewPhase)
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
  // 카운트다운이 도는 단계면 TurnCountdown을, 대기·결과 단계면 PhaseActions를 같은 자리에 그린다.
  const isTurnPhase = state?.phase === 'starting' || state?.phase === 'advantage' || state?.phase === 'picking'
  const user = snapshot?.user ?? (auth.kind === 'ok' ? auth.user : null)

  // 챔피언 그리드는 어드밴티지(밴·강제픽 지정)와 일반 픽이 함께 쓴다. 지금 단계에 맞는 요청으로 나눠 보낸다.
  const handlePick = (championId: string) => {
    if (!state || !state.game_id) return
    if (state.phase === 'advantage') {
      advantage(state.game_id, championId)
      return
    }
    if (state.phase === 'picking' && state.turn_id) {
      pick(state.game_id, state.turn_id, championId)
    }
  }

  // PC: 위에 헤더·팀, 아래 왼쪽 열에 카운트다운과 픽 순서, 오른쪽에 챔피언 그리드
  if (isPc) {
    return (
      <main className={styles.screenPc}>
        <Header status={snapshot?.status ?? 'idle'} user={user} state={state} isPc={true} />
        <TeamRoster state={state} isPc={true} />

        <div className={styles.pcBodyGrid}>
          <div className={styles.pcLeftCol}>
            {isTurnPhase && state ? (
              <TurnCountdown
                state={state}
                anchor={snapshot?.anchor ?? null}
                isConnected={isConnected}
                isPending={isPending}
                onStartNow={startNow}
                onPause={pause}
                onResume={resume}
              />
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

  // 모바일: 같은 부품을 위에서 아래로 한 줄로 쌓는다
  return (
    <main className={styles.screenMobile}>
      <Header status={snapshot?.status ?? 'idle'} user={user} state={state} isPc={false} />
      <TeamRoster state={state} isPc={false} />

      {isTurnPhase && state ? (
        <TurnCountdown
          state={state}
          anchor={snapshot?.anchor ?? null}
          isConnected={isConnected}
          isPending={isPending}
          onStartNow={startNow}
          onPause={pause}
          onResume={resume}
        />
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
