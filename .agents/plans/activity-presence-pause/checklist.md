# 체크리스트 — activity-presence-pause (protocol v4)

## 서버 (`activity_server.py`, `game_core.py`)

- [ ] `ready` 메시지 처리(연결당 한 번, 응답 없음, 재연결 시 다시 받기)
- [ ] 사용자별 ready 연결 수 집계(다중 연결은 한 명, 전부 끊기면 제외, 관전자 제외)
- [x] `heartbeat=10` 끊김 감지. 창 닫기는 즉시 반영, 휴대폰 백그라운드는 운영 실측에서 15초 안에 감지되지 않아 보장하지 않기로 함(2026-09-29)
- [ ] 전원 입장 시 5초 카운트다운 시작, 이탈 시 취소(`start_now` 강제분은 유지)
- [ ] `start_now` 요청과 판정 순서(`wrong_phase`·`not_allowed`·`paused`)
- [ ] `pause`·`resume`과 남은 시간 보존·재장전, 정지 중 `paused` 거절
- [ ] `/챔피언리셋` 명령(누구나, 확인 없음, 다음 판부터 적용)
- [ ] `uv run python -m unittest discover -s tests` 전부 통과

## 화면 (`web/activity/src`)

- [ ] 입장 점(팀 칸 이름 옆) + 상단 "입장 n/6"
- [ ] `starting` 대기·카운트다운 표시와 "지금 시작" 버튼
- [ ] 일시정지/재개 버튼과 "⏸ X님이 일시정지함" 배너
- [ ] 이탈·재입장 토스트("⚠ X님 연결 끊김 — 필요하면 일시정지하세요")
- [ ] `npm test`, `npm run build`, `npm run lint` 통과

## 문서 (이 worktree)

- [x] `docs/ACTIVITY_PROTOCOL.md` §15 작성, 제목·§1·예시 `protocol_version` 4
- [x] `README.md`·`AGENTS.md`에 `/챔피언리셋`·입장 시작·일시정지 반영
- [x] 이 계획 디렉터리(plan·checklist·context-notes) 작성

## 배포

- [ ] 맥미니 dev(`lol-bot-dev`·`lol-web-dev`)에서 TEST2 화면 확인
- [ ] 배포 전 `game_core.py`의 임시 `MAX_PLAYERS = 2` 되돌리기(사용자 테스트 종료 확인 후)
- [ ] 운영에서 2인 이상으로 입장 표시 → 전원 입장 5초 카운트다운 → 일시정지/재개 → 미입장 시 "지금 시작" 확인
