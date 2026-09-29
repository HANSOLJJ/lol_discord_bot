# 맥미니 pm2 구조 정리 (2026-09-29)

## 목표
- 항상 켜 둘 것은 웹과 터널뿐이다: `lol-web`, `lol-tunnel`, `finance`, `finance-tunnel`, `lol-health`.
- 봇과 dev 서버는 사용자가 원할 때만 켠다: `lol-bot`, `lol-bot-dev`, `lol-web-dev`.
- 이름을 구별하기 쉽게 바꾼다: `lol` → `lol-bot`, `lol-dev` → `lol-bot-dev`, `lol-dev-web` → `lol-web-dev`.
- finance 터널도 macOS LaunchAgent(`com.cloudflare.cloudflared`) 대신 pm2 `finance-tunnel`로 옮겨 lol과 같은 구조로 맞춘다.
- 재부팅 리허설로 자동 기동 상태를 검증한다.

## 코드 변경
- `ecosystem.config.cjs`: 앱 이름 변경.
- `scripts/deploy.sh`: 웹은 항상 재시작하고, 봇·dev 앱은 실행 중일 때만 재시작한다(꺼 둔 봇을 배포가 켜지 않게).
- `scripts/healthcheck.py`: 필수 앱을 `lol-web`, `lol-tunnel`로 바꾼다. 봇은 꺼져 있는 것이 정상이라 점검하지 않는다.
- 문서: README, DEPLOY_MACMINI, INFRA의 앱 이름과 운영 방식.

## 맥미니 작업
1. pull → 옛 이름 앱 삭제 → 새 이름 등록(봇·dev는 stopped) → `lol-health` 갱신.
2. `finance-tunnel` pm2 등록 → LaunchAgent 정지·비활성(plist는 이름 바꿔 백업) → 확인.
3. `brew services`의 cloudflared 상태 확인.
4. `pm2 save` → 재부팅 → 상태·외부 주소 확인.
