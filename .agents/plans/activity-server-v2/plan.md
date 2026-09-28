# 액티비티 서버·봇 통신 규격 v2 구현 계획

작성일은 2026-09-28이다. 형식의 기준은 [docs/ACTIVITY_PROTOCOL.md](../../../docs/ACTIVITY_PROTOCOL.md) 7~13절이고, 설계 배경은 [통합 계획](../activity-integration/plan.md) 5·6·8·15절이다.
진행 상태는 [checklist.md](checklist.md), 결정 이유는 [context-notes.md](context-notes.md)에 기록한다.

## 목표

- 새 판 시작, 픽, 승리 팀 입력, 번복을 액티비티에서 처리한다. 디스코드 `/게임시작`, `/승리`, `/번복`은 예비 경로로 남긴다.
- 운영 봇(`pick_mode: embed`)의 동작은 바꾸지 않는다. dev 봇은 `dev_pick_mode: activity`로 새 방식을 쓴다.

## 구조

| 모듈 | 역할 |
|---|---|
| `game_core.py` (신규) | 게임 상태와 `lock`(기존 `pick_lock`)을 소유한다. 판 만들기(`new_game`), 자동 배정(`auto_assign`), 승리 기록(`record_result_locked`), 번복(`reverse_locked`)을 디스코드와 분리한 공통 함수로 둔다. activity 모드의 시계·타이머·요청 판정(`activity_start/pick/result/reverse`), state 본문(`snapshot`)과 권한(`me`)도 여기에 둔다. 디스코드를 import하지 않으므로 테스트에서 가짜 시계·저장 함수로 검증한다. |
| `got_champe.py` | 디스코드 응답·메시지·embed 모드 카운트다운만 맡는다. 전역 게임 상태는 `game.<이름>`으로 옮긴다. activity 모드의 채널 현황판과 LAUNCH_ACTIVITY 버튼, 액티비티 요청 뒤의 채널 공지를 `effects`로 제공한다. |
| `activity_server.py` | 세션·WebSocket·형식 검증·요청 멱등성·state 방송을 맡는다. 게임 판정은 주입받은 `game`에 맡긴다. |

## 순서

1. `game_core.py`로 공통 상태·함수를 옮기고 got_champe가 쓰게 한다(embed 동작 유지) → 테스트: embed 회귀.
2. activity 모드 시계·타이머·판정·snapshot·me → 테스트: 규칙.
3. activity_server v2(데모 제거, 요청 처리, 멱등성) → 테스트: WS 왕복.
4. got_champe activity 모드 채널 현황판·LAUNCH_ACTIVITY·액티비티 시작 연결, config.
5. 전체 테스트·py_compile 후 보고.
