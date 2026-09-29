<!-- 맥미니 환경 배포 및 운영 가이드 -->
# 맥미니 배포 및 운영 가이드

맥미니(macOS arm64) 환경에서 롤 투기장 디스코드 봇, 정적 웹 서버, 개발용 액티비티 및 Cloudflare 터널을 pm2로 운영하는 절차를 설명합니다.

## 1. 서비스 주소 및 인프라 구성

Cloudflare 터널, DNS 설정, 캐시 규칙, 디스코드 개발자 포털 설정 등 세부 인프라 구성은 [인프라 가이드(INFRA.md)](INFRA.md)를 참조합니다.

| 외부 도메인 / 경로 | 대상 로컬 주소 | 설명 |
|---|---|---|
| `lol.hansoljj.com/pick-api` | `http://127.0.0.1:8790` | 운영 봇 액티비티 API 및 WebSocket (pm2 `lol-bot`) |
| `lol.hansoljj.com` (기타 경로) | `http://127.0.0.1:8791` | aiohttp 정적 웹 서버 (pm2 `lol-web`). `/`는 액티비티면 픽 화면, 브라우저면 대시보드 |
| `arena.hansoljj.com` | `http://127.0.0.1:8791` | 옛 주소. 웹 서버가 `https://lol.hansoljj.com`으로 301 영구 리다이렉트 |
| `lol-dev.hansoljj.com` | `http://127.0.0.1:5173` | 개발 액티비티 Vite 개발 서버 (pm2 `lol-web-dev`) |
| `fin.hansoljj.com` | `finance` 터널 | 롤과 무관한 다른 서비스. 맥미니 작업 시 건드리지 않음 |


## 2. pm2 프로세스 목록

`ecosystem.config.cjs`에 정의된 6개 앱입니다. 이름 규칙은 `lol-{bot|web}[-dev]`입니다(2026-09-29 `lol` → `lol-bot`, `lol-dev` → `lol-bot-dev`, `lol-dev-web` → `lol-web-dev`로 변경).

- `lol-bot`: 운영 디스코드 봇 (`pick_mode: activity`, `DEV_MODE=false`). 운영 환경에 `DISCORD_CLIENT_ID`와 `DISCORD_CLIENT_SECRET`이 주입되면 포트 8790에서 `/pick-api` 액티비티 API 서버도 함께 시작합니다.
- `lol-web`: aiohttp 정적 웹 서버 (`WEB_PORT=8791`). 프론트엔드 빌드 결과물(`web/activity/dist/`)을 서빙하고 구 도메인 리다이렉트를 처리합니다.
- `lol-bot-dev`: 개발 디스코드 봇 (`DEV_MODE=true`, `ACTIVITY_PORT=8792`, `dev_pick_mode: activity`, `dev_auto_start_seconds: 0`).
- `lol-web-dev`: 액티비티 Vite 개발 서버 (포트 5173, `ACTIVITY_PROXY_TARGET=http://127.0.0.1:8792`).
- `lol-health`: 5분 간격 cron(`cron_restart: '*/5 * * * *'`)으로 실행되는 헬스체크 스크립트. `lol-web`과 `lol-tunnel` 상태를 점검하고 장애 시 디스코드 웹훅으로 알립니다.
- `lol-tunnel`: Cloudflare 롤 전용 터널 데몬 (`cloudflared tunnel --config ~/.cloudflared/lol.yml run`).

### 평소 켜 두는 앱과 필요할 때만 켜는 앱

| 구분 | 앱 | 비고 |
|---|---|---|
| 항상 켜 둠 | `lol-web`, `lol-tunnel`, `lol-health` | 대시보드(`lol.hansoljj.com`)는 봇 없이 `lol-web`이 `data/history_data.json`을 직접 읽어 보여 줍니다. |
| 필요할 때만 | `lol-bot` | 게임할 때 `pm2 start lol-bot`, 끝나면 `pm2 stop lol-bot`. 꺼져 있으면 슬래시 명령과 픽 화면 서버(`/pick-api`)가 작동하지 않습니다. |
| 필요할 때만 | `lol-bot-dev`, `lol-web-dev` | TEST2 테스트할 때만 켭니다. |

- `pm2 save`를 한 시점의 상태(켜짐·꺼짐)가 재부팅 뒤에 그대로 복구됩니다. 봇을 켜 둔 채 `pm2 save`를 하지 않도록 주의합니다.
- 재부팅 시 pm2 자체는 LaunchAgent `pm2.hansol.plist`가 띄웁니다.
- 같은 맥미니의 `finance` 서비스도 pm2에서 돕니다. 웹 서버는 `finance`, 터널은 `finance-tunnel`(`cloudflared tunnel --config ~/.cloudflared/config.yml run`)입니다. 롤 저장소의 `ecosystem.config.cjs`에는 들어 있지 않습니다.

## 3. 최초 설치 및 기동

맥미니의 저장소 루트에서 아래 순서로 실행합니다.

```bash
# 1. 파이썬 의존성 동기화
uv sync

# 2. 웹 액티비티 의존성 설치 및 빌드
cd web/activity
npm ci
npm run build
cd ../..

# 3. pm2로 전체 프로세스 기동 후, 필요할 때만 쓰는 앱은 끈다
pm2 start ecosystem.config.cjs
pm2 stop lol-bot lol-bot-dev lol-web-dev

# 4. 서버 재부팅 시 자동 기동되도록 상태 저장
pm2 save
```

## 4. 코드 업데이트 및 배포

배포 스크립트(`scripts/deploy.sh`)를 사용하여 코드 풀, 의존성 동기화, 빌드, pm2 재시작을 진행합니다.

```bash
# 배포 후 lol-web 재시작, lol-bot은 켜져 있을 때만 재시작
bash scripts/deploy.sh

# dev 앱(lol-bot-dev, lol-web-dev)도 켜져 있으면 함께 재시작
bash scripts/deploy.sh --dev
```

### 배포 시 유의사항
- **프론트엔드 단독 변경**: 웹 화면만 변경된 경우 `cd web/activity && npm run build`만 실행하면 충분합니다. `lol-web`이 `dist/` 폴더를 직접 서빙하므로 pm2 재시작 없이 즉시 반영됩니다.
- **dev 배포 후 액티비티 재오픈**: 개발 환경 배포 뒤에는 디스코드에 열려 있던 액티비티 창을 완전히 닫았다가 다시 열어야 최신 자산이 로드됩니다.

## 5. 로그 확인 및 프로세스 관리

```bash
# 전체 프로세스 동작 상태 확인
pm2 status

# 프로세스별 실시간 로그 확인
pm2 logs lol-bot
pm2 logs lol-web
pm2 logs lol-bot-dev
pm2 logs lol-web-dev
pm2 logs lol-health
pm2 logs lol-tunnel

# 특정 프로세스 단독 재시작
pm2 restart lol-bot
pm2 restart lol-web
```

## 6. 환경변수(.env) 설정

저장소 루트의 `.env` 파일에 아래 키들을 설정합니다. 비밀값은 저장소나 외부에 절대 공유하지 않습니다.

- `DISCORD_TOKEN`: 운영 디스코드 봇 토큰.
- `DISCORD_TOKEN_DEV`: 개발 디스코드 봇 토큰.
- `DISCORD_CLIENT_ID`: 운영 액티비티 디스코드 Client ID (운영 봇 액티비티 API 활성화용).
- `DISCORD_CLIENT_SECRET`: 운영 액티비티 디스코드 Client Secret.
- `DISCORD_CLIENT_ID_DEV`: 개발 액티비티 디스코드 Client ID.
- `DISCORD_CLIENT_SECRET_DEV`: 개발 액티비티 디스코드 Client Secret.
- `ARENA_GH_TOKEN`: 경기 결과 오프사이트 백업용 GitHub 토큰 (Fine-grained PAT, contents write 권한).
- `ARENA_GH_REPO`: 백업 대상 GitHub 저장소 (`HANSOLJJ/lol_arena`).
- `ALERT_WEBHOOK_URL`: 서비스 장애 및 복구 알림을 수신할 디스코드 웹훅 URL (미설정 시 로그 파일에만 기록).

> **경고**: `.env`의 `DEV_MODE`는 삭제되었습니다. pm2가 `ecosystem.config.cjs`를 통해 앱별로 `DEV_MODE` 환경변수를 주입합니다. pm2 없이 로컬 터미널에서 `uv run python got_champe.py`로 직접 띄우면 기본값이 운영 봇(`DEV_MODE=false`)으로 동작하여 pm2에서 실행 중인 운영 봇과 중복 로그인 충돌을 일으키므로 절대로 직접 실행하지 않습니다.

## 7. 데이터 영속성 및 오프사이트 백업

- **로컬 원본**: 경기 결과와 누적 전적의 마스터 데이터는 맥미니 로컬 파일인 `data/history_data.json` 및 `data/wins.json`에 저장됩니다 (git 추적 제외).
- **GitHub 오프사이트 백업**: 봇이 매 경기(`/승리` 확정 시)마다 GitHub API를 통해 `HANSOLJJ/lol_arena` 저장소로 `history_data.json`을 자동 커밋하여 원격 백업을 유지합니다 (`ARENA_GH_TOKEN`, `ARENA_GH_REPO`). 백업이 실패하더라도 로컬 봇 동작에는 영향을 주지 않으며 다음 판 저장 시 자동으로 만회됩니다.

