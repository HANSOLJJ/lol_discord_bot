# 검토 맥락과 판단 근거

## 2026-09-28 범위와 환경

- 사용자 요청은 docs 검토 및 ACTIVITY_DESIGN.md 개선 논의이며, 최종 목표는 두 Git의 기능 통합이다. 저장소와 사용 흐름을 모두 통합하는지는 아직 답변이 없다. 아래는 제안이다.
- 실제 파일명은 ACTIVITY_DESIGN.md이다. 대상 저장소는 lol_discord_bot과 lol_arena이다.
- 기존 확정 방향은 봇 + aiohttp, Vite, 개발 앱 분리, 기존 터널 활용이다. 이 결정을 뒤집을 근거는 발견하지 않았다.
- 처음 exec_command는 helper_unknown_error: setup refresh had errors로 실패했고 filesystem 쓰기는 승인 정책으로 거부됐다. 사용자가 권한을 변경한 뒤 exec_command가 정상 동작했다.
- 봇의 game_recorder.py, parse_all_history.py, docs/PARSE_REPORT.md와 arena의 index.html에 기존 미커밋 변경이 있다. 검토는 현재 작업 파일을 기준으로 했으며 이 변경을 건드리지 않는다.
- 로컬 추적 참조상 bot은 origin/main보다 3커밋 앞서고 arena는 45커밋 뒤다. fetch하지 않았으므로 원격 최신 상태를 확인한 수치는 아니다. 실제 병합 전에 미커밋 작업과 데이터 자동 커밋을 확인해야 한다.
- AGENTS.md/README의 GitHub Pages·arena.dcom.co.kr 설명은 최신 설계 및 기존 context-notes의 Cloudflare Pages·arena.hansoljj.com 설명과 다르다. 실제 운영 설정은 이번에 확인하지 않았다.

## 코드에서 확인한 설계 보완점

- got_champe.py의 ChampionButton.callback은 선택 즉시 current_pick_index를 증가시킨다. 정상 흐름에서 current_picker의 기존 선택을 취소하는 분기는 도달하지 않는다. 설계의 '재클릭 = 취소를 유지'는 실제 규칙을 재확인해야 한다. 최소 변경 제안은 클릭 즉시 확정, 취소 미지원이다.
- 현재 버튼 객체가 제한하던 챔피언 후보를 WS 입력에서는 서버가 직접 검증해야 한다. game_id·턴·참가자·현재 후보·마감을 하나의 락 안에서 검증한다.
- 프로토콜에 turn_id, request_id, state_version을 추가하고 요청 중복 처리 및 오래된 스냅샷 무시 규칙을 정하는 것을 제안한다. game_id는 재시작해도 재사용되지 않는 식별자가 적절하다.
- 락 밖 전송은 유지하되 방송 순서를 보장해야 한다. asyncio.gather만으로 느린 연결의 완료 대기나 누적이 해결되지는 않는다. 소켓별 전송 제한 시간과 최신 스냅샷 병합을 제안한다.
- got_champe.py는 save_wins 이후 record_game을 별도 호출하고, 판 기록 실패 후에도 승리 완료 응답으로 진행할 수 있다. 통합 결과 화면 전에 전적의 기준과 부분 실패 복구를 정해야 한다. history를 기준으로 승수를 재계산하는 방식 또는 SQLite 트랜잭션을 비교하되 DB 도입은 확정하지 않는다.
- game_recorder.upload_async는 전체 JSON을 GitHub Contents API로 배포한다. 대시보드는 최초 fetch 한 번으로 기록을 읽는다. Git 통합만으로 즉시 전적 갱신이 되지는 않는다.
- 서버 재시작 시 인증뿐 아니라 진행 중 게임 상태도 사라진다. 재인증 성공을 게임 복구와 구분하고, 초기 버전은 중단 안내와 새 판 시작 정책을 명시하는 것을 제안한다.

## 기능 통합 제안

- 사용자 흐름은 게임 시작 → 픽 → 결과 대기 → 결과 확정 → 오늘 전적·누적 통계로 정의한다. API와 Discord 명령이 같은 게임·결과 함수를 호출하도록 한다.
- 초기에는 고정 6명과 활성 게임 1개를 유지한다. TEAM1/TEAM2 액티비티 인스턴스를 서버의 같은 게임에 연결하고, instance_id를 게임 ID로 곧바로 쓰지 않는다.
- OAuth로 신원을 확인한 뒤 서버에서 참가·관전·결과 입력 권한을 구분한다. DEV_MODE의 턴 우회도 허용된 테스트 사용자로 제한한다.
- 통합 저장소의 봇 코드와 web 소스를 함께 관리하되, Pages에는 web 빌드 결과만 게시한다. 현재 '저장소 루트 전체 서빙' 전제는 수정해야 한다. 봇 실행과 웹 배포는 별도 유지 가능하다.
- 전적 조회 API와 결과 변경 알림을 통해 열린 화면도 갱신한다. GitHub JSON 배포는 전환기에 유지 가능하다. 제거 시 봇 중단 중 공개 전적 조회가 불가능해질 수 있으므로 읽기용 스냅샷 보존 여부를 정한다.
- 첫 검증은 현재 dev 골격 계획대로 진행하되 두 채널·서로 다른 실제 사용자·모바일 복귀를 포함한다. 한 계정의 DEV_MODE 테스트만으로 권한과 동시성을 검증할 수 없다.
- 다음 순서 제안은 통합 목표·픽 규칙 확정 → dev 경로 검증 → 저장소·웹 배포 정리 → 픽 구현 → 결과·전적 연결 → 기존 경로 정리이다.
- 테스트는 저장소의 tests/에 보존한다. 중복 요청, 이전 턴 요청, 후보 밖 챔피언, 자동 배정 경합, 재접속, 결과 중복 기록과 저장 실패를 검증 대상으로 삼는다.

## 공식 문서 대조

- Discord Multiplayer Experience. https://github.com/discord/discord-api-docs/blob/main/developers/activities/development-guides/multiplayer-experience.mdx
  instanceId는 액티비티 인스턴스 수명에 따른 식별자다. Activity Instance API로 서버에서 위치와 참가자를 확인할 수 있다.
- Discord Networking. https://github.com/discord/discord-api-docs/blob/main/developers/activities/development-guides/networking.mdx
  클라이언트가 보내는 신원·채널 정보를 신뢰하지 않으며, 외부 URL에는 프록시 매핑이 필요하다.
- Discord Local Development. https://github.com/discord/discord-api-docs/blob/main/developers/activities/development-guides/local-development.mdx
  개발 앱 분리와 터널을 통한 프록시 테스트가 공식 가이드와 부합한다. URL Mapping의 긴 경로 우선 및 디렉터리 target도 부합한다. 개발자 본인 외 사용자 접근은 별도 검증해야 한다.
- Discord How Activities Work. https://github.com/discord/discord-api-docs/blob/main/developers/activities/how-activities-work.mdx
  LAUNCH_ACTIVITY는 명령·메시지 컴포넌트·모달 제출 응답에서 지원한다. 실제 채널과 클라이언트별 검증은 필요하다.
- MDN performance.now. https://developer.mozilla.org/en-US/docs/Web/API/Performance/now
  Date.now는 시스템 시계 변경 영향을 받는다. 서버 시각에 performance.now 경과 시간을 더해 표시하고 모바일 복귀 시 재동기화하는 것을 제안한다. 절전 중 동작에는 플랫폼 차이가 있다.
- Python asyncio.gather. https://docs.python.org/3/library/asyncio-task.html#asyncio.gather
  gather는 모든 작업 완료를 기다린다. 병렬 실행 자체가 느린 연결의 대기 시간을 제한하지 않는다.
- Cloudflare Pages Build Configuration. https://developers.cloudflare.com/pages/configuration/build-configuration/
  빌드 루트와 출력 디렉터리를 지정할 수 있다. 통합 저장소에서는 웹 출력만 게시한다.
