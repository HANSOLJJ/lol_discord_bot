# 액티비티 화면: 입장 현황 · 입장 대기/지금 시작 · 일시정지 (protocol_version 4)

공통 계약은 코디네이터 scratchpad의 `presence_contract.md`, 전체 계획은 `~/.claude/plans/goofy-napping-seahorse.md` 5절이다.
이 작업은 `web/activity/src`만 고친다. 서버는 다른 워커가 만든다.

## 목표
- 서버가 보내는 `present`·`paused`·`me.can_start_now/can_pause/can_resume`을 받아 화면에 보여 준다.
- 첫 state를 그린 뒤 연결마다 한 번 `{t:'ready'}`를 보낸다.
- `starting` 입장 대기 중에는 "참가자 입장 대기 n/N"과 "지금 시작" 버튼, 카운트다운 중에는 5초를 보여 준다.
- 일시정지/재개 버튼, "⏸ X님이 일시정지함" 배너, 정지 중 고정 초를 보여 준다.
- 참가자가 나가거나 다시 들어오면 다른 사람 화면에 토스트를 띄운다.

## 순서
1. protocol.ts + fixtures/preview 새 필드 → protocol 테스트
2. connection.ts ready·요청 3종 → connection 테스트
3. view-logic.ts 계산 함수 → view-logic 테스트
4. useActivity 연동(ready, 액션, 이탈 알림 토스트)
5. 컴포넌트(TeamRoster, Header, TurnCountdown, PipView)
6. `npm test`, `npm run build`, `npm run lint`
