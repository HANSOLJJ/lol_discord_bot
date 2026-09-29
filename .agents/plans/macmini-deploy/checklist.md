<!-- 맥미니 운영·개발 이전 체크리스트 -->
# 맥미니 운영·개발 이전 체크리스트

계획은 [plan.md](plan.md), 결정 기록은 [context-notes.md](context-notes.md)에 있다.

- [ ] 맥미니 저장소 fast-forward, `uv sync`, `web/activity`의 `npm ci`·`npm run build`
- [x] 정적 웹 서버·pm2 설정·배포 스크립트·장애 알림·vite 프록시 환경변수 (워커)
  - [x] `web/activity/vite.config.ts`: `/pick-api` 프록시 대상 환경변수 (`ACTIVITY_PROXY_TARGET`) 지원
  - [x] `web/activity/src/dashboard/lib/legacy-compare.test.ts`: `data/history_data.json` 경로 추가 및 부재 시 skip 처리
  - [x] `web_server.py`: aiohttp 정적 웹 서버 구현 (경로 규칙, Host 분기, 캐시 헤더, 보안 검증, 쿼리 제외 로깅)
  - [x] `tests/test_web_server.py`: 정적 웹 서버 단위 테스트 작성 및 검증
  - [x] `ecosystem.config.cjs`: pm2 프로세스 설정 (`lol`, `lol-web`, `lol-dev`, `lol-dev-web`, `lol-health`, `lol-tunnel`)
  - [x] `scripts/deploy.sh`: 맥미니 배포 스크립트 작성
  - [x] `scripts/healthcheck.py` 및 `tests/test_healthcheck.py`: 헬스체크 스크립트 및 테스트 작성
  - [x] `docs/DEPLOY_MACMINI.md`: 맥미니 배포 문서 작성 및 보강
- [ ] 워커 결과 검증 후 main 병합, push, 맥미니에 반영
- [ ] 사용자가 맥미니 `.env`에 `DISCORD_TOKEN_DEV`, `DISCORD_CLIENT_ID_DEV`, `DISCORD_CLIENT_SECRET_DEV` 추가
- [ ] pm2로 `lol`, `lol-web`, `lol-dev`, `lol-dev-web` 기동, `pm2 save`, 로컬 주소 확인
- [ ] 사용자 확인 후 터널에 `lol-dev.hansoljj.com` 추가, DNS 이전, cloudflared 재시작, finance 복귀 확인
- [ ] Windows dev 봇·Vite 종료, 디스코드에서 맥미니 dev 액티비티 확인
- [ ] 사용자 결정 후 arena.hansoljj.com을 Pages에서 맥미니(8791)로 전환
- [ ] 재부팅 뒤 자동 기동 확인
