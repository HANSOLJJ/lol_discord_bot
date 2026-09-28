# 롤 액티비티·기능 통합 결정 기록

기준은 [plan.md](plan.md), 진행은 [checklist.md](checklist.md)이다. 결정과 근거를 날짜순으로 추가한다.

## 2026-09-28 문서 통합 범위

- 사용자는 docs와 ACTIVITY_DESIGN.md 개선 검토를 요청했고, 최종 목표를 두 Git의 기능 통합으로 밝혔다.
- 이후 특정 채널에서 카운트다운 자체가 보이지 않았던 경험을 강조했다. 따라서 plan의 첫 완료 기준을 카운트다운·연결 상태·복귀 동기화로 정했다.
- 사용자는 performance.now와 모바일 재동기화의 근거 기록 여부를 확인한 뒤, 설계까지 총정리한 플랜을 만들고 기존 handover/design 문서를 삭제해도 된다고 했다.
- 현재 실행 기준은 이 폴더의 3개 파일이다. docs의 액티비티 설계·인수인계와 기존 activity-pick/activity-integration-review의 내용을 이관한다. 삭제 전 출처는 Git 이력에 남는다.
- COUNTDOWN_ANALYSIS와 PARSE_REPORT는 원인·데이터 복구 근거이므로 보존한다. 루트 handover.md는 별개의 과거 Workers 이식 검토이며 이번 실행 기준이 아니다.
- 이번 작업은 문서 통합이다. 소스 구현·라이브러리 설치·원격 push·배포·실제 Git 병합은 수행하지 않는다.
- 통합 후 내부 문서 링크 9개, 코드 블록 짝, 핵심 주제 12개를 검사했다. 삭제한 문서를 가리키는 Markdown 링크는 없다. 코드 변경이 없어 실행 테스트 대신 문서 검증을 수행했다.

## 기존에 확정된 방향과 이유

- 액티비티를 택한 이유는 매 숫자가 Discord 메시지 편집을 거치는 지연과 채팅에 픽 화면이 밀려나는 문제이다. 마감 시각을 전달하고 화면에서 계산한다.
- 기존 봇 + aiohttp + 맥미니 + 터널을 선택했다. 게임 상태·pick_lock·타이머·기록을 한 프로세스에 유지해 별도 게임 서버와의 동기화를 줄인다.
- Worker+Durable Object 분업은 시작·embed·기록이 맥미니에 남고 상태가 분리된다. 전면 Workers 이식은 Python 로직과 presence 기반 참가자 선정까지 재설계해야 한다. VPS는 향후 대안이나 현재 운영 부담이 늘어난다.
- Cloudflare로 옮기면 항상 빨라진다고 단정할 근거는 없다. SDK의 참가자 정보만으로 게임 상태 동기화를 대신하지 않고 자체 서버를 사용한다.
- 초기 결정은 Vite + Embedded App SDK와 바닐라 JS였다. 프론트 구성은 아래 2026-09-28 추가 결정에서 React·TypeScript로 변경했다. 개발 앱 분리, 채널 현황판과 전환 스위치는 유지한다. 비상 개인 버튼은 필요가 확인되면 별도 검토한다.
- 개발 앱은 URL Mapping과 봇 토큰을 운영에서 분리한다. 운영 주소를 개발 터널로 바꾸거나 같은 토큰의 봇 두 개를 실행하는 문제를 피한다.
- pm2 자동 기동은 사용자 요구이다. 이전 조사에서 맥미니 재부팅 뒤 tmux 봇이 꺼진 채 발견됐다. 새 프로세스 등록 전 현재 실행 상태를 확인한다.

## 과거 관측과 현재 확인을 구분하기

- 9/15~16 측정 기록에는 맥미니→Discord API 왕복 약 0.3초, Discord 편집 지연 0.85~1.2초, 게이트웨이 RESUME·1006 끊김이 있었다. 이 수치로 이후 특정 사건의 원인을 확정하지 않는다.
- 이전 PC/KT 측정은 arena·fin이 SJC 엣지 약 150ms, discordsays.com이 ICN 약 8ms, 맥미니 터널이 icn01/icn06이었다. Discord 프록시를 통과한 실제 앱 왕복은 별도로 측정해야 한다.
- macOS 시계 오차 +0.08초는 당시 HTTP Date 대조 결과이다. 시계가 앞으로도 바뀌지 않는다는 보장이 아니다.
- 기존 조사 버전은 py-cord 2.8.1, aiohttp 3.14.3, 맥미니 node v25.8.1, cloudflared 2026.8.2, uv /opt/homebrew/bin/uv였다. Windows cloudflared는 당시 미설치였다. 설치·운영 전 재확인한다.
- 기존 기록상 arena.hansoljj.com은 Cloudflare Pages로 이관됐고 finance는 맥미니·pm2·Tunnel을 사용한다. README와 프로젝트 지침에는 더 오래된 GitHub Pages·arena.dcom.co.kr 설명이 남아 있다. 이번에는 실제 운영 설정에 접속하지 않았다.
- 이전 인수인계의 'tmux 운영 중'과 이후 조사에서 '재부팅 후 봇 꺼짐'은 관측 시점이 다르다. 플랜에서 현재 운영 사실로 확정하지 않는다.
- 검토 시작 시 bot의 game_recorder.py·parse_all_history.py·docs/PARSE_REPORT.md, arena의 index.html에 미커밋 변경이 있었다. AGENTS.md와 COUNTDOWN_ANALYSIS.md도 미추적 파일이었다. 이 작업으로 변경하거나 함께 커밋하지 않는다.
- 초기 로컬 추적 참조에서 bot은 3커밋 앞서고 arena는 45커밋 뒤였다. 이후 검토 메모 커밋 b1d5171이 추가됐다. fetch하지 않았으므로 실제 원격 최신 상태를 뜻하지 않는다.

## 코드 검토에서 보완한 내용

- 초기 챔피언 메시지 전송 실패 채널은 champion_messages에 등록되지 않아 후속 갱신도 받지 않는다. 일부 채널 성공만으로 게임이 계속된다.
- push_channel_embed가 편집 예외를 삼킨다. 채널별 장애 로그가 없으며 중간 상태 병합으로 숫자가 생략될 수도 있다. 사용자의 전체 미표시 사건과 연결 가능한 경로이지만 원인 확정은 아니다.
- 액티비티는 처음 상태를 받은 전경 화면에서 숫자별 네트워크 의존을 제거한다. 최초 연결 실패·앱 정지·픽 전송 실패까지 없애지는 않는다. 연결 상태를 표시하고 복귀 시 재동기화한다.
- ChampionButton.callback은 선택 즉시 current_pick_index를 증가시킨다. 정상 흐름에서 이전 선택을 재클릭해 취소할 수 없다. 따라서 '기존 취소 유지'를 지우고 즉시 확정을 기본안으로 명시했다. 별도 취소 기능은 미결이다.
- 기존 버튼 객체가 제한하던 후보 목록을 WS에서는 서버가 직접 확인해야 한다. 요청 ID와 턴 ID로 중복·이전 턴 조작을 막고, 상태 버전으로 역순 스냅샷을 구분한다.
- 락 밖 통신 원칙은 유지한다. gather는 전송을 병렬화하지만 느린 연결의 완료 대기·버퍼 누적을 해결하지 않는다. 소켓별 최신 상태와 전송 제한이 필요하다.
- 현재 승리 처리는 save_wins 성공 후 별도 record_game 실패가 가능하다. 결과 화면 통합 전 기준 기록과 부분 실패 복구를 정한다. SQLite 도입을 확정한 것은 아니다.
- 현재 대시보드는 GitHub에 배포된 history JSON을 최초 fetch 한 번으로 읽는다. 같은 Git에 넣는 것만으로 실시간 전적 갱신이 되지 않는다.
- 서버 재시작 시 세션과 게임 전역 상태가 함께 사라진다. 재인증과 진행 중 판 복구를 분리하고 초기에는 중단 안내·새 게임을 기준으로 한다.

## 카운트다운 시계 설계 근거

- Date.now는 시스템 시계와 사용자의 시각 변경에 영향을 받는다. 최초 5회 ping으로 서버 시각을 추정한 뒤 performance.now의 경과 시간으로 진행하도록 plan 5절에 계산식을 넣었다.
- 최소 RTT 샘플의 수신 시각에서 서버 시각을 s + RTT/2로 추정한다. 네트워크 비대칭·스케줄링 지연이 있어 오차 수치를 보장하지 않는다. RTT 게이트와 실제 상태 반영 지연을 함께 측정한다.
- performance.now의 절전 중 진행에는 플랫폼 차이가 있다. 전경 복귀·재접속마다 전체 상태와 시간을 다시 받고 입력을 재개한다. 30초 주기 측정만으로 모바일 복귀를 처리하지 않는다.
- 서버도 단조 시계로 내부 타이머·접수 판정을 유지하고 스냅샷의 서버 시각과 남은 시간을 함께 직렬화한다. 클라이언트와 서버의 벽시계 변경 영향을 각각 다룬다.
- 이전 표시 20초가 약 24초 이상이었던 것과 새 실제 20초의 차이를 전환 검증에 포함했다. 유예는 기존 2초에서 시작하며 추정 지연만으로 줄이지 않는다.

## 통합 목표와 남은 결정

- 사용자는 두 Git의 기능 통합을 목표로 했다. 픽·결과 입력·통계를 같은 액티비티에서 잇는 흐름은 구체화한 목표안이다. 세부 UI와 권한까지 이미 승인됐다고 해석하지 않는다.
- 봇 경로를 유지하고 web/을 추가하는 것이 최소 이동안이다. 기준 원격·공개 범위·이력 보존은 실제 통합 시 결정한다.
- 기존 '루트 전체 서빙·빌드 결과 커밋'은 현재 분리 저장소의 전환기 방식으로 한정한다. 최종 Pages 배포는 웹 출력 디렉터리만 대상으로 한다.
- GitHub JSON 업로드 제거는 봇 중단 시 공개 전적 조회의 가용성도 바꾼다. 읽기용 스냅샷 유지 여부와 캐시 갱신 시각 표시를 함께 결정한다.
- 테스트는 저장소 tests/에 보존한다. 과거 e:\tmp\countdown_probe.py, countdown_e2e.py, test_countdown_counter.py와 맥미니 /tmp의 측정 스크립트는 참고용이다. 존재와 재사용 가능성은 실행 전에 확인한다.
- 패키지 설치 승인과 finance 공유 터널 재시작 시각은 실제 작업 직전에 확인한다. 문서 작성 승인을 운영 변경 승인으로 확대하지 않는다.

## 공식 자료

이번 검토에서 확인한 자료이다. 구현 시 설치 버전과 실제 Discord 클라이언트에서 동작을 검증한다.

- [MDN performance.now](https://developer.mozilla.org/en-US/docs/Web/API/Performance/now). 단조 시계·Date.now 차이·절전 중 플랫폼 차이의 근거이다.
- [Discord Multiplayer Experience](https://github.com/discord/discord-api-docs/blob/main/developers/activities/development-guides/multiplayer-experience.mdx). instanceId 수명과 서버의 Activity Instance API 검증 근거이다.
- [Discord Networking](https://github.com/discord/discord-api-docs/blob/main/developers/activities/development-guides/networking.mdx). 클라이언트 데이터 신뢰 제한과 프록시·외부 자산 경로의 근거이다.
- [Discord Local Development](https://github.com/discord/discord-api-docs/blob/main/developers/activities/development-guides/local-development.mdx). 개발 앱·터널·URL Mapping과 테스트 계정 접근 검증의 근거이다.
- [Discord How Activities Work](https://github.com/discord/discord-api-docs/blob/main/developers/activities/how-activities-work.mdx). LAUNCH_ACTIVITY와 Entry Point 흐름의 근거이다.
- [Python asyncio.gather](https://docs.python.org/3/library/asyncio-task.html#asyncio.gather). 모든 작업 완료를 기다리는 동작의 근거이다.
- [Cloudflare Pages Build Configuration](https://developers.cloudflare.com/pages/configuration/build-configuration/). 빌드 루트와 공개 출력 디렉터리 분리의 근거이다.

## 2026-09-28 웹 서빙 방식 변경 확정

- 사용자가 Git 연동 Cloudflare Pages 배포를 더 이상 쓰지 않겠다고 결정했다. finance(fin.hansoljj.com)처럼 맥미니 자립 서버가 웹까지 직접 서빙하고 Cloudflare는 DNS와 Tunnel만 담당한다.
- 웹 정적 서빙은 봇의 aiohttp 서버(127.0.0.1:8790)가 맡는 것을 기본안으로 한다. 별도 Node 서버를 추가하지 않는다는 8절 결정과 일치한다.
- 배포 절차는 finance와 동일하게 맥미니에서 git pull → 필요 시 빌드 → pm2 restart이며 자동 배포는 없다.
- 공개 호스트 arena.hansoljj.com은 터널 ingress로 연결하고 Pages의 커스텀 도메인 연결을 해제한다. pick.hansoljj.com을 별도 호스트로 유지할지 arena 단일 호스트로 합칠지는 남은 결정으로 추가했다.
- Pages가 사라지면 봇 프로세스 중단 시 대시보드도 함께 내려간다. 15절의 '공개 전적의 장애 시 조회' 결정의 중요도가 높아졌고 pm2 자동 재시작이 1차 완화책이다.
- 이 결정에 맞춰 plan.md의 2절 표, 9-2, 12-2, 13 단계 2, 15절 표와 checklist 2절을 수정했다. 저장소 통합 목표 자체는 변경이 없다.

## 2026-09-28 정적 웹 서버 분리와 파일 기반 전적 확정

- 사용자가 "전적 대시보드는 봇과 무관하게 항상 동작하고, 봇은 게임 시작·진행에만 필요하게 하라"고 결정했다. 웹 서빙을 봇 aiohttp에 두려던 직전 기본안을 철회하고, 봇과 분리된 초소형 정적 웹 서버 프로세스(기본 127.0.0.1:8791, pm2 별도 앱)가 웹 빌드 출력과 history_data.json을 서빙한다.
- 정적 웹 서버는 요청받은 파일을 그대로 돌려주는 역할만 하며 게임 상태를 갖지 않는다. 8절의 별도 게임 서버 금지 결정과 충돌하지 않도록 문구를 구분했다.
- 공개 전적 조회는 파일 기반으로 확정했다. 봇이 로컬에 쓰는 history_data.json을 정적 서버가 같은 디스크에서 그대로 서빙하므로, 봇이 중단돼도 마지막 기록까지 조회가 유지되고 GitHub 스냅샷 백업은 불필요하다.
- game_recorder._save_history를 코드로 확인한 결과 이미 임시 파일 작성 후 os.replace 교체 방식의 원자적 저장이었다. 정적 서버가 같은 파일을 서빙해도 부분 파일이 노출되지 않으므로 추가 코드 변경은 필요 없다.
- 호스트 분리는 유지로 확정했다. arena.hansoljj.com → 8791(웹), pick.hansoljj.com → 8790(봇 API)의 프로세스별 매핑이 가장 단순하고, Discord URL Mapping은 변경이 없다.
- plan.md의 2절 표, 8절, 9-2, 10절 4·5항, 12-1, 12-2를 수정하고 15절 표에서 확정된 결정 두 건을 제거했다. checklist 2절도 갱신했다.
- 추가 확인: 봇 저장소 .gitignore가 wins·history 전적 파일을 모두 제외하고 있어 git에는 전적 데이터가 없다. 현재 유일한 외부 사본은 GitHub 업로드(lol_arena)이므로, 업로드를 폐기하면 맥미니 단일 디스크만 남는다. 대체 백업 결정을 15절 표에 추가했다.

## 2026-09-28 백업·운영 소개선 확정

- 전적 데이터 오프사이트 백업은 git 방식으로 확정했다. 기존 GitHub Contents API 업로드 코드를 그대로 백업 용도로 유지하고, 공개 조회만 정적 서버 기반으로 바뀐다. 코드 변경이 없고 판마다 전체 파일이 올라가 유실 범위가 최소라는 점이 근거다. 백업 대상 저장소는 저장소 통합 시 기준 원격과 함께 결정한다.
- 코드 저장소에서 data/history_data.json을 직접 추적하는 방식은 선택하지 않았다. 봇이 코드 저장소에 자동 커밋과 push를 하게 되어 코드 이력이 데이터 커밋으로 덮이고, push 자격증명과 충돌 관리 부담이 늘기 때문이다.
- 운영 소개선 3건을 확정했다. 배포 스크립트(git pull → 빌드 → pm2 restart), 상태 확인 실패 시 Discord webhook 알림, history_data.json의 Cache-Control: no-cache 지정이다. plan 9-2·12-1과 checklist 2·6·7절에 반영했다.
- 액티비티 안에서 전적 JSON을 읽을 때 모든 요청이 `/` 매핑(arena.hansoljj.com/pick)을 거친다는 경로 주의점을 9-3절에 추가했다.
- 윈도우 개발 환경을 재확인했다. node v25.0.0, npm 11.6.2, uv 0.12.14는 설치돼 있고 cloudflared는 여전히 미설치다. pyproject.toml 의존성은 py-cord 2.8.1, python-dotenv, requests뿐이라 aiohttp 직접 의존성 추가가 필요하다.

## 2026-09-28 포털 활성화 절차 확인

- 사용자가 운영 앱(롤랜덤챔프봇)의 앱 인증 페이지에서 활성화 방법을 물었다. 앱 인증은 서버 100개 이상 확장용이라 이 프로젝트에 불필요하다고 안내했다.
- 운영 앱에서 Enable Activities를 먼저 켜지 않도록 안내했다. 켜는 즉시 Launch Entry Point 명령이 운영 서버에 노출되는데, URL 매핑이 없고 sync_commands와의 공존도 검증되지 않았기 때문이다. dev 앱에서 먼저 진행한다.
- Discord 공식 문서(building-an-activity.mdx)에서 확인한 절차: OAuth2 Redirects에 `https://127.0.0.1`, 활동 > URL 매핑의 `/`, 활동 > 설정의 Enable Activities, 활성화 시 기본 Entry Point 명령 Launch 자동 생성, Installation Contexts의 User Install·Guild Install 모두 선택.
- 같은 문서의 "Launching a non-distributed Activity is limited to you or members of the developer team" 문장에 따라, 팀 외부 계정의 실행 조건을 운영 전환 전 결정으로 15절에 추가했다. local-development·overview 문서에는 배포 요건이 명시돼 있지 않아 dev 앱에서 실험으로 확정한다.

## 2026-09-28 봇 토큰 모드별 분리 구현

- 사용자 요청으로 DEV_MODE에 따라 봇 토큰을 나눴다. true면 DISCORD_TOKEN_DEV(dev 앱), false면 DISCORD_TOKEN(운영 앱)을 쓴다. 기존에는 DEV_MODE가 데이터 파일과 가상 유저만 바꾸고 로그인은 항상 운영 봇 계정이었다.
- dev 토큰이 없을 때 운영 토큰으로 대체하지 않고 종료하게 했다. 개발 중 운영 봇이 뜨는 사고를 막는 것이 분리의 목적이기 때문이다.
- parse_all_history.py(운영 채널 풀스캔 복구)와 watch_bus.py는 운영 토큰 사용이 맞으므로 변경하지 않았다.
- 두 모드에서 토큰을 빈 값으로 덮어 실행해 각각 DISCORD_TOKEN_DEV, DISCORD_TOKEN 누락 메시지로 종료되는 것을 확인했다. 맥미니 운영 .env는 DEV_MODE=false라 동작 변화가 없다.

## 2026-09-28 프론트 구성 변경 확정

- 사용자는 통합 목표에 맞는 프론트 개선안을 요청했고, Vite + React + TypeScript + Discord Embedded App SDK, React 기본 상태 관리, CSS Modules, WebSocket/fetch 조합으로 플랜을 다시 작성하라고 승인했다.
- 기존 대시보드는 약 1,560줄의 단일 HTML에 집계·DOM 생성·이벤트 연결이 함께 있다. 픽·인증·재접속·결과·전적 화면을 통합할 때 상태와 컴포넌트 경계를 명시하는 편이 관리에 유리하다고 판단했다.
- 측정용 골격부터 React·TypeScript를 사용한다. 기존 대시보드는 집계 함수를 먼저 분리해 재사용하고 결과·전적 통합 단계에서 UI를 이관한다. 카운트다운 개선에 대시보드 전체 재작성을 선행 조건으로 걸지 않는다.
- 카운트다운 정확도는 서버 판정과 시각 보정이 담당한다. 계산을 React와 분리하고 표시할 초만 컴포넌트에 전달한다. 주입 가능한 시계로 복귀·경계 상황을 검증한다.
- 서버 스냅샷과 사용자 탭·필터 상태를 구분한다. 연결·구독은 화면마다 복제하지 않으며 React 개발 모드의 setup/cleanup과 재진입에서 리스너·소켓·타이머 정리를 검증한다.
- TypeScript는 외부 JSON의 런타임 검증을 대신하지 않는다. 메시지 수신 검증과 별도 타입 검사·빌드를 모두 계획에 넣었다.
- 서버는 기존 Python 봇 + aiohttp.web을 유지한다. aiohttp 자체가 HTTP·WebSocket 서버 기능을 제공한다. FastAPI의 요청 검증·OpenAPI 문서화 이점은 있지만 현재 범위에서 전환하지 않는다. aiohttp는 직접 사용하는 의존성으로 명시한다.
- 이번 변경은 계획 문서에 한정한다. 패키지 설치·실제 프론트 구현·서버 변경은 아직 수행하지 않았다.
- [React 공식 Vite·TypeScript 안내](https://react.dev/learn/build-a-react-app-from-scratch). 선택한 프론트 구성의 근거이다.
- [Vite TypeScript·CSS Modules 안내](https://vite.dev/guide/features.html). TypeScript 변환과 별도의 타입 검사, CSS Modules 지원의 근거이다.
- [aiohttp 웹 서버 안내](https://docs.aiohttp.org/en/stable/web_quickstart.html). HTTP 라우트·JSON 응답·WebSocket 지원의 근거이다.
- [FastAPI 기능 안내](https://fastapi.tiangolo.com/features/). 대안 비교에서 요청 검증·자동 API 문서화 기능을 확인했다.
