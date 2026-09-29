# 입장 현황 · 전원 입장 시작 · 수동 일시정지 · 챔피언 풀 비우기 (protocol v4)

원본 전체 계획: `C:/Users/noble/.claude/plans/goofy-napping-seahorse.md`.
공통 계약(서버·화면·문서 워커가 그대로 쓰는 이름·의미): `presence_contract.md`(코디네이터 scratchpad).
통신 규격: [docs/ACTIVITY_PROTOCOL.md](../../docs/ACTIVITY_PROTOCOL.md) §15.

## 배경

디스코드가 액티비티를 여는 시간이 컴퓨터마다 달라서, 늦게 연 사람은 이미 자기 차례 시간이 흘러간 상태로 들어온다. 원인은 게임 시작 뒤 `auto_start_seconds`(운영 15초)가 지나면 참가자 접속 여부와 상관없이 첫 픽 타이머가 도는 구조다. 서버는 누가 화면에 들어와 있는지 모른다.

## 변경 요약

- 입장(presence): 클라이언트가 첫 `state`를 그린 뒤 `ready`를 보내고, 서버가 참가자 중 입장자를 `present`로 알린다. 끊김은 WebSocket heartbeat(10초)로 감지한다.
- 전원 입장 시작: `starting`은 입장 대기가 되고, 전원 입장 시 5초 카운트다운 뒤 기존처럼 `advantage`·`picking`으로 간다. 안 들어오는 사람이 있으면 참가자 누구나 `start_now`로 시작한다.
- 수동 일시정지: `pause`·`resume`. 참가자만, 시간 제한 없음, 재개는 참가자 누구나. 정지 중 픽·어드밴티지·시작 요청은 `paused`로 거절한다.
- `/챔피언리셋`: 챔피언 제외 목록(`game.excluded`)을 비운다. 다음 판부터 적용된다.
- `protocol_version` 3 → 4.

## 작업 분담

- 서버 워커(claude): `activity_server.py`(ready, heartbeat, set_present 반영), `game_core.py`(전원 입장 시작, 일시정지, 챔피언 풀 비우기).
- 화면 워커(agy): `web/activity/src`(입장 점·입장 n/6, 지금 시작·일시정지 버튼, 이탈 토스트).
- 문서 워커(muse, 이 worktree): 규격 §15, README·AGENTS.md, 이 계획 파일들.
