# 맥락 및 결정 기록 (Context Notes)

- **2026-09-28: 프로토콜 v2 확정 내용 반영**
  - PROTOCOL_VERSION은 2로 상향하며, 2가 아닌 경우 입력을 차단하고 업데이트 필요 화면을 표시한다.
  - v1의 `demo_countdown`은 완전히 제거하고 `start`, `pick`, `result`, `reverse` 요청으로 대체한다.
  - `state`의 필수 객체 구조: `players`(6명), `pick_order`(6명 ID), `champions`(8개), `selections`(맵), `auto_assigned`(배열), `result`(completed에서만 채움), `ddragon_version`(Data Dragon 버전), `me`(권한 및 역할 정보).
  - 디자인 원본(Main.dc.html, Pc.dc.html, Pip.dc.html 등)의 HTML/CSS 명세를 분석하여 폰트('Barlow Condensed', 'IBM Plex Sans KR'), 컬러코드(TEAM 1: #5b8cff, TEAM 2: #ff6b5e, 노란색: #facc15, 경고 빨강: #ff3b3b), 그리드 및 갭을 일치시킨다.
  - 카운트다운 숫자의 매 초 변경이 전체 화면 리렌더를 유발하지 않도록 남은 시간/프로그레스 바 렌더링을 별도 서브 컴포넌트로 분리한다.
  - 개발 환경(`import.meta.env.DEV`)에서만 `?preview=<phase>` 쿼리 파라미터로 고정 state 렌더링을 지원하며, 운영 빌드에서는 포함되지 않도록 가드한다.
  - 반응형 분기: 화면 크기에 따라 3가지 모드(pip: <= 480x320, pc: >= 720px 너비, mobile: 기본 1열)를 `useLayoutMode` 훅으로 전환한다.
  - 카운트다운 렌더링 격리: 초 단위 카운트다운(`useRemainingSeconds`)을 `TurnCountdown` 내부에서만 구독하여, 초 변경 시 팀 구성/픽 순서/챔피언 그리드가 불필요하게 리렌더링되지 않도록 최적화했다.
  - 구버전 데모 전용 컴포넌트(`Countdown.tsx`, `Countdown.module.css`)는 v2 규격 반영에 따라 완전히 제거했다.
  - 액션 펜딩 및 토스트: `start`, `pick`, `result`, `reverse` 요청 처리 중 중복 클릭을 방지(`isPending`)하고, 실패 응답 message 및 성공 피드백을 토스트로 안내한다.
- **2026-09-28: 픽 화면 검토 반영 3건 및 이용약관·개인정보 처리방침 추가**
  - 미리보기 픽스처의 `me.id`가 `SAMPLE_PLAYERS[4]`(보링)로 잘못 지정되어 있던 문제를 `SAMPLE_PLAYERS[0]`(정한솔)로 바로잡는다. `SAMPLE_PICK_ORDER[4]`가 정한솔이므로 내 차례(`current_index = 4`) 및 "(나)" 뱃지 표시가 일치하게 된다.
  - 개발 서버(`vite.config.ts`) 프록시에 `'/ddragon'` -> `https://ddragon.leagueoflegends.com` (rewrite: prefix 제거)을 추가하여 초상화 이미지 404를 해결한다.
  - Discord Activity 내부 외부 폰트 요청 차단 문제를 해결하기 위해 `index.html`의 Google Fonts 링크를 제거하고, 숫자용 `Barlow Condensed` (600, 700) 라틴 woff2 파일과 `OFL.txt`를 `activity/public/fonts/`에 배치하고 `@font-face`로 불러온다. 본문 한국어는 시스템 글꼴 목록(`Apple SD Gothic Neo, Malgun Gothic, Noto Sans KR, sans-serif`)으로 전환한다.
  - Discord App Verification 제출을 위해 정적 HTML `terms.html`, `privacy.html`을 저장소 루트에 생성하며, 대시보드 테마와 동일한 색상 체계(#0f1115 배경)와 한국어+영어 병기 본문, 대시보드 및 상호 이동 링크를 제공한다.

