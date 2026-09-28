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

## 2026-09-28 dev 앱 포털 설정 점검

- 사용자가 롤랜덤챔프봇-dev 앱을 만들고 포털 설정을 마쳤다. .env에 dev 토큰 키가 DISCORD_DEV_TOKEN으로 들어가 있어 코드 규칙에 맞게 DISCORD_TOKEN_DEV로 키 이름만 바꿨다(값은 읽지 않음).
- Discord API(applications/@me, users/@me/guilds, applications/{id}/commands)로 점검했다. dev 토큰은 운영 토큰과 다르고 앱 이름·client ID가 일치했다. Presence·Server Members 인텐트가 켜져 있고(비인증 앱의 LIMITED 플래그), 설치 컨텍스트는 길드·사용자 모두, 기본 설치 범위는 bot·applications.commands, 권한 정수 84992(채널 보기·메시지 보내기·링크 임베드·메시지 기록 보기)였다. 참가 서버는 TEST2 하나다.
- 남은 문제 두 가지. 리디렉션 값이 앞에 공백이 붙은 " https://127.0.0.1"로 저장돼 있어 포털에서 고쳐야 한다. 전역 명령이 비어 있고 EMBEDDED 플래그도 없어 액티비티 활성화(Launch 명령 자동 생성)가 아직 적용되지 않았다. URL 매핑에 넣을 터널 주소가 먼저 필요하므로 cloudflared 설치가 다음 선행 작업이다.
- 전역 명령이 비어 있는 지금 봇을 먼저 실행하면 슬래시 명령만 등록된다. 이후 액티비티를 켜고 봇을 재시작하면 Entry Point와 sync_commands 공존(checklist 1절)을 깨끗한 상태에서 검증할 수 있다.

## 2026-09-28 맥미니 현황 확인 (SSH)

- 이 세션의 ssh-mcp에 `macmini`(Tailscale 100.104.120.76, 실제 로그인 사용자 hansol)가 등록돼 있어 읽기 전용 명령으로 확인했다.
- 운영 롤 봇은 맥미니에서 실행 중이 아니다. got_champe 프로세스가 없고 pm2에는 finance만 있으며 tmux 세션도 없다. 단계 0(pm2 자동 기동)의 필요성이 실제로 확인됐다.
- 맥미니 봇 저장소는 ~/projects/lol_discord_bot, HEAD d68de61(= 당시 origin/main)이다. 윈도우 로컬에는 push하지 않은 커밋이 여러 개 있다.
- 도구 버전은 node v25.8.1, uv 0.12.13, cloudflared 2026.8.2이고 ~/.cloudflared에 finance 터널의 config.yml과 자격증명이 있다.
- 사용자가 개발용 윈도우 터널의 필요성을 질문했다. 편집이 윈도우에서 일어나므로 빠른 반복을 위한 것이며, 맥미니만으로 개발하는 대안과의 비교를 안내했다.
- 사용자가 윈도우 고정 터널로 확정했다. quick tunnel은 실행마다 주소가 바뀌어 URL 매핑을 매번 고쳐야 하고, 맥미니 개발은 수정마다 코드 전송·재시작이 붙고 finance 터널 재시작이 필요하다. 대시보드 관리형 터널 `lol-dev`를 윈도우 서비스로 설치하고 `lol-dev.hansoljj.com` → `127.0.0.1:5173`으로 연결한다.
- 연결 대상을 localhost 대신 127.0.0.1로 정했다. 윈도우의 Node가 localhost를 IPv6(::1)로만 바인딩하면 터널이 IPv4로 접속해 502가 날 수 있으므로, Vite 바인딩 주소와 터널 대상을 같은 IPv4 주소로 고정한다.
- 지연시간 측정은 운영과 같은 경로여야 의미가 있으므로 단계 1 측정은 맥미니에서 한다. SSH로 맥미니 작업이 가능하다.

## 2026-09-28 개발 환경 구축 완료

- 사용자가 cloudflared 설치, 대시보드 관리형 터널 lol-dev 생성과 윈도우 서비스 등록, 포털 URL 매핑·액티비티 활성화·리디렉션 수정을 직접 했다. 이후 설치 작업은 사용자 승인으로 에이전트가 진행했다.
- 봇에 aiohttp==3.14.3을 직접 의존성으로 추가했다(bot 8f3f68f). py-cord 전이 의존성으로 이미 설치돼 있어 새 다운로드는 없었다.
- lol_arena/activity/에 create-vite 9.2.1의 react-ts 템플릿으로 골격을 만들고 @discord/embedded-app-sdk를 추가했다(arena 9251c2a). 설치 버전은 react 19.3.0, vite 8.3.1, typescript 6.0.3, @vitejs/plugin-react 6.1.1, embedded-app-sdk 2.5.0이다. 템플릿 기본값인 oxlint와 @types/node는 그대로 두었다.
- vite.config.ts에 server.host 127.0.0.1, port 5173(strictPort), allowedHosts lol-dev.hansoljj.com, hmr.clientPort 443을 설정했다. /pick-api 프록시와 build base는 봇 서버·배포 작업 때 추가한다.
- 검증 결과, 템플릿 상태에서 tsc -b와 vite build가 통과했다. cloudflared 서비스는 Running·Automatic이고, Vite를 끈 상태에서 lol-dev는 502, 켠 상태에서 로컬 200과 터널 경유 Vite 페이지 응답을 확인했다. API 점검에서 EMBEDDED 플래그, Entry Point 명령 launch(타입 4), 공백이 제거된 리디렉션을 확인했다.
- 윈도우에서 백그라운드 npm run dev를 작업 중지로 멈추면 자식 node(vite) 프로세스가 남아 5173을 계속 점유했다. 명령줄로 해당 vite 프로세스임을 확인한 뒤 종료했다. 이후 검증 때도 포트 해제를 확인한다.
- 남은 1단계 준비 항목은 실제 테스트 계정 접근 확인, CSS Modules 적용, activity_server 구현, LAUNCH_ACTIVITY와 sync_commands 공존 검증이다. 전역 명령에 launch만 있는 지금 봇을 실행하면 공존 검증을 바로 할 수 있다.

## 2026-09-28 Entry Point 명령과 명령 동기화 공존

- dev 앱에 액티비티를 켜 Launch Entry Point 명령(type 4)만 있는 상태에서 dev 봇을 실행했다. py-cord의 on_connect 자동 동기화와 on_ready의 bot.sync_commands()가 모두 50240 오류("You cannot remove this app's Entry Point command in a bulk update operation")로 실패했다. Launch는 지워지지 않았지만 슬래시 명령이 하나도 등록되지 않았다.
- py-cord 2.8.1 코드를 확인한 결과, 모르는 명령을 삭제 대상으로 분류해 일괄 덮어쓰기에서 빼고, delete_existing=False나 individual 방식에서도 등록 후 대조 단계에서 모르는 명령에 ValueError를 낸다. 라이브러리 설정만으로는 해결되지 않는다.
- Bot(auto_sync_commands=False)로 자동 동기화를 끄고, on_ready에서 sync_commands_keeping_entry_point()로 직접 동기화하게 바꿨다. 등록된 명령을 조회해 type 4 명령을 application_id·version만 빼고 그대로 덮어쓰기 목록에 포함한다. 명령 ID 캐시는 하지 않으며, py-cord가 ID로 못 찾으면 이름으로 찾는 동작(process_application_commands)에 의존한다. 전역 명령에는 interaction data의 guild_id가 없어 이름 대조가 성립한다.
- 검증으로 dev 봇을 두 번 실행했다. 두 번 모두 오류 없이 로그인했고, 전역 명령은 launch(4)와 게임시작·승리·누적결과·시즌시작·번복(1)이 함께 등록됐다. 운영 앱에는 아직 Entry Point가 없어 운영 봇은 기존처럼 슬래시 명령만 덮어쓴다.
- 동작 차이로, 예전 py-cord는 변경이 없으면 덮어쓰기를 건너뛰었지만 지금은 on_ready마다 조회 1회와 덮어쓰기 1회를 한다. 기존 명령 덮어쓰기는 명령 생성 한도에 포함되지 않으므로 문제로 보지 않았다. 모르는 명령이 들어올 때의 py-cord 자동 재동기화도 함께 꺼진다.
- 슬래시 명령이 실제 Discord에서 실행되는지는 사용자가 TEST2에서 확인할 항목으로 남겼다.

## 2026-09-28 워커 병렬 진행 방식

- 사용자가 Orca supervised 방식으로 여러 워커에게 일감을 맡기기로 했다. 에이전트가 코디네이터로 worktree 생성, 워커 실행, 완료 보고 검토, main 병합을 맡는다. push는 하지 않는다.
- 일감은 서로 독립적인 세 개다. 1번 액티비티 서버(activity_server.py, 봇 실행부 asyncio 전환)와 2번 프론트 골격(SDK 인증, WebSocket, 시계 보정·카운트다운 모듈)은 claude, 3번 픽 판정 로직 분리와 회귀 테스트는 agy가 맡는다. 사용자가 agy 성능이 가장 낮다는 점을 들어, 새로 설계할 일은 claude에, 기존 코드를 동작 변화 없이 옮기는 일은 agy에 배정했다.
- 3번은 운영 픽 판정을 옮기므로 "현재 동작을 고정하는 테스트를 먼저 쓰고 옮긴다"는 순서를 지시서에 넣고, 코디네이터가 diff를 중점 검토한다.
- 워커마다 새 worktree를 준다. main에는 사용자의 미커밋 변경이 있고, 1번과 3번이 같은 got_champe.py를 고치며, dev 봇 토큰과 8790·5173 포트는 동시에 하나만 쓸 수 있기 때문이다. 워커는 단위 테스트와 빌드로만 검증하고, 실제 dev 봇·Discord 실행은 병합 후 코디네이터가 한다.
- 1번과 2번이 병합 때 맞도록 메시지 형식을 docs/ACTIVITY_PROTOCOL.md(protocol_version 1)로 먼저 고정했다. 1단계 측정을 위해 게임 상태 연결 전에도 카운트다운을 볼 수 있는 개발 전용 demo_countdown 메시지를 넣었다.
- 테스트는 새 패키지 없이 한다. 파이썬은 unittest와 aiohttp.test_utils, 프론트는 Node 25 내장 테스트 러너(node --test)를 쓴다. 프론트 설정의 erasableSyntaxOnly와 .ts 확장자 import 허용으로 TypeScript를 그대로 실행할 수 있다.

## 2026-09-28 워커 실행 기록

- Orca 1.4.210의 worker-start는 `--worktree new-top-level`을 선택자로 인식하지 못했다. worktree를 `orca worktree create --no-parent`로 먼저 만들고 정확한 id로 배정했다.
- Orca가 worktree를 로컬 main이 아닌 origin/main에서 분기해, 작업 전에 세 브랜치를 로컬 main으로 fast-forward했다. 저장소 기준 ref 변경은 사용자 결정 대기다.
- 첫 claude 워커가 새 폴더의 신뢰 확인 창에서 기본값 "No, exit"로 종료됐다. worker-stop 후 claude용 두 worktree 폴더만 신뢰 처리하고 --retry-of로 재시도했다. agy의 Orca 에이전트 id는 `antigravity`다.
- 1번 워커의 규격 해석 질문 세 가지(데모 성공 reply, 4KB 초과 처리, 토큰 빈도 제한 기준)를 기본안대로 승인하고 규격 문서에 반영했다(66d11d7). 2번 워커에 프론트 영향분을 알렸다.
- 3번(agy) 완료 보고를 검토해 승인했다. 검사 순서 9단계, 응답 문구, 원본 객체 직접 변경, 거절·취소 시 인덱스 유지가 원본과 같다. 타이머 취소가 상태 변경 뒤로 옮겨졌지만 await 없는 동기 구간이라 동작 차이가 없고, 모든 클릭에서 미리 호출하게 된 get_member_team은 부수 효과가 없는 조회다. callback이 "차례 아님" 문구를 한 번 더 만드는 중복이 있으나 결과가 같아 그대로 두었다.
- 코디네이터가 테스트 16개와 py_compile을 직접 재실행해 통과를 확인하고, 워커를 해제한 뒤 HANSOLJJ/pick-logic을 main에 --no-ff로 병합했다. 병합 후 main에서도 테스트가 통과했다.
- 워커가 보고한 의심 동작(정상 흐름에서 취소 분기와 "이미 선택함" 분기에 도달하기 어려움)은 기존 검토 결과와 같으며 plan 15절 "실제 픽 취소 지원" 미결 항목으로 둔다.
- 1번(claude) 완료 보고를 검토해 승인했다. activity_server.py는 비밀값을 로그에 남기지 않고(상태 코드·예외 이름만), 접근 로그는 query 없이 경로만 남긴다. 상태 변경과 브로드캐스트는 락 안에서 await 없이 하고 전송은 연결별 송신 작업이 맡는다. got_champe.py 변경은 import 한 줄과 실행부뿐이다. py-cord 2.8.1의 `async with bot`은 실행 중인 루프로 다시 연결하며, 기존 코드에 bot.loop 의존이 없음을 확인했다.
- 워커의 추가 해석 두 가지(3회째 위반에도 reply를 보낸 뒤 4400으로 닫음, 1단계에는 주입할 콜백이 없어 생성자에 설정·discord_api_base·session_ttl만 둠)는 규격과 충돌하지 않아 그대로 받았다.
- 코디네이터가 테스트 28개를 재실행한 뒤 워커를 해제했다. 워커 터미널은 사용자 조작 이력(user_takeover)으로 Orca가 닫지 않고 남겼다. HANSOLJJ/activity-server를 main에 --no-ff로 병합했고, tests/__init__.py는 자동 병합됐다. 병합 후 main에서 테스트 44개(서버 28, 픽 판정 16)가 통과했다.
- 실제 dev 봇으로 통합 확인을 했다. 액티비티 서버가 127.0.0.1:8790에서 먼저 뜬 뒤 봇이 로그인했고, 전역 명령은 launch와 슬래시 명령 5개가 유지됐다. 가짜 code 토큰 요청은 실제 Discord 거절로 401 oauth_failed, JSON이 아닌 본문은 400 bad_request, 잘못된 세션의 WebSocket은 4401로 닫혔다.
- 2번(claude) 완료 보고를 검토해 승인했다. 변경은 lol_arena의 activity/ 안에만 있다. discord.ts는 frame_id로 화면만 나누고 prompt none 인증 실패 시 버튼으로 동의 창을 허용하며, 진행 중인 인증을 공유해 React 개발 모드의 이중 마운트에서도 authorize가 한 번만 나간다. connection.ts는 소켓 동일성으로 이전 소켓 이벤트를 버리고, epoch 변경 시 상태를 폐기하며, 4401은 재인증 이벤트, 4400은 재접속 없이 업데이트 필요로 처리한다. 카운트다운 훅은 rAF로 계산하되 표시할 초가 바뀔 때만 상태를 갱신하고 0에서 멈춘다.
- 워커의 규격 해석(reply의 id·message·state_version null 허용, round·season 정수 또는 null, 다른 epoch의 state 무시, hello 직후·sync 뒤 첫 state는 같은 버전도 적용, 버튼 재시도는 prompt none 없이, 4400은 새로고침 안내)은 서버 구현·규격과 맞는다. 특히 서버는 JSON 오류 reply에 id null을 보내므로 null 허용이 필요했다.
- 코디네이터가 build(tsc -b 포함), lint(경고 0), test(34개)를 직접 재실행해 통과를 확인했고, HANSOLJJ/activity-frontend를 arena main에 --no-ff로 병합했다. 병합 후 arena main에서도 build와 test가 통과했다. 워커 터미널은 user_takeover로 남았다.
- 세 워커의 디스패치가 모두 정리됐고 회수할 터미널은 없다. 실제 Discord 클라이언트 안의 인증·연결·카운트다운 확인과 맥미니 경로 RTT 측정이 단계 1의 남은 일이다. Discord 프록시가 상대 경로 /pick-api를 URL 매핑 없이 `/` 매핑으로 넘기는지는 실제 실행으로 확인한다.
- 통합 확인 중 사용자가 오후 3:31에 직접 실행한 봇 프로세스(`uv run python -u got_champe.py`)가 떠 있음을 발견했다. 코디네이터가 띄운 것이 아니므로 건드리지 않았다. 같은 dev 토큰이면 확인하는 동안 봇 세션이 둘이었을 수 있다.

## 2026-09-28 PC Discord 실제 실행 확인

- 개발 중인 액티비티는 Discord 클라이언트의 개발자 모드를 켜고 음성 채널에 들어가야 로켓 버튼의 활동 목록에 나타난다(공식 local-development 문서). Entry Point 명령 launch(type 4)는 `/` 슬래시 목록에 나오지 않는다. 트레이 메뉴로 Discord를 완전히 종료했다 다시 켜서 명령 목록을 갱신했다.
- 첫 실행은 "연결 중"에서 멈췄다. 봇 서버 로그에 액티비티의 토큰 요청이 없었고, Vite 로그에 첫 접속 순간 SDK 의존성 최적화로 인한 페이지 새로고침이 있었다. 새로고침이 Discord SDK 연결 확인(ready)을 끊은 것으로 판단했고, 최적화가 끝난 뒤 다시 실행하자 정상 동작해 원인이 확인됐다. vite.config.ts에 optimizeDeps.include로 SDK를 서버 시작 때 미리 최적화하게 했다(arena ff5e2a2).
- 두 번째 실행에서 전체 흐름이 동작했다. 실제 Discord OAuth 토큰 교환 200과 세션 발급, WebSocket 연결, 데모 카운트다운 시작·종료, RTT 15샘플(p50 9ms, p95 12ms, 최대 12ms)을 확인했다. Discord 프록시가 `/pick-api` 요청을 URL 매핑 추가 없이 `/` 매핑(lol-dev)으로 넘기고, Vite 프록시가 봇 서버로 전달한다. `/.proxy` 접두사는 필요 없었다.
- RTT 값은 윈도우 개발 터널로 같은 PC에 돌아오는 경로라 운영 경로가 아니다. 단계 1의 p95 < 1초 판정은 맥미니 경로에서 한다.
- 사용자가 오후 3:31에 실행해 둔 봇은 .env의 DEV_MODE=false로 뜬 운영 봇이었고, 사용자가 테스트 전에 종료했다. 맥미니에도 운영 봇이 없어 그 시점부터 운영 봇은 꺼진 상태다.

## 2026-09-28 다른 계정의 액티비티 실행 조건

- 사용자가 다른 계정으로 웹 브라우저 Discord에서 참가를 시도했으나 되지 않았다. 공식 문서 문장("Launching a non-distributed Activity is limited to you or members of the developer team")대로 소유자 외 계정에는 권한이 없다.
- Discord 개발자 지원 문서("What are Verified and Unverified Activities?", "Unverified Activity Safety")에 따르면, 검증되지 않은 액티비티는 개발팀과 명시적으로 초대받은 앱 테스터만 실행할 수 있고 멤버 25명 미만 서버와 DM에서만 실행된다. 검증된 액티비티는 모든 Discord 사용자가 App Launcher에서 찾고 실행·참가할 수 있다. "배포된" 상태는 이 검증을 뜻하는 것으로 본다.
- 앱 테스터 절차: 포털의 앱 → App Testers에서 사용자명으로 초대하고, 초대받은 사람이 이메일로 수락한다. 팀 소유 여부와 무관하게 최대 50명이다. 테스터는 클라이언트 고급 설정의 Application Test Mode를 켜고 앱 ID를 넣어 활성화해야 비공개 액티비티가 보인다.
- 코디네이터가 처음에 Application Test Mode 입력창을 "다른 계정 권한과 무관하니 취소하라"고 잘못 안내했다가 정정했다. 이 입력창은 앱 테스터 절차의 일부다.
- 운영 전환 때 친구 6명은 앱 테스터(각자 이메일 수락과 테스트 모드 설정, 운영 서버 멤버 25명 미만 조건) 또는 앱 인증 중 하나로 해결한다. 앱 인증 요건은 포털 앱 인증 화면에 나온 팀 소유, 이용약관·개인정보 처리방침 링크, 팀원 2단계 인증이다.

## 2026-09-28 앱 인증 절차 조사

- 사용자가 앱 테스터는 뒤로 미루고 운영 앱의 앱 인증을 우선하겠다고 했다. 인증된 앱의 액티비티는 모든 사용자가 쓸 수 있고 25명 서버 제한도 없어진다.
- 절차(Discord 문서 Enabling Discovery, 지원 문서 검색 결과, 사용자가 보여준 포털 앱 인증 화면 기준): 포털 앱 인증 탭의 체크리스트를 모두 충족한다. 항목은 팀 소유, 유해 표현 없음, 이용약관 링크, 개인정보 처리방침 링크, 설치 링크, 팀원 전원의 이메일 인증과 2단계 인증이다. 그다음 개발자 약관·정책 준수와 "인증 후 이름·소유권은 Discord 지원 없이 바꿀 수 없다"는 두 확인란에 체크하고 Verify App을 누른다. 팀 소유자가 Stripe로 신분증 인증을 한다(16세 이상 신분증, 3년마다 재인증, 60일 안에 못 하면 인증 상실).
- 확인하지 못한 것: 인증 신청 뒤 사람이 하는 별도 내용 심사가 있는지, 걸리는 기간, 액티비티에만 해당하는 추가 기준. Discord 도움말 센터 문서가 403으로 열리지 않아 원문을 읽지 못했다. Discovery를 켜면 앱 목록 노출까지 최대 24시간이 걸린다는 문장만 공식 문서로 확인했다.
- 특수 인텐트: 2026년 6월 변경으로 사용자 1만 명 미만 앱은 포털 토글만으로 Presence·Server Members 인텐트를 계속 쓸 수 있다. 이 봇은 인증과 무관하게 인텐트 심사 대상이 아니다.
- 인증 대상은 운영 앱(롤랜덤챔프봇)이다. 팀 이전은 되돌릴 수 없고, 인증 뒤에는 앱 이름을 스스로 바꿀 수 없으므로 이름을 먼저 확정해야 한다. 개인정보 처리방침에는 lol_arena 공개 저장소의 history_data.json에 Discord 사용자 ID와 이름이 공개된다는 점을 사실대로 적어야 한다.

## 2026-09-28 여러 계정·모바일 실제 확인

- 앱 테스터 초대는 Discord 친구 관계가 있어야 가능했다. 친구 추가 → 포털 앱 테스터 초대 → 이메일 수락 → 애플리케이션 테스트 모드(앱 ID, URL 출처 유형 "Discord 프록시") 순서로 다른 계정이 웹 브라우저 Discord에서 참가했다. 권한 전에는 "Do not have access"가 떴다. 코디네이터가 앞서 검색 요약만 보고 초대 방법을 단정했다가 실제 화면과 달라 정정한 이력이 있다.
- 소유자 계정은 휴대폰에서 연결됐고 RTT 20샘플 p50 48ms, p95 72ms, 최대 101ms였다(윈도우 개발 터널 경로, 참고용).
- 서버 로그에서 두 계정이 동시에 연결(연결 2개)된 상태로 데모 카운트다운이 시작됐고, 사용자가 휴대폰과 다른 계정 화면에서 같은 숫자로 줄어드는 것을 확인했다. 휴대폰을 백그라운드로 보냈다 돌아와도 카운트다운이 이어졌다.
- Vite 설정 변경으로 개발 서버가 재시작됐을 때 WebSocket이 1006으로 끊겼다가 토큰 교환 없이 같은 세션으로 다시 연결됐다. 실제 환경에서 자동 재접속이 동작함을 확인했다.
- 지금 액티비티는 1단계 측정용 골격이라 데모 카운트다운만 있다. 실제 게임 연결, 챔피언 선택 화면, 팀·결과·전적 표시는 4단계 이후 작업이다. 단계 1에서 남은 항목은 맥미니 경로 RTT 측정(p95 < 1초 판정)과 LAUNCH_ACTIVITY 버튼 동작 확인이다.

## 2026-09-28 액티비티 실행 위치를 팀짜기로 결정

- 사용자가 팀 편성 후 TEAM1·TEAM2 음성 채널을 오가는 상황에서 액티비티가 어떻게 되는지 물었다. 음성 채널에서 연 액티비티는 텍스트 채널로 화면을 옮겨도 작은 창으로 유지됐고, 채널 목록에서 TEAM1과 TEAM2에 인스턴스가 따로 열리는 것도 확인했다.
- 텍스트 채널 입력창의 앱 버튼(App Launcher)으로 팀짜기에서 dev 액티비티를 열 수 있었다. 팀짜기에서 연 액티비티는 TEAM1·TEAM2 음성 채널을 오가도 화면에서 계속 보였다(PC 확인). 코디네이터가 앞서 로켓 버튼 설명을 "음성 채널에서만"처럼 들리게 말해 혼동을 준 적이 있다.
- 사용자 결정: 액티비티 모드에서는 팀짜기에만 메시지와 실행 버튼을 보내고, TEAM1·TEAM2 음성 채널 채팅에는 보내지 않는다. 채널별 전송·편집 실패가 카운트다운 미표시 문제의 원인 후보(3절)였으므로 전송 대상 자체를 줄이는 효과도 있다.
- 코드 확인 결과 봇이 TEAM1·TEAM2를 쓰는 곳은 config.json channels의 메시지 전송 대상(get_game_channels)뿐이고, 팀 편성은 온라인 상태 기준이다. 설정 변경만으로 적용할 수 있으나 기존 embed 모드 사용자에게도 영향이 있어 6단계 운영 전환 때 적용한다.
- 남은 확인: 모바일에서 텍스트 채널 액티비티가 음성 채널 이동 중에도 유지되는지.
- 같은 날 dev 봇으로 기존 embed 방식 `/게임시작` 한 판(ROUND 98)이 끝까지 진행됐다. 개발 모드 가상 유저라 6명 모두 자동 배정이었고, 버튼을 직접 눌러 고르는 경로는 아직 확인하지 않았다.

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
