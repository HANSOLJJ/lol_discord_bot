# HANDOVER — 챔피언 픽 화면을 디스코드 액티비티로 개편

작성: 2026-09-28. 다음 세션이 이 문서만 읽고 설계·구현을 시작할 수 있게 쓴 인수인계다.
결정은 끝났고(액티비티로 간다), 남은 건 설계 세부와 구현이다.

> 2026-09-28 갱신: 4절의 결정 사항은 확정됐다. 구현 설계는 [ACTIVITY_DESIGN.md](ACTIVITY_DESIGN.md)를 본다.

## 0. 왜 하나 — 메시지 편집 카운트다운의 한계

지금 픽 카운트다운은 봇이 embed 메시지를 1.2초마다 편집해서 숫자를 바꾼다. 화면에 닿기까지
`봇(맥미니) → 디스코드 API → 게이트웨이 → 각자의 디스코드 앱`을 거치고, 지연이 세 구간에서 생긴다.

| 구간 | 실측 (2026-09-15~16) | 봇 쪽에서 해결 가능? |
|---|---|---|
| ① 맥미니 → 디스코드 API | 왕복 0.3초, 집 네트워크 끊김(게이트웨이 RESUME 수십 회, 1006 끊김) | 클라우드 이전으로 가능 |
| ② 디스코드 서버가 편집을 붙잡음 | 가끔 0.85~1.2초 | 불가 |
| ③ 게이트웨이 → 보는 사람 앱 | 보는 사람 네트워크 | 불가 |

2026-09-28 실전: "어떤 채널에서 카운트가 2번 정도 안 보였다". 봇은 편집 실패를 `except: pass`로 삼키고
로그가 없어 원인 미확정. ① 구간 끊김이 가장 유력.

그간 시도한 것 (전부 `got_champe.py`, 상세는 docs/COUNTDOWN_ANALYSIS.md와 커밋 메시지)

- V1 매초 편집 → rate limit 100% 소진 (38e2bc8 이전)
- V2 `<t:X:R>` 클라이언트 렌더 → 보는 사람 PC 시계로 계산돼 사람마다 다른 숫자 (8/29 사고, 552334b에서 폐기)
- V3 시계 기준 1초 틱 → 서버가 편집을 붙잡으면 다음 숫자가 0.4초 만에 덮여 "빠져 보임"
- 현재(d68de61): 횟수 기반, 한 칸 = 편집 응답 대기(최대 1초) → max(박자 1.2 남은 시간, 최소 휴식 0.8).
  표시 20초 ≈ 실제 24초. 실측으로 디스코드 앱은 1초 간격 편집도 전부 그린다는 것 확인 (합치지 않음)

결론: 메시지 편집으로 초를 세는 한 ②③은 못 없앤다. **화면을 우리가 직접 그려야** 근본 해결.
덤으로 해결되는 것: TEAM1/TEAM2 채널에서 채팅이 챔피언 UI를 위로 밀어 올리는 문제(보류 중이던 과제).

## 1. 디스코드 액티비티란

디스코드 안에서 iframe으로 도는 웹앱이다(Embedded App SDK, `@discord/embedded-app-sdk`).
음성 채널에서 "활동 시작"(로켓 아이콘)으로 띄우는 체스·워치 투게더 같은 것. PC·모바일 모두 지원.
봇이 `LAUNCH_ACTIVITY` 인터랙션 응답이나 Entry Point 커맨드(type 4)로 띄울 수 있다.
TEAM1/TEAM2가 음성 채널이라 구조가 잘 맞는다.

## 2. 목표 모습 (초안 — 다음 세션에서 사용자와 확정)

- `/게임시작`은 지금처럼 봇이 처리(팀 배정·픽순·챔프 8개). 대신 "픽 화면 열기" 버튼으로 액티비티를 띄운다.
- 액티비티 화면: 팀 구성, 픽순, 챔프 8개 버튼, 현재 차례, **클라이언트가 직접 세는 카운트다운**, 선택 현황.
- 카운트다운: 서버가 `마감 시각`(서버 시계)만 보내고, 클라이언트는 서버 시계와의 차이(offset)를 재서
  보정한 뒤 스스로 센다. V2의 PC 시계 문제는 offset 보정으로 없어진다(NTP식 왕복 측정 몇 번).
- 판정은 서버가 한다. 현재의 "마감 = 0 도달 + 유예 `pick_grace_seconds`" 규칙과 자동 배정을 서버로 유지.
- 실시간 동기화: 액티비티 ↔ 우리 서버 웹소켓. 누가 고르면 전원 화면에 즉시 반영.
- 봇 메시지 embed는 백업/기록용으로 남길지 결정 필요(액티비티를 안 켠 사람 대비).

## 3. 현재 코드에서 재사용할 것 (got_champe.py, 2026-09-28 기준 줄번호)

- 게임 상태 전역: :71-130 (`selected_users`, `pick_order`, `current_pick_index`, `current_pick_deadline`, `auto_assigned_users` 등)
- 순수 로직: `pick_random_champions` :252, `calculate_pick_order` :267, `get_member_team` :301
- 픽 처리 임계 구역: `ChampionButton.callback` :821~ (턴 검증, 스노플레이크 접수 시각 판정, 재클릭=취소, `pick_lock` :119)
- 타이머·자동 배정: `start_pick_timer` :558, `pick_timeout_handler` :574 (마감 = 0 도달, 유예 뒤 랜덤 배정)
- 자동 시작: `begin_champion_select` :757, `auto_start_handler` :784
- 승리·기록: `VictorySelect` :1161 → `game_recorder.record_game()` → lol_arena GitHub PUT (무변경 유지)
- 화면 갱신 파이프라인 :406-560 (`broadcast_embed_update`, `push_channel_embed`, coalescing) — 액티비티로 가면
  카운트다운 편집은 필요 없어지고, embed을 남긴다면 픽 현황 갱신만 남는다

## 4. 다음 세션에서 결정할 것 (사용자와 상의)

1. **서버를 어디에**: ⓐ 기존 py-cord 봇에 웹소켓 서버(aiohttp) 추가 — 상태가 한 프로세스라 가장 단순, 맥미니 +
   Cloudflare Tunnel로 HTTPS 공개 ⓑ Cloudflare Workers + Durable Object — 루트 `handover.md`(2026-08-26 Workers 이식
   인수인계)와 방향이 겹침. 게임당 DO 1개가 웹소켓·타이머 Alarm·직렬화를 다 해 준다. 대신 봇 로직 포팅이 필요.
   참고: 맥미니 네트워크 끊김(0절 ①)은 ⓐ에서도 영향이 남는다
2. 액티비티 호스팅 위치(정적 파일): Cloudflare Pages / 봇 서버에서 직접 서빙 / lol_arena 같은 GitHub Pages
3. 6명 전원이 액티비티를 켜야 보인다 → 안 켠 사람 대책(봇 embed 병행 여부)
4. 액티비티 안에서 누가 누군지: Embedded App SDK의 `authorize` → `authenticate`로 디스코드 유저 확인(OAuth2 code
   교환을 서버가 해야 함 → 봇 앱의 client secret 필요)
5. DEV/테스트: TEST2 서버에서 먼저. 디스코드 개발자 포털에서 앱의 Activities 활성화, URL Mapping 설정

## 5. 준비물 체크

- 디스코드 개발자 포털: 기존 봇 앱(롤랜덤챔프봇) → Activities 활성화, URL Mappings, OAuth2 redirect, client secret
- HTTPS 공개 주소 (Tunnel 또는 Cloudflare)
- 프론트: 빌드 도구(Vite 등) 도입 여부 — 외부 패키지 설치는 사용자 승인 후
- `.env`에 추가될 비밀: `DISCORD_CLIENT_SECRET` 등 (커밋 금지)

## 6. 참고 자료

- docs/COUNTDOWN_ANALYSIS.md — V1/V2/V3 비교, `<t:R>`이 왜 틀렸나
- 루트 handover.md — Workers + Durable Object 이식 설계(2026-08-26). 서버 위치 ⓑ를 고르면 그대로 재사용
- 측정 도구(저장소 밖): `e:\tmp\countdown_probe.py`, `e:\tmp\countdown_e2e.py` (맥미니 `/tmp`에도 있음)
  — 게이트웨이 도착·서버 적용 시각 측정, Playwright로 웹 클라이언트 DOM 관찰
- 테스트(저장소 밖): `e:\tmp\test_countdown_counter.py` 외. 봇 모듈을 `exec`로 불러 콜백을 직접 구동하는 방식
- 디스코드 문서: Activities / Embedded App SDK (context7 `/discord/discord-api-docs`)

## 7. 현재 운영 상태 (2026-09-28)

- 맥미니 tmux `lol` 세션에서 `uv run python -u got_champe.py` (9/23 15:37 시작), 코드 d68de61
- config: pick_timeout 20, auto_start_seconds 15, pick_grace_seconds 2, countdown_step_seconds 1.2
- 개편 전까지는 현재 봇을 그대로 운영한다
