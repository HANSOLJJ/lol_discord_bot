# 액티비티 서버 v2 구현 보고 (2026-09-28)

브랜치는 `HANSOLJJ/activity-server`이고 push하지 않았다. 기준은 docs/ACTIVITY_PROTOCOL.md(protocol_version 2)이다.

## 커밋

| 해시 | 내용 |
|---|---|
| 2ac3978 | 구현 계획·체크리스트·결정 기록 |
| 3a016d1 | 게임 상태와 공통 함수를 `game_core.py`로 추출, got_champe가 사용 (embed 동작 유지) |
| d485fcc | activity 모드 시계·타이머·요청 판정·state·권한 (`game_core.py`) |
| 70e4e2c | `activity_server.py` v2 (게임 요청, 멱등성, 사용자별 state, 데모 제거) |
| c591f02 | got_champe activity 모드 현황판·픽 화면 열기·액티비티 공지 연결, `config.json` pick_mode |

## 검증

- `uv run python -m unittest discover -s tests -t .`: 97개 통과. 작업 전 44개(test_pick_logic 16, test_activity_server 28)에서 데모 테스트 5개를 지우고 v2에 맞게 고쳤으며, test_game_core 19개, test_activity_rules 30개, test_activity_server의 종료·게임 요청 테스트 9개를 더했다.
- `uv run python -m py_compile got_champe.py activity_server.py pick_logic.py`: 통과.

## 공통 함수 (디스코드 명령과 액티비티가 같은 함수·같은 `game.lock`을 쓴다)

`game_core.py`의 `GameCore`(got_champe에서는 전역 `game`). 예전 `pick_lock`은 `game.lock`이다.

| 함수 | 위치 | 쓰는 곳 |
|---|---|---|
| `new_game(members, mode)` | game_core.py:236 | `/게임시작`, 액티비티 `start` |
| `auto_assign(picker_index)` | game_core.py:334 | embed 타이머(`pick_timeout_handler`), activity 타이머 |
| `record_result_locked(team_key)` | game_core.py:362 | `VictorySelect.callback`, 액티비티 `result` |
| `reverse_locked(game)` | game_core.py:476 | `ReverseConfirmView.confirm`, 액티비티 `reverse` |
| `snapshot()`, `me()` | game_core.py:665, 741 | 액티비티 state |
| `activity_start/pick/result/reverse` | game_core.py:772~ | 액티비티 요청 판정(규격 9절 순서) |

got_champe 쪽 공통 알림: `announce_result`(결과·오늘의 결과·누적 전적), `announce_reverse`(정정 공지)를 드롭다운·확인 버튼과 액티비티가 함께 쓴다.

## embed 모드에서 바뀐 것이 없다는 근거

- `config.json`의 `pick_mode`는 `"embed"`이다. embed 판은 `game.mode == "embed"`라 액티비티에는 항상 `phase: "none"`, `can_start=false`로 보이고 `start`는 `not_allowed`이다(EmbedModeTest, EmbedModeSocketTest).
- 채널 버튼·카운트다운·매초 편집 코드(`ChampionButton`, `pick_timeout_handler`, `show_countdown_step`, `push_channel_embed`)는 전역 이름을 `game.`으로 바꾼 것 외에 그대로다. `flush_embed_updates`에는 `game.mode == "activity"`일 때만 타는 분기 하나를 더했다.
- 예전 got_champe.py의 한국어 문자열 상수가 새 got_champe.py·game_core.py에 모두 남아 있음을 AST로 대조했다. 함수 목록 차이는 `calculate_pick_order`·`pick_random_champions`의 game_core 이동뿐이다.
- test_game_core.py가 예전 코드와 같은 문구, 저장 순서(승수 저장 → 판 기록, 번복은 판 기록 → 승수), 실패 시 원복(승수 저장 실패면 아무것도 바뀌지 않음, 번복 저장 실패면 판 기록 원복), 오늘의 결과 O/X, 라운드·session_rounds를 검증한다. test_pick_logic.py 16개도 그대로 통과한다.
- 의도한 작은 차이: 승리 기록의 판정·저장·판 기록을 락 안에서 한 번에 하고(예전은 래치만 락 안), `/게임시작`의 상태 초기화도 락 안에서 한다. `current_teams` 비우기가 결과 embed 전송 전으로 당겨졌다(결과 embed는 기록 시점 사본으로 그린다). 사용자에게 보이는 문구와 순서는 같다.

## 실제 디스코드에서 확인할 항목

1. "픽 화면 열기" 버튼의 LAUNCH_ACTIVITY(type 12) 원시 응답이 PC·모바일에서 액티비티를 여는지, 실패 시 안내 문구가 뜨는지, py-cord가 이중 응답하지 않는지.
2. 액티비티 `start`의 길드 조회와 온라인 일반 사용자 6명 선정(운영 모드, Presence·Members 인텐트), DEV_MODE의 wins_dev 6명 사용.
3. activity 모드 현황판: `/게임시작`과 액티비티 시작 모두에서 팀짜기(config channels)에 한 번 올라가고, 픽 시작·픽·자동 배정·완료 때만 고쳐지는지, 다음 판에서 "종료된 게임"으로 바뀌고 버튼이 비활성화되는지.
4. 액티비티 결과 입력·번복 뒤 결과·오늘의 결과·누적 전적·정정 공지가 `/승리`·`/번복`과 같게 나오는지, `history_data_dev.json`에 한국어 챔피언 이름이 저장되는지.
5. 디스코드 `/번복`으로 화면의 판을 뒤집었을 때 액티비티 state의 `result.corrected`가 바뀌는지, `/승리`(예비 경로)로 기록해도 액티비티가 `completed`로 바뀌는지.
6. 운영 봇(`pick_mode: embed`) 한 판이 예전과 같게 진행되는지(채널 버튼·카운트다운·자동 배정·승리·번복).
7. 서버 재시작 뒤 새 `server_epoch`의 `none`이 오는지.

## 남은 일·주의

- `config.json` `channels`를 `["팀짜기"]`로 줄이는 것은 운영 전환(6단계) 때 한다.
- 액티비티에서 시작한 판의 결과·번복 공지는 그 판의 채널(config channels)로 간다. `/시즌시작` 뒤 이전 시즌 판은 액티비티에서 번복할 수 없다(`record_failed`).
