<!-- 운영·개발 환경을 모두 맥미니로 옮기는 배포 계획 -->
# 맥미니 운영·개발 이전 계획

체크리스트는 [checklist.md](checklist.md), 결정과 근거는 [context-notes.md](context-notes.md)에 있다.
상위 계획은 [activity-integration/plan.md](../activity-integration/plan.md) 12절이다.

## 1. 목표

사용자 결정(2026-09-29): 운영뿐 아니라 개발(dev 봇, 액티비티 개발 서버)도 맥미니에서 돌리고, Windows 로컬은 더 쓰지 않는다.

## 2. 맥미니 현황 (2026-09-29 조회)

- 저장소 `~/projects/lol_discord_bot`: origin/main의 이전 커밋 `d68de61`, 로컬 수정 없음. 합친 저장소(`web/` 포함)를 fast-forward로 받을 수 있다.
- 도구: uv 0.12.13, node 25.8.1, npm 11.19.1, pm2 7.0.4, cloudflared 2026.8.2.
- 데이터 원본 `data/`: history_data.json(236판), wins.json(total_rounds 86), 개발용 파일 두 개.
- `.env` 키: `DISCORD_TOKEN`, `DEV_MODE`, `ARENA_GH_TOKEN`, `ARENA_GH_REPO`. dev 봇 토큰과 액티비티용 Client ID·Secret이 없다.
- pm2: finance 하나만 돈다. 봇 프로세스 없음.
- 터널: `~/.cloudflared/config.yml`(brew services의 cloudflared)에 `fin.hansoljj.com → 127.0.0.1:8787` 하나만 있다.

## 3. 목표 구성

| pm2 앱 | 역할 | 주소 |
|---|---|---|
| `lol` | 운영 봇(`pick_mode: embed`). Client ID·Secret이 생기면 액티비티 서버도 켠다 | 127.0.0.1:8790 |
| `lol-web` | 정적 웹 서버. 새 대시보드, 액티비티 빌드(`/pick/`), `data/history_data.json`(캐시 금지), 약관 | 127.0.0.1:8791 |
| `lol-dev` | dev 봇(`DEV_MODE=true`, `ACTIVITY_PORT=8792`) | 127.0.0.1:8792 |
| `lol-dev-web` | 액티비티 Vite 개발 서버. `/pick-api`를 8792로 넘긴다 | 127.0.0.1:5173 |

정적 웹 서버의 경로 규칙:
- `/` → `web/activity/dist/dashboard.html`, `/assets/*`·`/fonts/*` → `dist/`
- `/pick/` → `dist/index.html`, `/pick/*` → `dist/*` (디스코드 URL 매핑 `/` → `arena.hansoljj.com/pick`)
- `/history_data.json` → `data/history_data.json`, `Cache-Control: no-cache`
- `/terms`, `/terms.html`, `/privacy`, `/privacy.html` → `web/*.html`
- `/legacy.html` → `web/index.html`(옛 대시보드, 비교용)

터널(finance 터널 config.yml의 404 규칙 앞):

| 호스트 | 대상 | 시점 |
|---|---|---|
| `lol-dev.hansoljj.com` | `http://127.0.0.1:5173` | dev 이전 때. 지금은 Windows의 대시보드 관리형 터널로 가는 DNS를 finance 터널로 옮긴다 |
| `arena.hansoljj.com` | `http://127.0.0.1:8791` | 사이트 전환 때. Cloudflare Pages의 사용자 지정 도메인을 먼저 뗀다 |
| `pick.hansoljj.com` | `http://127.0.0.1:8790` | 운영 앱 액티비티를 켤 때 |

## 4. 순서

1. (코디네이터, 무중단) 맥미니 저장소를 fast-forward로 받고 `uv sync`, `web/activity`에서 `npm ci`와 `npm run build`.
2. (워커) 저장소에 정적 웹 서버, pm2 설정(`ecosystem.config.cjs`), 배포 스크립트, 장애 알림 스크립트를 만들고, vite.config의 `/pick-api` 대상을 환경변수로 바꿀 수 있게 한다.
3. (사용자) 맥미니 `.env`에 dev 봇 토큰과 dev 앱 Client ID·Secret을 넣는다. 코디네이터는 비밀값을 읽거나 옮기지 않는다.
4. (코디네이터) pm2로 `lol`, `lol-web`, `lol-dev`, `lol-dev-web`을 띄우고 `pm2 save`. 로컬 주소로 각각 확인한다.
5. (사용자 시간 확인 후) 터널 설정에 `lol-dev`를 넣고 DNS를 옮긴 뒤 cloudflared를 재시작한다. finance가 몇 초 끊긴다.
6. Windows의 dev 봇과 Vite를 끄고, 디스코드에서 dev 액티비티가 맥미니로 동작하는지 확인한다.
7. (사용자 결정 후) arena.hansoljj.com을 Pages에서 맥미니로 옮긴다.
8. 재부팅 뒤 pm2 자동 기동으로 네 앱과 finance가 돌아오는지 확인한다.

## 5. 하지 않는 것

- 비밀값을 읽거나 출력하거나 다른 곳으로 복사하지 않는다.
- 사용자 확인 없이 cloudflared를 재시작하거나 DNS를 바꾸지 않는다.
- cloudflared를 업그레이드하거나 서비스 설치 방식을 바꾸지 않는다.
- 데이터 원본(`data/`)을 덮어쓰지 않는다.
