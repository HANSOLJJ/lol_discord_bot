<!-- 맥미니 이전 작업의 결정과 근거 기록 -->
# 맥미니 이전 결정 기록

## 2026-09-29 (코디네이터 기록)

- 사용자 결정: dev까지 맥미니에 모두 올리고 로컬(Windows)은 더 쓰지 않는다. 운영 봇이 올라갈 때까지 게임할 일은 없다.
- 운영 봇과 dev 봇을 같은 폴더에서 돌린다. 데이터 파일은 DEV_MODE에 따라 이미 나뉘어 있고(`*_dev.json`), 액티비티 포트만 `ACTIVITY_PORT`로 나눈다(운영 8790, dev 8792).
- dev 액티비티는 지금처럼 Vite 개발 서버로 띄운다. HMR과 `/pick-api` 프록시를 그대로 쓸 수 있어서이다. 운영은 빌드 결과를 정적 서버로 서빙한다.
- 빌드 설정에 `base`가 없어 자산 주소가 `/assets/...`이다. 디스코드는 액티비티의 `/`를 `arena.hansoljj.com/pick`으로 보내므로 브라우저의 `/assets/x`는 `arena.hansoljj.com/pick/assets/x`가 된다. 그래서 정적 서버가 `/`와 `/pick/` 양쪽에서 같은 `dist/`를 서빙하게 한다.
- `lol-dev.hansoljj.com`은 Windows에 설치한 대시보드 관리형 터널이 쓰고 있다. 맥미니에 같은 터널 커넥터를 서비스로 설치하면 기존 finance 터널의 launchd 항목과 이름이 겹칠 위험이 있어서, finance 터널(로컬 관리형 config.yml)에 호스트를 추가하고 DNS를 옮기는 방식을 택한다.
- 맥미니 `.env`에는 dev 봇 토큰과 액티비티 Client ID·Secret이 없다. 비밀값은 사용자가 직접 넣는다.
- 코디네이터 추가 지시 (2026-09-29): 운영 액티비티 도메인 `lol.hansoljj.com` 추가. 터널이 `lol.hansoljj.com`의 `/pick-api`는 8790(운영 봇), 나머지는 8791(정적 서버)로 전달함. `web_server.py`는 `ACTIVITY_ROOT_HOSTS`(기본값 `lol.hansoljj.com`)에 일치하는 Host 요청 시 `/`를 `web/activity/dist/index.html`로, 그 외는 `dist/dashboard.html`로 서빙함.
- `ecosystem.config.cjs`에 `lol-tunnel`(cloudflared run) 앱 추가.
- `docs/DEPLOY_MACMINI.md`에 도메인/포트 매핑 표, `lol-tunnel`, `.env`의 `DEV_MODE` 미사용 주의사항 명시.
