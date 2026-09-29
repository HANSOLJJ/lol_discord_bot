# 서버: 입장 현황 · 전원 입장 시 시작 · 수동 일시정지 · /챔피언리셋

전체 계획은 `~/.claude/plans/goofy-napping-seahorse.md`(1·2·3·6절), 공통 계약은 코디네이터의
`presence_contract.md`(protocol_version 4)이다. 이 폴더는 그 가운데 **서버(파이썬)** 몫만 다룬다.

## 범위
- `game_core.py`: `set_present`, 입장 대기 → 전원 입장 시 `ready_countdown_seconds` 카운트다운, `activity_start_now`,
  `activity_pause`·`activity_resume`, 정지 중 pick·advantage 거절, `_auto_start` guard, `snapshot()`의 `present`·`paused`,
  `me()`의 `can_start_now`·`can_pause`·`can_resume`, DEV_MODE 고정 자동 시작 유지, `reset_champion_pool()`.
- `activity_server.py`: `ready` 인라인 처리, 사용자별 ready 연결 수, heartbeat 10초, `start_now`·`pause`·`resume` 요청,
  `PROTOCOL_VERSION = 4`.
- `got_champe.py`: `/챔피언리셋`.
- `config.json`: `ready_countdown_seconds: 5`.
- embed 모드 동작은 바꾸지 않는다.

## 검증
`uv run python -m unittest discover -s tests` 전부 통과. 계획의 "검증" 서버 항목을 모두 테스트로 추가한다.
