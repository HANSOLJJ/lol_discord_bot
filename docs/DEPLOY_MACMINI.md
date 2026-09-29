<!-- 맥미니 환경 배포 및 운영 가이드 -->
# 맥미니 배포 및 운영 가이드

맥미니(macOS arm64) 환경에서 롤 투기장 디스코드 봇, 정적 웹 서버, 개발용 액티비티 및 Cloudflare 터널을 pm2로 운영하는 절차를 설명합니다.

## 1. 서비스 주소 및 포트 구성

| 외부 도메인 / 경로 | 대상 로컬 주소 | 설명 |
|---|---|---|
| `lol.hansoljj.com/pick-api` | `http://127.0.0.1:8790` | 운영 봇 액티비티 API 및 웹소켓 |
| `lol.hansoljj.com` (기타 경로) | `http://127.0.0.1:8791` | 정적 웹 서버 (액티비티 `index.html` 및 자산 서빙) |
| `arena.hansoljj.com` | `http://127.0.0.1:8791` | 정적 웹 서버 (전적 대시보드 `dashboard.html` 및 자산 서빙) |
| `lol-dev.hansoljj.com` | `http://127.0.0.1:5173` | 개발 액티비티 Vite 개발 서버 |

## 2. pm2 프로세스 목록

`ecosystem.config.cjs`에 정의된 6개 앱입니다.

- `lol`: 운영 디스코드 봇 (`DEV_MODE=false`)
- `lol-web`: aiohttp 정적 웹 서버 (`WEB_PORT=8791`)
- `lol-dev`: 개발 디스코드 봇 (`DEV_MODE=true`, `ACTIVITY_PORT=8792`)
- `lol-dev-web`: 액티비티 Vite 개발 서버 (포트 5173, 프록시 대상 8792)
- `lol-health`: 5분 간격 헬스체크 및 장애/복구 알림 스크립트
- `lol-tunnel`: Cloudflare 터널 프로세스 (`/Users/hansol/.cloudflared/lol.yml`)

## 3. 최초 설치 및 기동

맥미니의 저장소 루트(`/Users/hansol/projects/lol_discord_bot`)에서 실행합니다.

```bash
# pm2로 전체 프로세스 기동
pm2 start ecosystem.config.cjs

# 서버 재부팅 시 자동 기동되도록 상태 저장
pm2 save
```

## 4. 코드 업데이트 및 배포

배포 스크립트를 사용하여 Git pull, 의존성 동기화, 프론트엔드 빌드, pm2 재시작을 한 번에 진행합니다.

```bash
# 운영 프로세스(lol, lol-web)만 배포 및 재시작
./scripts/deploy.sh

# 개발 프로세스(lol-dev, lol-dev-web)까지 함께 재시작할 경우
./scripts/deploy.sh --dev
```

## 5. 로그 확인 및 프로세스 관리

```bash
# 특정 앱 로그 실시간 확인
pm2 logs lol
pm2 logs lol-web
pm2 logs lol-health
pm2 logs lol-tunnel

# 전체 상태 확인
pm2 status
```

## 6. 환경변수(.env) 설정

저장소 루트의 `.env` 파일에 아래 키들을 설정합니다. 비밀값은 저장소나 외부에 공유하지 않습니다.

- `DISCORD_TOKEN`: 운영 디스코드 봇 토큰.
- `DISCORD_TOKEN_DEV`: 개발 디스코드 봇 토큰.
- `DISCORD_CLIENT_ID`: 운영 액티비티 디스코드 Client ID.
- `DISCORD_CLIENT_ID_DEV`: 개발 액티비티 디스코드 Client ID.
- `DISCORD_CLIENT_SECRET`: 운영 액티비티 디스코드 Client Secret.
- `DISCORD_CLIENT_SECRET_DEV`: 개발 액티비티 디스코드 Client Secret.
- `ARENA_GH_TOKEN`: 경기 결과 백업용 GitHub 토큰.
- `ARENA_GH_REPO`: 경기 결과 백업 대상 GitHub 저장소.
- `ALERT_WEBHOOK_URL`: 서비스 장애 및 복구 알림을 수신할 디스코드 웹훅 URL.

> 주의: `.env`에 설정된 `DEV_MODE`는 pm2 구동 시 `ecosystem.config.cjs`에서 앱별로 명시 주입하므로 pm2 환경에서는 쓰이지 않습니다. pm2 없이 로컬 터미널에서 스크립트를 직접 실행하면 운영 봇으로 동작하므로 주의해야 합니다.
