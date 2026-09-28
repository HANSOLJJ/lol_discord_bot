# Context Notes: 픽 화면 액티비티 개편

결정과 그 이유를 날짜순으로 append 한다. 계획: [docs/ACTIVITY_DESIGN.md](../../../docs/ACTIVITY_DESIGN.md).

## 2026-09-28 설계 확정 (사용자와 상의)

- **액티비티로 간다** (ACTIVITY_HANDOVER에서 이미 결정). 이번 세션은 세부 결정.
- **arena.hansoljj.com 활용** (사용자 요청). 확인 결과 arena는 Cloudflare Pages(lol_arena repo, CNAME 파일은 이미 제거됨)이고
  `hansoljj.com` 존 전체가 Cloudflare에 있다. 화면은 `arena.hansoljj.com/pick/`에 둔다. URL Mapping target은 경로 붙은 디렉터리 허용(디스코드 문서).
- **디스코드 API로 동기화할 수 없나?** (사용자 질문) → 불가. SDK는 참가자 목록·음성 상태 같은 디스코드 정보만 주고,
  참가자 간 임의 데이터 전달 기능이 없다. 공식 멀티플레이어 가이드도 자체 서버를 쓰라고 한다. 채널 메시지로 우회하면 지금의 편집 방식으로 돌아간다.
- **Cloudflare도 북미 경유라 지연이 비슷하지 않나?** (사용자 질문) → 맞다. 실측(이 PC, KT):
  arena.hansoljj.com·fin.hansoljj.com = SJC 엣지, 연결 약 150ms / discordsays.com = ICN, 약 8ms. 맥미니 finance 터널은 icn01·icn06에 연결.
  그러나 액티비티에서는 숫자가 네트워크를 타지 않으므로(마감 시각 1회 + offset 보정) 지연 크기가 표시에 영향이 없다.
  지연은 남의 픽 반영(0.2~0.3초)과 클릭 도착(유예가 흡수)에만 남는다. 디스코드 프록시 → 우리 서버 구간은 밖에서 못 재므로 1단계 게이트로 실측.
- **서버 위치 = 기존 봇 + aiohttp + 터널 (A안)**. 버린 안:
  - B(Worker+DO 분업): 픽 20초만 맥미니와 무관해지고 시작·embed·기록은 여전히 맥미니. 상태가 두 곳에 나뉘어 동기화 코드가 계속 따라온다
  - C(전면 Workers 이식, 루트 handover.md): 범위가 가장 크고 presence 대체(참가 버튼) 재설계까지 겹친다
  - D(VPS): A와 코드가 같아 나중에 옮기기 쉽다. 지금은 서버 관리 부담만 늘어난다
  - Cloudflare로 옮겨도 속도 이득은 없다(Worker·DO도 같은 해외 엣지 근처). 이득은 맥미니 끊김 독립성 하나뿐
- **finance 참고** (사용자 제안): finance는 2026-08-31 Cloudflare Pages Functions/KV → 맥미니 Express+SQLite+pm2 + Tunnel로 옮겼다.
  이유 중 "24/7 상시 실행", "장시간 웹소켓"이 이번과 같다. 가져올 것: 기존 `finance` 터널 재사용(ingress 한 줄), 127.0.0.1 바인드,
  Pages와 Tunnel은 같은 호스트명 불가 → 서버는 `pick.hansoljj.com`, cloudflared plist 인자 함정은 이미 해결됨. Access는 붙이지 않는다(디스코드 프록시가 통과 못 함).
- **embed = 픽 현황판만 + 전환 기간 구 방식 스위치(`pick_ui`)**. 사용자가 "애매하다"고 해서 선택지 5개(액티비티만 / 현황판 / 현황판+개인 비상 버튼 /
  버튼 완전 병행 / 전환 스위치)를 비교해 추천. 판정은 서버라 액티비티를 못 켠 사람도 자동 배정으로 게임이 멈추지 않는다. 비상 버튼(ephemeral)은 필요가 생기면 추가.
- **프론트 = Vite** (사용자 결정). 프레임워크 없이 바닐라로 시작. 소스 `lol_arena/activity/`, 빌드 결과 `lol_arena/pick/` 커밋,
  Pages 설정 무변경(루트에 package.json이 없어 Pages가 npm install을 하지 않음).
- **자동 기동 필수** (사용자 지시). 조사 중 발견: 맥미니가 2026-09-28 10:05 KST경 재부팅됐고 **롤 봇이 꺼져 있었다**(tmux 세션 없음, 프로세스 없음).
  pm2는 이미 launchd(`pm2.hansol.plist`)에 등록돼 finance를 띄우고 있으므로 같은 pm2에 `lol` 앱을 추가한다.
- 코드 조사: aiohttp 3.14.3 이미 설치(py-cord 의존성) → Python 새 패키지 없음. py-cord 2.8.1에 LAUNCH_ACTIVITY 헬퍼 없음 → raw callback type 12.
  맥미니 봇 경로 `~/projects/lol_discord_bot`(d68de61), node v25.8.1, uv `/opt/homebrew/bin/uv`.
- **dev 앱 따로 만든다** (사용자가 설계 문서에 적으라고 지시). 이유: URL Mapping이 앱마다 한 벌이라, 운영 앱으로 개발하면
  운영 주소를 개발 PC로 바꿔야 하고 그 사이 친구들이 개발 화면을 보게 된다. 토큰이 달라서 윈도우 봇과 맥미니 봇이 같은 클릭을 둘 다 받는 문제도 사라진다.
  개발 루프는 Vite(:5173)가 `/pick-api`를 봇(:8790)으로 proxy하고 quick tunnel 하나만 연다. 윈도우에 cloudflared가 없다(확인).
- **미결 (사용자 확인 필요)**: Vite·SDK·윈도우 cloudflared 설치 승인, 터널 재시작 작업 시각, 지금 TEST2 테스트 때 운영 토큰을 같이 쓰는지.
