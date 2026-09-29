<!-- 이 저장소에서 작업하는 에이전트가 가장 먼저 읽는 프로젝트 지침 -->
# AGENTS.md — 롤 투기장 디스코드 봇·웹

## 구성

- 한 저장소에 봇(루트 파이썬)과 웹(`web/`, React+TS+Vite 전적 대시보드·디스코드 액티비티)이 있다.
- 옛 `lol_arena` 저장소는 지원 중단이며 `history_data.json` 백업 대상으로만 남긴다. Archive하지 않는다. 읽기 전용이 되면 백업이 실패한다.
- 모든 서비스는 맥미니에서 pm2로 돈다. 평소에는 `lol-web`·`lol-tunnel`·`lol-health`만 켜고, `lol-bot`·`lol-bot-dev`·`lol-web-dev`는 필요할 때만 켠다. 배포는 `bash scripts/deploy.sh [--dev]`로 한다.
- 주소는 `lol.hansoljj.com`(운영), `lol-dev.hansoljj.com`(dev), `arena.hansoljj.com`(lol로 301)이다.

## 픽 방식과 게임 규칙

- 운영 픽은 액티비티(`config.json`의 `pick_mode: activity`, `channels: ["팀짜기"]`)이다.
- 친구들은 운영 앱 App Testers로 등록해서 쓴다. 사유와 등록 방법은 [인프라 가이드](docs/INFRA.md) 6-2절에 있다.
- `DEV_MODE`는 `.env`가 아니라 pm2가 앱마다 주입한다. pm2 없이 봇을 직접 실행하지 않는다.
- 게임 규칙은 6명 3:3, 승수 낮은 순 픽, 후보 8개, 20초 제한, 5·6위 어드밴티지다. 어드밴티지 규격은 [액티비티 통신 규격](docs/ACTIVITY_PROTOCOL.md) 14절에 있다.

## 전적 데이터

- 마스터는 `data/history_data.json`이다. 판 스키마는 `games[] = {round, round_orig, season, team1/2, winner, time, sources}`이며 봇이 직접 기록한 판의 `sources`는 `["BOT"]`이다.
- 시즌 번호의 단일 출처는 최상위 `current_season`이다. 새 시즌은 `/시즌시작`으로 연다. 승수를 백업 후 초기화하고 `current_season`을 1 올리고 라운드를 1부터 시작한다.
- `paths.py`가 모든 데이터·산출물 경로의 단일 출처다. 폴더 구조가 바뀌면 여기만 고친다.
- 시즌1은 150판이다. R119·R126은 중복 클릭으로 번호만 소모된 유령 라운드이며 R80만 실유실 후보다. 경위는 [과거 전적 복구 리포트](docs/PARSE_REPORT.md)에 있다.

## 문서

- 전체 안내는 [README.md](README.md)에, 터널·DNS·포털 설정은 [인프라 가이드](docs/INFRA.md)에, pm2 운영·배포·환경변수는 [맥미니 배포 가이드](docs/DEPLOY_MACMINI.md)에, 액티비티 통신 규격은 [액티비티 통신 규격](docs/ACTIVITY_PROTOCOL.md)에 있다.
- 문서만 고치는 작업에서는 코드, `config.json`, `.env`를 건드리지 않는다.
