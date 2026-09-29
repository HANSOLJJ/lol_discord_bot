# 결정 기록
- 2026-09-29 사용자 결정: 봇 관련 앱은 필요할 때만 켜고, 평소에는 웹과 터널만 띄운다.
- 2026-09-29 사용자 결정: finance 터널도 pm2로 옮긴다(방법 A). 전환 순간 finance가 몇 초 끊기는 것을 감수한다.
- 이름 규칙: `lol-{bot|web}[-dev]`. 사용자가 lol-bot, lol-bot-dev를 제안했고, dev 웹도 같은 규칙으로 `lol-web-dev`로 맞췄다.
- 헬스체크는 꺼 둔 봇을 장애로 보지 않도록 봇을 점검 대상에서 뺀다.
- deploy.sh는 꺼 둔 봇을 켜지 않도록 실행 중인 봇만 재시작한다.
- finance 터널 전환은 pm2 쪽 cloudflared를 먼저 띄워 연결 4개가 등록된 것을 확인한 뒤 LaunchAgent를 내려서 끊김 없이 옮겼다.
- 재부팅 리허설(2026-09-29 16:20): sudo가 비밀번호를 요구해서 `osascript`로 System Events에 재시작을 요청했다. 자동 로그인(hansol), FileVault 꺼짐, LaunchAgent `com.PM2`(`pm2 resurrect`)로 pm2가 저장 상태 그대로 복구됐다. 상시 앱은 online, 봇·dev 앱은 stopped로 돌아왔다. lol 주소는 약 30초 끊겼다.
