# HANDOVER — 파이썬 상주 봇 → Cloudflare Workers 이식

작성: 2026-08-26. 다음 세션(사람/에이전트)이 이 문서만 읽고 이식 작업을 시작할 수 있게 쓴 인수인계다.
현재 코드 조사 근거(파일:줄번호)를 그대로 남겼으니 코드를 다시 훑지 않아도 된다.

## 0. 왜 옮기나

지금 봇은 `python got_champe.py`로 **PC에서 사람이 직접 켜는 상주 프로세스**다 (got_champe.py:1203-1210, bat/작업스케줄러 없음 — 확인됨). PC가 꺼져 있으면 봇도 죽는다. Cloudflare로 옮기면 서버 없이 항상 살아있고, 무료 플랜 안에서 충분히 돈다.

## 1. 개념 — 디스코드 봇을 Cloudflare에 "올린다"는 게 뭔가

디스코드 봇이 동작하는 방식은 두 가지다.

1. **게이트웨이 방식 (지금)** — 봇이 디스코드에 WebSocket으로 **상시 접속**해 있고, 서버의 모든 이벤트(메시지, 접속 상태 등)를 실시간으로 받는다. py-cord가 이걸 해준다. 상시 접속이 필요하므로 **켜져 있는 컴퓨터가 필수**다.
2. **HTTP Interactions 방식 (이식 후)** — 봇은 아무 데도 접속해 있지 않다. 대신 디스코드 개발자 포털에 **"내 URL"을 등록**해 두면, 유저가 슬래시 커맨드를 치거나 버튼을 누를 때마다 **디스코드가 그 URL로 HTTP POST를 쏴 준다.** 우리는 그 요청에 응답만 하면 된다.

Cloudflare **Workers**는 정확히 이 두 번째 방식을 위한 물건이다 — "항상 켜진 서버"가 아니라 **"요청이 올 때만 실행되는 함수"**를 전 세계 엣지에 올려두는 서비스다. finance 프로젝트의 Pages Functions(`functions/api/*.js`)와 같은 런타임이고, 차이는 정적 사이트 없이 함수만 단독 배포한다는 것뿐이다.

즉 "Cloudflare에 올린다" = ① Worker 하나 만들고 ② 디스코드 요청의 서명을 검증해 응답하는 JS를 배포하고 ③ 개발자 포털에 그 Worker URL을 Interactions Endpoint로 등록. 이게 전부다. 절차는 6절에.

## 2. 현재 봇 요약 (조사 결과)

- **커맨드 3개** (전부 인자 없음, 프리픽스 커맨드 없음): `/게임시작`(got_champe.py:795-927), `/승리`(:1135-1137), `/누적결과`(:1143-1175)
- **게이트웨이 이벤트는 on_ready 하나뿐** (:1182-1199) — on_message 등 없음. 이식 장벽이 낮은 편
- **외부 연동**: Data Dragon(챔프 목록, 키 불필요, :164-179) / GitHub Contents API PUT(game_recorder.py:26-71 → `HANSOLJJ/lol_arena`의 `history_data.json`)
- **저장**: 전부 로컬 파일 — `data/wins.json`(누적 승수+총 판수), `data/history_data.json`(마스터 기록). DB 없음
- **자격증명**: `.env`에 `DISCORD_TOKEN`, `ARENA_GH_TOKEN`(fine-grained PAT, lol_arena Contents RW), `ARENA_GH_REPO`, `DEV_MODE`. 하드코딩 없음 (확인됨)
- **의존성**: py-cord / requests / python-dotenv 3개뿐 (requirements.txt)
- **정기 작업 없음** — GitHub 업로드는 승리 확정 시 1회 트리거(game_recorder.py:148), 스케줄 아님

## 3. 기능별 이식 판정 ★ 핵심

| 기능 | 판정 | 근거·방법 |
|---|---|---|
| `/누적결과` | **쉬움** | wins.json 읽기만(:1143-1175) → KV 읽기로 교체 |
| `/승리` + 승리팀 드롭다운 | **쉬움** | 요청-응답 구조. 기록 저장을 KV로, GitHub PUT은 fetch로 |
| Data Dragon 챔프 로드 | **쉬움** | 공개 CDN 그대로 fetch. on_ready 캐싱(:1185) → KV/Cache API 캐시로 |
| GitHub PUT 파이프라인 | **쉬움** | requests→fetch, 데몬 스레드(:84)→`ctx.waitUntil()`. sha 조회→PUT→409 재시도(:44-54) 로직 그대로 포팅 |
| 챔프 버튼·픽 진행 | **중간** | py-cord는 메모리 View 객체로 버튼 콜백을 라우팅하는데 HTTP에는 그게 없다. **모든 버튼/셀렉트에 의미 있는 custom_id 설계 필수** (예: `pick:<gameId>:<champ>`). 현재는 StartButton(:506) 빼고 custom_id가 없음(:587, :950-955) |
| 3채널 브로드캐스트 | **중간** | interaction 응답은 1개뿐. 나머지 채널은 Bot 토큰으로 REST(`POST /channels/{id}/messages`). 3초 응답 제한 → defer 후 waitUntil로 후속 전송 |
| 게임 진행 상태 | **어려움** | 전역 변수 15개(:58-75)가 프로세스 메모리에 있음 → **처음부터 Durable Object로 외부화** (2026-08-26 결정, 5절 참조). 게임당 DO 인스턴스 1개에 상태 JSON |
| 20초 픽 타이머(1초 틱 edit) | **어려움** | Workers엔 상주 asyncio 루프가 없음(:353-491). **권장: 타이머 표시를 디스코드 내장 상대시각 `<t:유닉스초:R>`로 바꾸면 서버 틱 자체가 불필요** (embed를 매초 edit할 이유가 사라짐). 자동 랜덤픽 마감 처리만 Durable Object Alarm 1발로 |
| `/게임시작`의 온라인 유저 자동 감지 | **대체 불가** | `member.status != offline`(:820-824)은 presence 게이트웨이 캐시 전용 — HTTP Interactions에는 presence가 **존재하지 않는다**. 재설계 필수 → 4절 |

### 놓치기 쉬운 포인트 2개
- **시즌 판정이 암묵 결합**: round 번호가 직전 기록 이하로 회귀하면 season+1 (game_recorder.py:115-120). wins 리셋 = 시즌 시작 신호. 이 로직을 반드시 같이 옮길 것.
- `unicodedata.east_asian_width`로 한글 폭 계산(:254-262) — JS에 직접 대응이 없다. 직접 구현하거나 정렬 포기.

## 4. 재설계 결정 필요 (사용자와 상의)

`/게임시작`의 6명 선발을 어떻게 할지. 후보는 세 가지다.

1. **참가 버튼 방식 (권장)** — `/게임시작` → "참가" 버튼 embed → 6명 누르면 자동 시작. presence 불필요, 오프라인 유저 오탐도 없어져 오히려 개선
2. 커맨드 인자로 6명 멘션 — `/게임시작 @a @b @c @d @e @f`. 단순하지만 입력이 귀찮음
3. 고정 멤버 6명 하드코딩 — 유연성 없음

또 하나: **오늘의 세션 전적(`overall_results`, :64)은 지금도 재시작하면 소실**되는 메모리 상태다. 이식하면서 KV에 남길지(개선), 지금처럼 버릴지 결정.

## 5. 목표 아키텍처

```
디스코드 유저 → 슬래시커맨드/버튼
  → 디스코드 서버가 Worker URL로 POST (Ed25519 서명 첨부)
  → Worker: 서명 검증 → interaction 라우팅(custom_id 기준)
      ├─ 게임 진행 상태: Durable Object (게임당 1개, 요청 직렬화)
      ├─ 저빈도 데이터: KV (wins, config, 챔프 캐시)
      ├─ 채널 전송/수정: 디스코드 REST API (Bot 토큰, waitUntil)
      ├─ 챔프 목록: Data Dragon fetch (KV 캐시)
      └─ 승리 확정 시: history_data.json KV 갱신 + GitHub PUT
                        → lol_arena repo 커밋 → (Pages가 자동 재배포)
```

- **봇→lol_arena 파이프라인은 무변경으로 유효** — 봇의 역할은 "repo에 커밋"까지고, 대시보드가 GitHub Pages든 Cloudflare Pages든 repo를 보고 배포하는 구조라 봇 코드와 무관 (검증됨: 로컬 두 파일 크기 일치 155,199B)
- **게임 진행 상태는 처음부터 Durable Object로** (2026-08-26 결정): 현 파이썬 봇에서 연타/중복 클릭으로 상태가 꼬이는 문제가 실제로 빈발했음 (시즌1 R119/R126 유령 라운드, 141판 카운터 어긋남이 모두 중복 클릭 산물 — CLAUDE.md). DO는 게임당 인스턴스 1개가 모든 클릭을 직렬 처리하므로 경합을 원천 차단. 픽 마감(20초) 자동 랜덤픽도 같은 DO의 Alarm으로 해결. 무료 플랜에서도 DO(SQLite-backed) 사용 가능
- **DO 직렬화 + 멱등 처리는 세트**: DO는 동시 처리만 막아줄 뿐, 줄 서서 들어온 두 번째 클릭의 무시는 앱 로직 몫. 이미 픽된 챔프·이미 확정된 승리의 재클릭은 상태 검사로 거부할 것
- wins·챔프 캐시 등 게임 진행과 무관한 저빈도 데이터는 KV로 충분

## 6. Cloudflare에 올리는 절차 (구체)

### 6-1. 디스코드 개발자 포털 (https://discord.com/developers/applications)
1. 기존 앱 선택 → **General Information** 탭에서 `PUBLIC KEY` 복사 (서명 검증에 필요, 비밀 아님)
2. 같은 탭의 **INTERACTIONS ENDPOINT URL** — 여기에 Worker URL을 넣는다. **저장 버튼을 누르는 순간 디스코드가 검증 PING을 쏘므로, 서명 검증+PING 응답이 구현된 Worker를 먼저 배포한 뒤에 입력해야 한다** (순서 중요)
3. **Bot** 탭 — 기존 `DISCORD_TOKEN` 그대로 사용 (REST 전송용). privileged intents(Presence/Members, got_champe.py:25-26)는 이식 후 필요 없어지므로 꺼도 됨
4. 슬래시 커맨드 등록: 게이트웨이의 `bot.sync_commands()`(:1199)가 사라지므로, 커맨드 정의 JSON을 `PUT /applications/{appId}/guilds/{guildId}/commands`로 1회 등록하는 스크립트를 만든다 (로컬에서 실행, 커맨드 바뀔 때만)

### 6-2. Worker 생성·배포 — 두 가지 방법
- **방법 A. Git 연동 (권장 — finance Pages와 같은 흐름)**: Cloudflare 대시보드 → **Workers & Pages → Create → Workers → Connect to Git** → `HANSOLJJ/lol_discord_bot` 선택. main push마다 자동 배포. repo에 `wrangler.toml`(이름·main 파일·KV 바인딩 선언) 필요
- **방법 B. CLI**: `npx wrangler deploy` (로컬에서 수동 배포. 처음 검증 땐 이게 빠름 — `wrangler dev`로 로컬 테스트도 가능)

### 6-3. 저장소·비밀 설정
- KV namespace 생성: 대시보드 **Storage & Databases → KV** → 생성 후 `wrangler.toml`에 바인딩 (finance의 KV 바인딩과 동일 개념)
- DO 바인딩: `wrangler.toml`에 `durable_objects` 바인딩 + `migrations` 선언 (무료 플랜은 `new_sqlite_classes` 사용). KV처럼 대시보드에서 미리 만드는 게 아니라 코드의 클래스 선언 + 배포로 생성됨
- 비밀 3개 이전: `DISCORD_TOKEN`, `DISCORD_PUBLIC_KEY`(비밀 아니지만 같이), `ARENA_GH_TOKEN` → `npx wrangler secret put <이름>` 또는 대시보드 Worker → Settings → Variables and Secrets. **코드/커밋에 절대 넣지 않는다**
- `config.json`·초기 wins 데이터는 KV에 시딩 (일회성 스크립트)

### 6-4. Worker 코드 골격
1. `POST /` 수신 → `X-Signature-Ed25519`/`X-Signature-Timestamp` 헤더를 PUBLIC KEY로 검증 (crypto.subtle — finance functions/_lib/access.js의 RS256 검증과 같은 패턴, 알고리즘만 Ed25519)
2. `type:1`(PING) → `{type:1}`(PONG) 응답 — 포털 URL 등록 검증용
3. `type:2`(슬래시커맨드)/`type:3`(컴포넌트) → 이름/custom_id로 라우팅
4. 3초 내 응답 못 하는 작업(3채널 전송, GitHub PUT)은 defer 응답(`type:5`) 후 `ctx.waitUntil()`에서 REST로 마무리

## 7. 마이그레이션 순서 (커밋 단위 제안)

1. **뼈대**: 서명 검증 + PING 응답 + `/누적결과` (KV wins 읽기) → 포털에 URL 등록, 첫 동작 확인
2. 커맨드 등록 스크립트 + `/승리` (드롭다운 custom_id 설계, KV 기록, GitHub PUT waitUntil)
3. `/게임시작` — 참가 방식 재설계(4절 결정 먼저) + **게임 상태 DO 도입** + 팀 배정·픽순·챔프 8개 로직 JS 포팅(순수 함수라 그대로 옮기면 됨, :189-301)
4. 픽 버튼 진행 + `<t:...:R>` 타이머 + DO Alarm 마감(자동 랜덤픽)
5. 파이썬 봇 종료·README 갱신. `parse_all_history.py`(재해복구 풀스캔)는 게이트웨이 읽기 전용이라 **로컬 파이썬으로 남겨둔다** (상시 실행 아님, 필요할 때만)

## 8. 검증

- 각 단계마다 DEV 서버(디스코드 테스트 서버)에서 실커맨드 확인 — `DEV_MODE` 개념은 KV 키 분리(`wins_dev` 등)로 유지
- GitHub PUT은 dev 모드에서 스킵하는 현재 동작(game_recorder.py:81-82) 유지
- 최종: 실서버에서 한 판 돌리고 → lol_arena 대시보드에 기록 반영 확인

## 9. 주의 — lol_arena 로컬 clone이 낡음

로컬 `lol_arena`는 2026-07-20 시점이고 `CNAME=arena.dcom.co.kr`(GitHub Pages 흔적)이 남아 있다. 실제로는 2026-08-25에 Cloudflare Pages(arena.hansoljj.com)로 이관 완료됐다 (finance 프로젝트 context-notes 기준). **lol_arena 작업 전 `git pull` 먼저.** 어느 쪽이든 봇의 GitHub PUT 파이프라인은 무변경.
