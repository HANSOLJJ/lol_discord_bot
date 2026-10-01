# web/activity: 픽 화면(디스코드 액티비티)과 전적 대시보드

React + TypeScript + Vite 프로젝트 하나에서 두 화면을 빌드한다. 빌드 결과 `dist/`는 봇 저장소 루트의 `web_server.py`(pm2 `lol-web`)가 직접 서빙한다.
각 소스 파일의 역할은 파일 첫 줄 주석에도 적혀 있다. 이 문서는 그 파일들이 어떻게 이어지는지를 정리한다.

## 1. 진입점 두 개

| 화면 | HTML | 렌더 시작 | 최상위 컴포넌트 |
|---|---|---|---|
| 픽 화면 (액티비티) | `index.html` | `src/main.tsx` | `src/App.tsx` → `ActivityScreen` 또는 `BrowserNotice` |
| 전적 대시보드 | `dashboard.html` | `src/dashboard/main.tsx` | `src/dashboard/DashboardApp.tsx` |

`vite.config.ts`의 `build.rollupOptions.input`에 두 HTML이 함께 등록되어 있어서 `npm run build` 한 번에 둘 다 나온다.

운영에서 어느 화면을 줄지는 `web_server.py`가 정한다.

- `/`: 쿼리에 `frame_id`가 있으면 `dist/index.html`(픽 화면), 없으면 `dist/dashboard.html`(대시보드). 디스코드는 액티비티를 열 때 항상 `frame_id`를 붙인다
- `/dashboard.html`: 대시보드
- `/pick/`: 픽 화면

## 2. 픽 화면의 흐름

```text
src/main.tsx            React 루트를 만들고 index.css를 불러온 뒤 <App />을 그린다
  └ src/App.tsx         어디서 열렸는지 보고 화면을 고른다
       ├ 개발 서버 + ?preview=<키>  → ActivityScreen (미리보기, 서버 연결 없음)
       ├ 디스코드 안 (frame_id 있음) → ActivityScreen
       └ 일반 브라우저              → BrowserNotice ("디스코드에서 열어 주세요")

ActivityScreen
  └ hooks/useActivity.ts         인증과 서버 연결을 한 번만 만들고 React 상태로 내려 준다
       ├ lib/discord.ts          SDK ready → authorize → POST /pick-api/token → authenticate
       ├ lib/connection.ts       WebSocket /pick-api/ws, 재접속(0.5·1·2·5초), 4401이면 재인증
       │    ├ lib/protocol.ts    받은 JSON을 규격대로 검증하고 타입을 붙인다
       │    └ lib/clock.ts       ping 5회로 서버 시계 기준점을 잡고 30초마다 다시 잰다
       └ 화면 컴포넌트들 ← lib/view-logic.ts (차례·잠금·색상 같은 순수 계산)
                       ← hooks/useRemainingSeconds.ts (남은 초를 requestAnimationFrame으로 계산)
```

카운트다운 숫자는 서버가 보낸 마감 시각과 `lib/clock.ts`의 기준점으로 각 화면이 직접 센다. 숫자마다 네트워크를 타지 않는다.
`lib/clock.ts`와 `lib/connection.ts`는 React에 의존하지 않아서 `node --test`로 바로 테스트한다.

## 3. 대시보드의 흐름

```text
src/dashboard/main.tsx   React 루트를 만들고 <DashboardApp />을 그린다
  └ DashboardApp.tsx      탭·필터 상태를 갖고 아래 모듈을 조합한다
       ├ hooks/useHistoryData.ts       /history_data.json 로드, 20초마다 HEAD로 바뀌었는지 확인
       │    └ lib/validation.ts        데이터 구조 검증
       ├ lib/session.ts                6시간 공백 기준 세션 분할, 기간 선택지
       ├ lib/filter.ts                 기간·같은 팀·챔피언 검색·정렬
       ├ lib/stats.ts                  통계 탭 계산 (순수 함수)
       └ hooks/useChampionPortraits.ts → lib/ddragon.ts (Data Dragon 초상화 주소)
```

## 4. 파일 지도 (`src/`)

### 공통·픽 화면

| 파일 | 역할 |
|---|---|
| `main.tsx` | 픽 화면 React 렌더링 진입점 |
| `App.tsx` | 실행 위치(디스코드 안/밖)와 개발 미리보기에 따라 화면을 고르는 최상위 컴포넌트 |
| `index.css` | 픽 화면 전역 스타일 |
| `vite-env.d.ts` | Vite 환경 변수 타입 선언 |

`components/` (스타일은 같은 이름의 `.module.css`)

| 파일 | 역할 |
|---|---|
| `ActivityScreen.tsx` | 픽 화면 본체. 반응형 3가지 뷰, phase별 화면, 통신 연동 |
| `BrowserNotice.tsx` | 디스코드 밖에서 열었을 때의 실행 안내 |
| `Header.tsx` | 상단 헤더. 연결 상태, 라운드·시즌, 사용자 이름 |
| `TeamRoster.tsx` | TEAM 1·TEAM 2 명단과 현재 차례 강조 |
| `PickOrderList.tsx` | 픽 순서 목록 (1~6순위, 이름, 승수, 선택 상태, 초상화) |
| `ChampionGrid.tsx` | 챔피언 후보 4x2 그리드 (초상화, 자물쇠, 픽 클릭) |
| `TurnCountdown.tsx` | 카운트다운 숫자와 진행 막대. 남은 초가 바뀔 때의 다시 그리기가 화면 전체로 번지지 않게 따로 그린다 |
| `PhaseActions.tsx` | 대기(`none`), 승리 팀 입력(`awaiting_result`), 결과·번복(`completed`) 버튼 |
| `PipView.tsx` | 작은 창(PiP) 요약. 카운트다운, 차례 안내, 진행 원 6개 |
| `Toast.tsx` | 하단 알림 |

`hooks/`

| 파일 | 역할 |
|---|---|
| `useActivity.ts` | 인증과 서버 연결을 한 번만 만들고 상태·요청 함수(pick, start, pause 등)를 제공 |
| `useRemainingSeconds.ts` | 남은 초를 rAF로 계산하고, 표시할 초가 바뀔 때만 상태를 갱신 |
| `useCountdownMaxSeconds.ts` | 진행 막대의 전체 길이를 카운트다운마다 처음 본 남은 초로 맞춤 |
| `useLayoutMode.ts` | 화면 크기로 레이아웃 모드(`mobile`, `pc`, `pip`) 판정 |

`lib/`

| 파일 | 역할 |
|---|---|
| `discord.ts` | 디스코드 실행 여부 판별(`frame_id`), SDK 인증과 `/pick-api/token` 세션 교환 |
| `connection.ts` | WebSocket 연결·재접속·요청 응답 대응·상태 적용·시계 측정 |
| `protocol.ts` | 서버와 주고받는 메시지 타입과 수신 JSON 런타임 검증 |
| `clock.ts` | 서버 시각 기준점, 보정된 서버 시각, 남은 초, RTT 통계 |
| `view-logic.ts` | 차례·잠금·색상·버튼 활성화 등 순수 뷰 계산 |
| `preview.ts` | 개발 미리보기용 상태 생성과 `?preview=` 파싱 |

`test/`

| 파일 | 역할 |
|---|---|
| `fixtures.ts` | 규격 예시 메시지 생성기. 테스트뿐 아니라 개발 미리보기(`preview.ts`, `useActivity.ts`)도 쓴다 |
| `fakes.ts` | `connection` 테스트용 가짜 WebSocket·타이머·시계·visibility |

`*.test.ts`는 옆에 있는 같은 이름의 모듈을 테스트한다.

### 대시보드 (`dashboard/`)

| 파일 | 역할 |
|---|---|
| `main.tsx` | 대시보드 React 렌더링 진입점 |
| `DashboardApp.tsx` | 6개 탭(대전 기록 + 통계 5개)을 총괄하는 최상위 컴포넌트 |
| `dashboard.css` | 대시보드 전역 스타일 |
| `components/DashboardHeader.tsx` | 타이틀과 마지막 갱신 시각 |
| `components/DashboardTabs.tsx` | 탭 내비게이션 (대전 기록, 개인, 2인 시너지, 3인 시너지, 챔피언, 3:3 매치업) |
| `components/DashboardFilters.tsx` | 대전 기록 탭 필터. 챔피언 검색, 정렬, 같은 팀 플레이어 칩(최대 3개), 승패 요약 |
| `components/StatsFilters.tsx` | 통계 탭 필터. 기간, 인원 선택, 최소 판수 |
| `components/GameList.tsx` | 대전 기록 카드 목록, 30개씩 더 보기 |
| `components/GameCard.tsx` | 경기 한 판 카드 (팀 대진, 승리 강조, 번복 배지) |
| `components/PlayerStatsView.tsx` | 개인 탭. 개요 표, 모바일 카드, 챔피언별 드릴다운 |
| `components/ComboStatsView.tsx` | 2인·3인 시너지 탭 |
| `components/ChampStatsView.tsx` | 챔피언 탭 |
| `components/MatchupStatsView.tsx` | 3:3 매치업 탭 |
| `components/ChampionPortrait.tsx` | 원형 초상화, 실패 시 첫 글자로 대체 |
| `components/StatsTable.module.css` | 통계 탭 4개(개인·시너지·챔피언·매치업)가 함께 쓰는 표 스타일 |
| `hooks/useHistoryData.ts` | 전적 로드와 20초 주기 변경 감지 |
| `hooks/useChampionPortraits.ts` | 챔피언 초상화 주소 매핑 로드 |
| `lib/types.ts` | 대시보드 데이터 타입 |
| `lib/validation.ts` | 전적 원본 구조·무결성 검증 |
| `lib/session.ts` | 세션 분할과 라벨 |
| `lib/filter.ts` | 경기 목록 필터·정렬 |
| `lib/stats.ts` | 통계 계산과 정렬 |
| `lib/corrected.ts` | 번복 정보 표기와 요약 |
| `lib/ddragon.ts` | Data Dragon 초상화 주소와 대체 표기 |
| `lib/time.ts` | UTC → KST 변환과 포맷 |
| `lib/legacy-compare.test.ts` | 옛 대시보드 계산 결과와 `stats.ts`가 같은지 전 조건 비교 |

## 5. 개발 명령

`web/activity`에서 실행한다.

| 명령 | 하는 일 |
|---|---|
| `npm ci` | 의존성 설치 (`package-lock.json` 그대로) |
| `npm run dev` | Vite 개발 서버 `127.0.0.1:5173` (pm2 `lol-web-dev`, 주소 `lol-dev.hansoljj.com`) |
| `npm run build` | `tsc -b`로 타입 검사 후 `dist/` 생성 |
| `npm test` | `node --test "src/**/*.test.ts"` |
| `npm run lint` | oxlint |

개발 서버는 아래 경로를 프록시한다(`vite.config.ts`).

| 경로 | 대상 |
|---|---|
| `/pick-api` (HTTP·WebSocket) | `ACTIVITY_PROXY_TARGET`, 없으면 `http://127.0.0.1:8790`. pm2 `lol-web-dev`는 dev 봇 `8792`를 넣는다 |
| `/history_data.json` | `https://lol.hansoljj.com` (운영 데이터로 대시보드 개발) |
| `/ddragon` | `https://ddragon.leagueoflegends.com` |

### 개발 미리보기

개발 서버에서만 `?preview=<키>`를 붙이면 서버 연결 없이 고정 상태로 픽 화면을 그린다. 운영 빌드에서는 무시된다.
예: `http://127.0.0.1:5173/?preview=picking`

키: `none`, `starting`, `starting_countdown`, `starting_paused`, `advantage_ban`, `advantage_force`, `advantage_waiting`,
`picking`, `picking_other`, `picking_warning`, `picking_paused`, `picking_banned`, `picking_forced`, `picking_forced_last`,
`awaiting_result`, `completed`, `completed_reversed`

## 6. 설정·자산 파일

| 파일 | 내용 |
|---|---|
| `.env.development` | `VITE_DISCORD_CLIENT_ID` = dev 앱 client id (공개값이라 커밋한다) |
| `.env.production` | `VITE_DISCORD_CLIENT_ID` = 운영 앱 client id |
| `vite.config.ts` | 개발 서버 주소·프록시·HMR, 진입점 두 개, SDK 사전 최적화 |
| `tsconfig*.json` | 앱(`app`)·빌드 도구(`node`)·테스트(`test`)용 타입 설정 |
| `.oxlintrc.json` | lint 규칙 |
| `public/favicon.svg` | 파비콘 |
| `public/fonts/` | Barlow Condensed 600·700 (라이선스 `OFL.txt`) |

`dist/`와 `node_modules/`는 git에 넣지 않는다.

## 7. 관련 문서

- [액티비티 통신 규격](../../docs/ACTIVITY_PROTOCOL.md): 메시지 형식을 바꿀 때는 이 문서를 먼저 고치고, `lib/protocol.ts`, `test/fixtures.ts`, 서버(`activity_server.py`, `game_core.py`)를 함께 맞춘다
- [맥미니 배포 가이드](../../docs/DEPLOY_MACMINI.md): pm2 앱, `scripts/deploy.sh` 빌드·배포
- [인프라 가이드](../../docs/INFRA.md): 터널, 디스코드 포털 URL Mapping
