# 결정 기록

- 2026-09-29: 계약서 갱신으로 `paused.remaining_ms`는 `number | null`이다. `starting` 입장 대기 중 정지면 null이며 화면은 초 없이 "입장 대기 중 일시정지"로 보여 준다.
- 2026-09-29: PipView에는 버튼을 넣지 않고 표시만 넣는다(코디네이터 확인). PiP에서 누르면 창이 커지는 기존 동작을 유지한다.
- 2026-09-29: 기준 테스트는 107개 통과 상태에서 시작했다.
- 2026-09-29: `ready`는 훅에서 snapshot이 바뀔 때마다 `notifyRendered()`를 부르고, 연결 모듈이 `#open && #gotHello && #gotState && !#readySent`로 연결당 한 번만 보낸다. 재연결 직후 state가 무시돼도 이어지는 상태 변화에서 보내진다.
- 2026-09-29: 이탈 알림은 처음 입장과 구분하려고 "이번 판에서 나갔던 사람" 목록(departed)을 함께 넘기는 순수 함수로 만들었다. 내 변화는 알리지 않고, 결과 단계에서는 목록만 갱신한다.
- 2026-09-29: 진행 막대 길이는 starting 5초(READY_COUNTDOWN_SECONDS), advantage·picking 20초(TURN_SECONDS) 상수다. 서버 설정값이 state에 없어서다.
- 2026-09-29: 정지 중에는 `canClickChampion`이 false를 돌려 카드 클릭을 막는다(서버도 paused로 거절).
- 2026-09-29: 정지한 사람이 참가자가 아니면(DEV_MODE) 배너 이름은 "누군가"로 표시한다.
