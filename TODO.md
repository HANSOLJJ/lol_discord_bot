# TODO

할 일을 순서대로 적는다. 위 항목이 끝나야 아래 항목을 시작한다. 끝난 항목은 날짜와 커밋을 적고 체크한다.

## 1. 6명 실전 테스트 (액티비티)

2026-09-29에 운영 픽을 액티비티(`pick_mode: activity`)로 바꿨지만, 6명이 실제로 한 판을 한 적은 아직 없다(2026-10-01 기준).
"액티비티로 실제 게임을 한두 번 문제없이 하면 채널 버튼 방식을 지운다"가 2026-09-29의 결정이다.

- [x] 6명이 각자 액티비티를 열고 한 판을 끝까지 진행한다 (2026-10-16~17 실전, 사용자 확인)
  - [x] 전원 입장 표시(입장 n/6)와 5초 뒤 자동 시작, "지금 시작"
  - [x] 20초 카운트다운이 6명 화면에서 같게 보이는지, 숫자가 빠지지 않는지
  - [x] 픽, 재클릭 취소, 시간 초과 자동 배정
  - [x] 5·6위 어드밴티지(밴·강제픽)가 걸리는 판이면 그 흐름
  - [x] 일시정지·재개
  - [x] 승리 팀 입력 → 대시보드(lol.hansoljj.com)에 기록 반영, 필요하면 번복
  - [x] PC와 휴대폰을 섞어서 확인
- [x] 한 판 더 해서 문제가 없는지 확인한다
- [x] 문제가 있으면 여기에 적고 고친다
  - 세션 발급 1시간 뒤 전원 4401 → 액티비티 재로그인 실패, 채널을 나갔다 들어와야 복구. 연결 중에는 세션을 끊지 않게 고침(2026-10-19, 91390eb). 서버 재시작으로 세션이 사라지는 경우는 남아 있어 게임 중에는 `lol-bot`을 재시작하지 않는다

## 2. 채널 버튼 방식(`pick_mode: embed`) 삭제

1번이 끝난 뒤에 한다. 삭제 전 기준점은 git 태그 `embed-mode-last`이다. 되살릴 일이 생기면 이 태그에서 꺼낸다.

- [x] `got_champe.py`에서 embed 모드 전용 코드를 지운다 (2026-10-19, b13300e. TODO에 없던 `send_pick_complete`도 embed 경로 전용이라 함께 지움)
  - 카운트다운(`show_countdown_step`, `countdown_step_seconds`, `start_pick_timer`, `pick_timeout_handler`)
  - 자동 시작(`begin_champion_select`, `auto_start_handler`)과 문구(`turn_description`, `start_countdown_description`)
  - 챔피언 버튼(`ChampionView`, `ChampionButton`)과 `/게임시작`의 embed 분기
  - `flush_embed_updates` 안의 embed 분기. **편집 파이프라인 자체(`request_embed_update` → `flush_embed_updates` → `broadcast_embed_update` → `push_channel_embed`)는 activity 현황판도 쓴다**(`ActivityEffects.board_changed`). 지우지 말고, 편집이 판당 몇 번으로 줄어든 만큼 단순하게 줄일 수 있는지만 본다
    - 판당 채널마다 7~8회라 채널당 0.5초 간격과 같은 화면 중복 방지를 지움(db941bd)
  - 정확한 범위는 삭제할 때 호출 관계를 따라가며 다시 확인한다. activity 모드도 쓰는 함수(예: `get_selection_status`, `close_champion_messages`)는 남긴다
- [x] `config.json`에서 `pick_mode`·`dev_pick_mode`와 embed 전용 키(`countdown_step_seconds`)를 정리한다. `load_config`의 기본값(`pick_mode: "embed"`)과 `game_core.py`의 `pick_mode()` 분기도 함께 정리한다. `auto_start_seconds`·`dev_auto_start_seconds`는 DEV_MODE가 아직 쓰므로 남긴다 (b13300e)
- [x] embed 모드 전용 테스트를 정리한다 (b13300e). ~~`pick_logic.py` 테스트는 남긴다~~ → 사용자 결정으로 `pick_logic.py`도 지우고 액티비티에 필요한 두 단계만 game_core에 둠(9896c54)
- [x] 문서를 정리한다: docs/INFRA.md의 "embed로 되돌리기" 안내, docs/ACTIVITY_PROTOCOL.md의 embed 언급, AGENTS.md, README.md, DEPLOY_MACMINI.md
- [x] Python 테스트, 스모크 테스트, DEV 봇으로 한 판을 돌려 확인한다
  - [x] Python 테스트 159개, 스트레스 도구 65케이스, 편집 파이프라인 스모크 점검 통과
  - [x] DEV 봇 두 판 (2026-10-19, TEST2): 새 판·어드밴티지·픽마다 현황판 갱신, 이전 판 종료 표시와 버튼 비활성화, 결과 기록 확인. 같은 날 운영 `lol-bot`을 647d579로 재시작

## 3. `got_champe.py` 나누기

2번이 끝난 뒤에 한다(지울 코드를 먼저 지워야 나눌 양이 줄어든다). 2번 뒤 1,352줄이다(2번 전 1,885줄).

- [ ] 2번 뒤 남은 구성을 다시 보고 나눌 단위를 정한다. 지금 보이는 후보는 다음과 같다
  - 설정·전적·챔피언 데이터 로드 (`load_config`, `load_wins`, `fetch_champion_data` 등)
  - 팀짜기 채널 현황판과 "픽 화면 열기" (`build_activity_board`, `send_activity_board`, `ActivityLaunchView` 등)
  - 슬래시 커맨드별 묶음: `/게임시작`, `/승리`(`VictoryView`), `/누적결과`, `/시즌시작`(`SeasonConfirmView`), `/챔피언리셋`, `/번복`(`ReverseConfirmView`). py-cord의 Cog로 나누는 방법을 검토한다
  - `got_champe.py`에는 봇 생성, `on_ready`, 실행부(`main`)만 남긴다
- [ ] 모듈 전역 상태(게임 진행·메시지 목록 등)를 어디에 둘지 먼저 정한다. 나누기의 가장 큰 걸림돌이다
- [ ] pm2 실행 명령(`uv run python -u got_champe.py`)은 그대로 두는 방향으로 한다
- [ ] 한 번에 한 단위씩 옮기고, 옮길 때마다 테스트와 DEV 봇 한 판으로 확인한다

## 보류 (2026-10-01 "일단 두자")

- [ ] `config/` 폴더: `config.json`을 옮긴다(`paths.CONFIG_FILE` 한 줄과 문서). `ecosystem.config.cjs`도 옮길지는 미정. 봇이 켜진 동안 배포하면 옛 코드가 설정을 못 찾을 수 있으니 봇이 꺼져 있을 때 배포한다
- [ ] 가끔 쓰는 도구 `parse_all_history.py`, `rollback_season.py`를 `tools/`로 옮긴다

## 기타

- [ ] `.env`·`.env.example`의 `ARENA_GH_*` 주석을 "GitHub Pages 자동 배포"에서 "history_data.json 오프사이트 백업"으로 고친다
