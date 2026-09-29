<!-- 맥미니 이전 작업의 결정과 근거 기록 -->
# 맥미니 이전 결정 기록

## 2026-09-29 (코디네이터 기록)

- 사용자 결정: dev까지 맥미니에 모두 올리고 로컬(Windows)은 더 쓰지 않는다. 운영 봇이 올라갈 때까지 게임할 일은 없다.
- 운영 봇과 dev 봇을 같은 폴더에서 돌린다. 데이터 파일은 DEV_MODE에 따라 이미 나뉘어 있고(`*_dev.json`), 액티비티 포트만 `ACTIVITY_PORT`로 나눈다(운영 8790, dev 8792).
- dev 액티비티는 지금처럼 Vite 개발 서버로 띄운다. HMR과 `/pick-api` 프록시를 그대로 쓸 수 있어서이다. 운영은 빌드 결과를 정적 서버로 서빙한다.
- 빌드 설정에 `base`가 없어 자산 주소가 `/assets/...`이다. 디스코드는 액티비티의 `/`를 `arena.hansoljj.com/pick`으로 보내므로 브라우저의 `/assets/x`는 `arena.hansoljj.com/pick/assets/x`가 된다. 그래서 정적 서버가 `/`와 `/pick/` 양쪽에서 같은 `dist/`를 서빙하게 한다.
- `lol-dev.hansoljj.com`은 Windows에 설치한 대시보드 관리형 터널이 쓰고 있다. 맥미니에 같은 터널 커넥터를 서비스로 설치하면 기존 finance 터널의 launchd 항목과 이름이 겹칠 위험이 있어서, finance 터널(로컬 관리형 config.yml)에 호스트를 추가하고 DNS를 옮기는 방식을 택한다.
- 맥미니 `.env`에는 dev 봇 토큰과 액티비티 Client ID·Secret이 없다. 비밀값은 사용자가 직접 넣는다.
- cloudflared는 brew services가 아니라 LaunchAgent `com.cloudflare.cloudflared`(인자 `tunnel --config ~/.cloudflared/config.yml run`)로 돈다. 재시작은 `launchctl kickstart -k gui/$(id -u)/com.cloudflare.cloudflared`이다.
- 2026-09-29 사용자 승인으로 터널을 바꿨다. 설정 백업은 `~/.cloudflared/config.yml.bak-20260929-lol`이다. finance 재시작이 한 번만 되도록 `lol-dev`(5173), `arena`(8791), `pick`(8790) 규칙을 한꺼번에 넣었다. 규칙은 DNS가 이 터널을 가리킬 때만 쓰이므로 arena·pick은 아직 영향이 없다. `ingress validate` 통과, 재시작 뒤 finance는 1초 만에 302로 복귀했다.
- `cloudflared tunnel route dns --overwrite-dns <finance 터널 ID> lol-dev.hansoljj.com`으로 lol-dev의 CNAME을 Windows 대시보드 관리형 터널에서 finance 터널로 옮겼다. 맥미니에 개발 서버가 없는 동안 lol-dev는 502를 돌려준다. Windows dev 봇과 Vite는 같은 토큰으로 겹치지 않게 껐다.
- 사용자 질문으로 finance와 롤 터널을 분리했다. 한 터널에 두면 롤 주소를 바꿀 때마다 finance가 끊기고, 롤 설정 오류가 finance까지 멈출 수 있다. 롤 터널은 로컬 관리형(`cloudflared tunnel create lol`, 맥미니의 cert.pem 사용)으로 만들어 비밀값을 따로 다루지 않았고, finance의 launchd 항목과 겹치지 않게 pm2 앱(`lol-tunnel`)으로 띄웠다.
- Zero Trust의 "Migrate finance"는 누르지 않기로 했다. 되돌릴 수 없고, 지금 설정 파일 방식으로 문제없이 돈다.
- 사용자 결정: 운영 주소는 `lol.hansoljj.com` 하나. 처음 계획한 `pick.hansoljj.com`(API 전용)과 `arena.hansoljj.com/pick`(화면)은 쓰지 않는다. 같은 주소에서 브라우저는 대시보드, 디스코드는 액티비티를 보게 하려고 `frame_id` query로 구분한다. 개발자 포털 URL 매핑이 dev와 같은 모양(`/` → 호스트)이 된다.
- 사용자 결정: `arena.hansoljj.com`은 맥미니 웹 서버가 `lol.hansoljj.com`으로 301 리다이렉트한다(방법 1). Cloudflare 리다이렉트 규칙(방법 2)은 설정이 저장소 밖에 남아서 택하지 않았다.
- 주의: 백엔드가 없을 때 cloudflared가 원본 연결 실패를 오류 로그에 남기면서 요청 주소를 통째로 적는다. WebSocket 주소의 `session` query가 `~/.pm2/logs/lol-tunnel-error.log`에 남은 것을 확인했다(당시 세션은 dev 봇 종료로 이미 무효). 백엔드를 띄우면 이 오류 기록은 생기지 않는다.
