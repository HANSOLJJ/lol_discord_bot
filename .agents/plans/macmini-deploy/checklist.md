<!-- 맥미니 운영·개발 이전 체크리스트 -->
# 맥미니 운영·개발 이전 체크리스트

계획은 [plan.md](plan.md), 결정 기록은 [context-notes.md](context-notes.md)에 있다.

- [x] 맥미니 저장소 fast-forward(17fbea9), `uv sync`, 봇 테스트 97개, `web/activity`의 `npm ci`·`npm run build`
- [ ] 정적 웹 서버·pm2 설정·배포 스크립트·장애 알림·vite 프록시 환경변수 (agy 작업 중, worktree macmini-ops)
- [ ] 워커 결과 검증 후 main 병합, push, 맥미니에 반영
- [ ] 사용자가 맥미니 `.env`에 `DISCORD_TOKEN_DEV`, `DISCORD_CLIENT_ID_DEV`, `DISCORD_CLIENT_SECRET_DEV` 추가
- [ ] pm2로 `lol`, `lol-web`, `lol-dev`, `lol-dev-web` 기동, `pm2 save`, 로컬 주소 확인
- [x] 사용자 확인 후 터널에 `lol-dev`·`arena`·`pick` 규칙 추가, `lol-dev` DNS 이전, cloudflared 재시작, finance 1초 만에 복귀 (2026-09-29)
- [x] Windows dev 봇·Vite 종료
- [ ] 디스코드에서 맥미니 dev 액티비티 확인
- [ ] 사용자가 Cloudflare 대시보드의 Windows 대시보드 관리형 터널에서 `lol-dev` 공개 호스트 이름을 지우고, Windows cloudflared 서비스를 정리
- [ ] 사용자 결정 후 arena.hansoljj.com을 Pages에서 맥미니(8791)로 전환
- [ ] 재부팅 뒤 자동 기동 확인
