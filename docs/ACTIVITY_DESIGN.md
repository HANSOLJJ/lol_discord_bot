# 설계: 챔피언 픽 화면을 디스코드 액티비티로

작성: 2026-09-28. 배경과 지금까지의 시도는 [ACTIVITY_HANDOVER.md](ACTIVITY_HANDOVER.md)에 있다. 이 문서는 사용자와 확정한
결정과, 그 결정대로 구현하는 방법을 적는다. 진행 체크리스트와 작업 중 결정 기록은 `.agents/plans/activity-pick/`에 둔다.

## 1. 확정된 결정

| 항목 | 결정 | 이유 |
|---|---|---|
| 픽 화면 | 디스코드 액티비티(Embedded App SDK) | 메시지 편집으로 초를 세는 한 디스코드가 편집을 붙잡는 지연(② 구간)을 없앨 수 없다 |
| 픽 서버 | **기존 봇 프로세스에 aiohttp 웹소켓 서버 추가** (맥미니) | 게임 상태·`pick_lock`·자동 배정·기록이 한 프로세스에 그대로 있다. aiohttp는 py-cord 의존성으로 이미 설치돼 있다(3.14.3) |
| 서버 공개 | 맥미니의 기존 `finance` 터널에 `pick.hansoljj.com` ingress 추가 | 터널·launchd 등록이 이미 돼 있다. finance가 Cloudflare 계산 계층을 떠나 같은 구조(맥미니 + Tunnel)로 정착했다 |
| 화면 호스팅 | `arena.hansoljj.com/pick/` (lol_arena repo, Cloudflare Pages) | 대시보드와 같은 배포 경로. URL Mapping target은 경로가 붙은 디렉터리를 허용한다 |
| 프론트 | Vite + `@discord/embedded-app-sdk` | 사용자 결정 |
| 채널 embed | **픽 현황판만 유지** (카운트다운 편집 없음, 버튼 없음) + 전환 기간에는 구 방식 스위치 | 액티비티를 안 켠 사람도 진행을 본다. 편집이 판당 7~8회로 줄어 지연·rate limit 문제가 없다 |
| 자동 기동 | pm2(이미 launchd에 등록됨)로 봇 실행, tmux 수동 실행 폐기 | 2026-09-28 맥미니 재부팅 뒤 봇이 꺼진 채 발견됐다 |
| 개발 환경 | dev 전용 디스코드 앱 `롤랜덤챔프봇-dev` (TEST2 전용, 9절) | URL Mapping이 앱마다 한 벌이라 운영 앱으로 개발하면 운영 주소를 바꿔야 한다 |

검토하고 버린 안은 context-notes에 이유와 함께 남겼다(Worker+DO 분업, 전면 Workers 이식, VPS, 디스코드 API 경유 동기화).

## 2. 전체 구조

```text
[디스코드 앱 6명]  ── 액티비티 iframe (https://<앱ID>.discordsays.com)
      │ 모든 요청은 디스코드 프록시를 거친다 (URL Mapping)
      ├ /pick-api/*  →  pick.hansoljj.com  →  finance 터널  →  맥미니 127.0.0.1:8790
      │                                                         got_champe.py 안의 aiohttp
      │                                                         ├ POST /pick-api/token  (OAuth code 교환)
      │                                                         └ GET  /pick-api/ws     (웹소켓)
      ├ /ddragon/*   →  ddragon.leagueoflegends.com                (챔피언 이미지)
      └ /            →  arena.hansoljj.com/pick                    (Vite 빌드 결과, 정적)

[봇 게이트웨이]  /게임시작 · /승리 · 채널 embed(현황판) — 지금과 같다
```

URL Mapping은 긴 prefix를 먼저 둔다(`/pick-api`, `/ddragon`, 마지막에 `/`).

## 3. 카운트다운과 판정

핵심은 **숫자 하나하나가 네트워크를 타지 않게** 하는 것이다. 네트워크는 시작 시 시계 맞추기와 상태 변경 알림에만 쓴다.

### 3-1. 서버 (봇)

- 차례가 시작되면 마감 시각을 **미리 확정**한다: `deadline = time.time() + pick_timeout`. 지금은 카운트 중 `inf`였다가
  0에 닿는 순간 확정하지만(편집 박자로 표시 시간이 늘어나기 때문), 액티비티 모드에서는 표시가 실제 시간과 같으므로 처음부터 정한다.
- 타이머 태스크는 `deadline + pick_grace_seconds`까지 한 번 잠든 뒤 지금과 같은 락 안 자동 배정 코드를 실행한다. 칸 단위 루프가 없다.
- 자동 시작도 같다: `start_at = time.time() + auto_start_seconds`를 방송하고 한 번 잠든다.
- **클릭 시각 판정**: 액티비티 클릭에는 스노플레이크가 없으므로 서버가 웹소켓 메시지를 받은 시각(`time.time()`)으로 판정한다.
  `received_at <= deadline + pick_grace_seconds`면 인정한다. 유예가 네트워크 지연(실측 예정, 예상 0.2~0.3초)을 흡수한다.
- 맥미니 시계는 macOS NTP로 동기화돼 있다(HTTP Date 대조 +0.08초, COUNTDOWN_ANALYSIS.md).

### 3-2. 클라이언트 (액티비티)

- **시계 차이(offset) 측정**: 웹소켓 연결 직후 `ping`을 5회 보낸다. 각 응답에서
  `rtt = t_recv - t_send`, `offset = server_ms - (t_send + t_recv) / 2`를 구하고, **rtt가 가장 작은 샘플의 offset**을 쓴다.
  30초마다 1회씩 다시 재서 갱신한다. 오차는 최대 rtt/2(약 0.15초)라 초 단위 표시에는 보이지 않는다.
- 표시: `remaining = ceil((deadline_ms - (Date.now() + offset)) / 1000)`을 `requestAnimationFrame`으로 다시 그린다.
  0 이하가 되면 "마감 확인 중…"을 띄우고 서버의 다음 상태를 기다린다(서버가 판정한다).
- 연결이 끊겨도 카운트다운은 계속 돈다(마감 시각을 이미 알고 있다). 끊김 배지를 띄우고 0.5 → 1 → 2 → 5초 간격으로 재접속한다.
  재접속하면 서버가 전체 상태를 다시 보낸다.

## 4. 웹소켓 프로토콜

전부 JSON 텍스트 메시지. 시각은 유닉스 밀리초.

### 서버 → 클라이언트

```jsonc
// 상태가 바뀔 때마다 전체 스냅샷을 보낸다 (6명·8챔프라 작다. diff를 만들지 않는다)
{
  "t": "state",
  "game_id": 12, "round": 37,
  "phase": "none" | "starting" | "picking" | "done",
  "start_at": 1790000000000,          // phase=starting일 때
  "deadline": 1790000020000,          // phase=picking일 때 현재 차례 마감
  "grace_ms": 2000,
  "players": [{"id": "123", "name": "표시이름", "avatar": "URL", "team": "team1", "wins": 5}],
  "pick_order": ["123", "456", ...],
  "current_index": 2,
  "champions": [{"name": "아리", "image": "/ddragon/cdn/<ver>/img/champion/Ahri.png"}],
  "selections": {"123": "아리"},
  "auto_assigned": ["456"]
}
{ "t": "pong", "c": <클라이언트가 보낸 값>, "s": <서버 시각> }
{ "t": "reply", "ok": true, "msg": "🔵 **아리** 선택 완료!" }   // 내 pick 요청에 대한 응답 (토스트)
```

- 이미지 URL은 Data Dragon 절대 주소를 `/ddragon/...` 상대 경로로 바꿔 보낸다(액티비티는 매핑 밖 외부 요청이 막힌다).
- 사용자 id는 JS 정수 범위를 넘으므로 **문자열**로 보낸다.

### 클라이언트 → 서버

```jsonc
{ "t": "ping", "c": 1790000000123 }
{ "t": "pick", "champ": "아리", "game_id": 12 }   // game_id가 현재와 다르면 거절 ("이전 게임")
```

재클릭 = 선택 취소 규칙은 지금과 같다(같은 챔프를 다시 pick).

## 5. 인증: 누가 누구인가

1. 클라이언트: `discordSdk.ready()` → `commands.authorize({client_id, response_type: "code", scope: ["identify"], prompt: "none"})` → `code`
2. `POST /pick-api/token {code}` → 서버가 `https://discord.com/api/oauth2/token`에 client_id·**client_secret**·code로 교환 →
   `GET /users/@me`로 사용자 id 확인 → 임의의 세션 토큰을 만들어 메모리 dict(`session → user_id`)에 저장 → `{access_token, session}` 응답
3. 클라이언트: `commands.authenticate({access_token})` (SDK 기능용) → `wss://<host>/pick-api/ws?session=...` 접속
4. 서버: 세션이 없으면 4401로 닫는다. pick은 세션의 user_id가 현재 차례일 때만 인정한다(DEV_MODE는 지금처럼 턴 검사 생략)

- 세션은 봇 재시작 시 사라진다. 클라이언트는 4401을 받으면 1번부터 다시 한다(`prompt: "none"`이라 화면 확인 없이 통과).
- 교환 HTTP 호출은 `requests`(동기)가 아니라 aiohttp `ClientSession`으로 한다. 이벤트 루프를 막지 않기 위해서다.
- `pick.hansoljj.com`은 인터넷에 공개된 주소지만, 세션 없이 할 수 있는 일은 없다. **Cloudflare Access는 붙이지 않는다**
  (디스코드 프록시가 Access 로그인을 통과하지 못한다).

## 6. 봇 코드 변경 (lol_discord_bot)

### 6-1. 새 모듈 `activity_server.py`

aiohttp 앱과 웹소켓 허브만 담는다. 게임 상태는 모른다(순환 import 방지).

- `start(port, get_snapshot, on_pick)`: `AppRunner`로 `127.0.0.1:<port>`에 바인드. 외부 노출은 터널 경로뿐이다
- `broadcast(snapshot)`: 연결된 모든 소켓에 `state` 전송. 느린 소켓 하나가 나머지를 막지 않게 소켓별 `send`를 `gather`로 보낸다
- `/pick-api/token`, `/pick-api/ws` 핸들러, 세션 dict, ping/pong
- 포트는 env `ACTIVITY_PORT`(기본 8790, finance는 8787)

### 6-2. `got_champe.py`

1. **실행 구조**: `bot.run(token)`을 `asyncio.run(main())`으로 바꾸고, `main()`에서 `activity_server.start(...)` 후 `await bot.start(token)`.
   `on_ready`에 두지 않는 이유: 게이트웨이 재접속마다 다시 불린다.
2. **픽 처리 분리**: `ChampionButton.callback`의 락 안 판단·변경 코드를 `apply_pick(user_id, champ_name, received_at)`로 뽑는다.
   반환 `(result, reply, all_picked)`. 버튼 콜백(구 방식)과 웹소켓 `on_pick`(액티비티)이 같은 함수를 쓴다. 이 단계는 동작 변화 없음.
3. **모드 스위치**: `config.json`의 `"pick_ui": "activity" | "embed"`(기본 `"embed"`로 시작해 검증 후 전환).
   - `embed`: 지금 코드 그대로 (카운트다운 편집 포함)
   - `activity`: 3절의 선계산 마감 타이머, 챔프 버튼 없는 현황판 embed, 상태 변경 시 `broadcast`
4. **현황판 embed (activity 모드)**: 팀 구성은 지금처럼. 챔피언 메시지는 버튼 대신 챔프 이름 목록 + "🎮 픽 화면 열기" 버튼 1개.
   description은 초를 쓰지 않는다: "🚀 곧 시작 (@첫 픽)" → "현재 차례 - @X" → "✅ 모든 선택 완료!". 필드 0은 기존 `get_selection_status()`.
   편집은 차례가 바뀔 때만 하므로 기존 coalescing 파이프라인(`request_embed_update`)을 그대로 쓴다.
5. **"픽 화면 열기" 버튼**: 인터랙션 응답 type 12(`LAUNCH_ACTIVITY`). py-cord 2.8.1에는 이 응답 함수가 없으므로
   `POST /interactions/{id}/{token}/callback {"type": 12}`를 `bot.http`로 직접 보낸다. 액티비티를 켜는 다른 길(음성 채널 로켓 아이콘)도 그대로 된다.
6. **상태 변경 지점마다 broadcast**: `/게임시작`(starting), `begin_champion_select`(picking), 픽·취소·자동 배정(picking/done).
   락 안에서 스냅샷을 만들고 전송은 락 밖에서 한다(지금의 "통신은 락 밖" 원칙과 같다).
7. `/승리`·기록·GitHub PUT은 무변경.

### 6-3. `.env` 추가

| 키 | 비밀 | 용도 |
|---|---|---|
| `DISCORD_CLIENT_ID` | 아님 | OAuth 교환 |
| `DISCORD_CLIENT_SECRET` | **비밀** | OAuth 교환. 커밋·로그 금지 |
| `ACTIVITY_PORT` | 아님 | 기본 8790 |

`.env.example`에 키만 추가한다.

## 7. 프론트 (lol_arena repo)

- 소스 `lol_arena/activity/` (Vite 프로젝트, `node_modules/`는 gitignore) → 빌드 결과 `lol_arena/pick/`에 커밋.
  Cloudflare Pages 설정은 바꾸지 않는다(빌드 단계 없음, 저장소 루트를 그대로 서빙). `package.json`이 루트가 아니라
  `activity/` 안에 있어서 Pages가 의존성 설치를 시도하지 않는다(finance에서 겪은 `node_modules` 노출 문제 회피).
- `vite.config`: `base: "./"`(디스코드 안에서는 `/`, 직접 열면 `/pick/`이라 상대 경로여야 둘 다 된다), `build.outDir: "../pick"`.
  개발 서버는 `/pick-api`를 `http://127.0.0.1:8790`으로 proxy한다(개발 때 터널 하나로 끝나게).
- client id는 공개값이라 `activity/.env.development`·`.env.production`에 `VITE_DISCORD_CLIENT_ID`로 커밋한다(dev 앱과 운영 앱이 다르다, 9절).
- 외부 패키지: `vite`, `@discord/embedded-app-sdk` 두 개만. 프레임워크(React 등) 없이 바닐라 JS로 시작한다.
- 화면 구성 (위에서 아래로, 모바일 세로 우선)
  1. 큰 카운트다운 + 현재 차례 이름 (내 차례면 강조)
  2. 챔프 8개 그리드 (이미지 + 이름, 고른 챔프는 팀 색 테두리와 고른 사람 이름, 내 차례가 아니면 비활성)
  3. 팀별 선택 현황 (픽순 번호, 승수, 고른 챔프, 자동 배정 표시)
  4. 토스트 (서버 `reply`), 연결 끊김 배지
- 디스코드 밖에서 직접 열면(`frame_id` 쿼리 없음) "디스코드에서 열어주세요" 안내만 띄운다.

## 8. 맥미니 운영

### 8-1. 자동 기동 (pm2): 액티비티와 무관하게 먼저 한다

`lol_discord_bot/ecosystem.config.cjs` (커밋):

```js
module.exports = {
  apps: [{
    name: 'lol',
    script: 'uv',
    args: 'run python -u got_champe.py',
    interpreter: 'none',
    cwd: __dirname,
    autorestart: true,
    restart_delay: 5000,
    max_restarts: 20,
    kill_timeout: 5000,
    time: true,
  }],
};
```

- `.env`는 코드의 `load_dotenv()`가 cwd에서 읽으므로 pm2에 비밀을 넣지 않는다.
- 절차: tmux 세션 종료 확인 → `pm2 start ecosystem.config.cjs` → `pm2 save`. pm2 자체는 이미 `pm2.hansol.plist`(launchd)로 부팅 시 뜬다
  (자동 로그인 `hansol` 전제, finance handover 12절).
- pm2의 PATH에 `/opt/homebrew/bin`(uv)이 없으면 `script`를 절대 경로 `/opt/homebrew/bin/uv`로 쓴다. 실제 기동에서 확인.
- 확인: `pm2 restart lol`로 정상 종료·재기동 → 재부팅 테스트(`finance`와 함께 복귀하는지).
- 로그: `pm2 logs lol`. 기존 `logs/` 폴더 사용 방식은 바꾸지 않는다.

### 8-2. 터널

`~/.cloudflared/config.yml`의 404 규칙 **앞에** 추가:

```yaml
  - hostname: pick.hansoljj.com
    service: http://127.0.0.1:8790
```

→ `cloudflared tunnel route dns finance pick.hansoljj.com` → `launchctl kickstart -k gui/$(id -u)/com.cloudflare.cloudflared`.
재시작하는 몇 초 동안 fin.hansoljj.com도 끊긴다. cloudflared 2026.8.2는 구버전 경고가 뜨지만 이번 범위에서 올리지 않는다.
웹소켓은 Tunnel이 별도 설정 없이 통과시킨다.

## 9. 개발·테스트 환경: dev 앱

### 9-1. 왜 앱을 하나 더 만드나

디스코드 개발자 포털의 "앱"은 봇 계정 그 자체다(지금은 롤랜덤챔프봇 하나). 봇 토큰도, 액티비티가 띄울 웹 주소(URL Mapping)도 이 앱에 붙는다.
URL Mapping은 앱마다 한 벌이다. 운영은 `arena.hansoljj.com/pick`을, 개발은 윈도우 PC의 개발 서버를 띄워야 하므로 앱이 하나면
개발할 때마다 운영 주소를 바꿨다가 되돌려야 하고, 그 사이 친구들이 켜면 개발 중인 화면(또는 빈 화면)을 보게 된다.

그래서 **dev 앱 `롤랜덤챔프봇-dev`를 따로 만들어 TEST2 서버에만 초대한다**(2026-09-28 결정). 이렇게 하면 다음과 같이 분리된다.

| | 운영 앱 (롤랜덤챔프봇) | dev 앱 (롤랜덤챔프봇-dev) |
|---|---|---|
| 초대된 서버 | 실서버 | TEST2만 |
| 봇 실행 위치 | 맥미니 (pm2) | 윈도우 PC (필요할 때만) |
| `.env` | 맥미니 `.env`: 운영 토큰·client id·secret, `DEV_MODE=false` | 윈도우 `.env`: dev 토큰·client id·secret, `DEV_MODE=true` |
| URL Mapping `/` | `arena.hansoljj.com/pick` | 개발 세션마다 바뀌는 quick tunnel 주소 |
| URL Mapping `/pick-api` | `pick.hansoljj.com/pick-api` | 없음 (Vite 개발 서버가 8790으로 proxy) |
| 프론트 client id | `activity/.env.production` | `activity/.env.development` |

덤으로, 윈도우에서 봇을 켜도 운영 봇과 토큰이 달라서 같은 클릭을 두 봇이 받는 일이 없다.

### 9-2. dev 앱 만들기 (사용자, 1회)

<https://discord.com/developers/applications> 에서 진행한다.

1. **New Application** → 이름 `롤랜덤챔프봇-dev`
2. **Bot** 탭
   - Reset Token → 토큰을 윈도우 `.env`의 `DISCORD_TOKEN`에 넣는다(운영 토큰은 윈도우에서 뺀다)
   - Privileged Gateway Intents: **Presence Intent**, **Server Members Intent** 켜기 (`got_champe.py:36-37`이 요구)
3. **OAuth2** 탭
   - Client ID → `.env`의 `DISCORD_CLIENT_ID`, `activity/.env.development`의 `VITE_DISCORD_CLIENT_ID`
   - Reset Secret → `.env`의 `DISCORD_CLIENT_SECRET` (커밋·로그 금지)
   - Redirects에 `https://127.0.0.1` 추가 (액티비티 OAuth는 이 값을 쓰지 않지만 등록된 redirect가 하나는 있어야 한다)
4. **OAuth2 → URL Generator**: scopes `bot` + `applications.commands`, 권한은 운영 봇과 같게
   (View Channels, Send Messages, Embed Links, Read Message History) → 생성된 링크로 **TEST2 서버에 초대**
5. **Activities → Settings**: Enable Activities, 지원 플랫폼 Web·iOS·Android 체크
6. **Activities → URL Mappings**: 아래 순서로 등록(긴 prefix가 먼저)

   | PREFIX | TARGET |
   |---|---|
   | `/ddragon` | `ddragon.leagueoflegends.com` |
   | `/` | (9-3에서 받은 quick tunnel 주소, 프로토콜 없이) |

7. TEST2 서버에 `config.json`의 채널(`팀짜기`, `TEAM1`, `TEAM2`)이 있는지 확인한다. 없으면 봇이 "설정된 채널을 찾을 수 없습니다"로 멈춘다

### 9-3. 개발 세션 순서 (윈도우)

1. 봇: `uv run python -u got_champe.py` (dev 토큰, `DEV_MODE=true`, 웹소켓 :8790)
2. 프론트: `lol_arena/activity`에서 `npm run dev` (:5173). `vite.config`에 아래 설정을 둔다
   - `server.proxy`: `/pick-api` → `http://127.0.0.1:8790` (`ws: true`)
   - `server.allowedHosts`: `['.trycloudflare.com']` (Vite가 모르는 호스트 요청을 거부하므로)
   - `server.hmr.clientPort: 443` (디스코드 프록시 뒤에서 HMR 웹소켓이 443으로 붙게)
3. 터널: `cloudflared tunnel --url http://localhost:5173` → 출력된 `https://xxxx.trycloudflare.com`을 dev 앱 URL Mapping `/`에 넣는다.
   quick tunnel 주소는 실행할 때마다 바뀌므로 매 세션 갱신한다. **윈도우에 cloudflared가 아직 없다(2026-09-28 확인) → 설치는 사용자 승인 후**
4. TEST2에서 `/게임시작` → "픽 화면 열기" 또는 음성 채널 로켓 아이콘으로 액티비티 실행

DEV_MODE에서는 가상 유저 6명(`wins_dev.json`)으로 게임이 만들어지고 턴 검사를 건너뛴다. 그래서 인증된 사람 한 명이 6명 차례를 모두 고를 수 있다.
판 기록의 GitHub PUT도 dev에서는 건너뛴다(`game_recorder`의 기존 동작). 다른 기기(모바일) 확인은 같은 계정으로 TEST2에 들어가 액티비티를 켜면 된다.

### 9-4. 봇 로직 테스트

지금처럼 저장소 밖(`e:\tmp`)의 exec 방식 스크립트로 한다. `apply_pick` 분리 전후로 같은 결과인지 확인한다.

## 10. 구현 순서 (커밋 단위)

각 단계는 검증을 통과해야 다음으로 간다.

| # | 단위 | repo | 검증 |
|---|---|---|---|
| 0 | pm2 자동 기동 (`ecosystem.config.cjs`) | bot | 맥미니 `pm2 restart lol` 정상, 재부팅 후 자동 복귀 |
| 1 | **측정용 골격**: `activity_server.py`(token·ws·ping만) + Vite 골격(SDK ready → 인증 → ping 100회 RTT 표시) | 양쪽 | dev 앱으로 PC·모바일에서 RTT 분포 기록. **p95가 1초를 넘으면 멈추고 서버 위치·유예를 재검토** |
| 2 | `apply_pick` 분리 (동작 변화 없음) | bot | exec 테스트 + DEV 서버 embed 모드 한 판 |
| 3 | activity 모드 서버: `pick_ui` 스위치, 선계산 마감 타이머, 상태 broadcast, ws pick, 현황판 embed, LAUNCH_ACTIVITY 버튼 | bot | DEV 서버에서 wscat 등으로 pick·마감·자동 배정·재클릭 취소·이전 게임 거절 |
| 4 | 액티비티 화면 (7절) | lol_arena | dev 앱으로 한 판: 6명 역할을 DEV_MODE로, 카운트다운이 끊김 없이 20→0, 재접속 시 상태 복구 |
| 5 | 운영 전환: 운영 앱 Activities 활성화·URL Mapping·OAuth redirect, 터널 ingress·DNS, `.env` 비밀, `pick_ui: "activity"` | 운영 | 실전 한 판 → 대시보드 기록 반영 |
| 6 | 안정화 후 정리: 구 카운트다운 코드와 `pick_ui` 스위치 삭제, CLAUDE.md·README·AGENTS.md 갱신 | bot | 사용자가 정리 시점 결정 |

## 11. 디스코드 개발자 포털 작업 (사용자)

dev 앱은 9-2절 절차로 1단계 전에 만든다. 운영 앱(롤랜덤챔프봇)은 5단계(운영 전환)에서 아래를 한다.

1. **Activities → Settings**: Activities 활성화 (지원 플랫폼 Web·iOS·Android)
2. **Activities → URL Mappings**: 위에서부터 `/pick-api` = `pick.hansoljj.com/pick-api`, `/ddragon` = `ddragon.leagueoflegends.com`, `/` = `arena.hansoljj.com/pick`
3. **OAuth2**: Redirects에 자리표시자 `https://127.0.0.1` 추가, Client Secret 발급 → 맥미니 `.env`
4. 액티비티를 켜면 디스코드가 Entry Point 커맨드(앱 이름으로 된 "실행" 커맨드)를 자동으로 만든다. 기존 슬래시 커맨드 동기화(`bot.sync_commands()`)가 이것을 지우지 않는지 1단계에서 확인한다

## 12. 위험과 확인할 것

- **디스코드 프록시 → 우리 서버 경로의 지연**: 밖에서 못 잰다. 1단계에서 실측(게이트). 참고로 이 PC에서 우리 존(arena·fin)은 SJC 엣지, discordsays.com은 ICN 엣지로 붙는다. 맥미니 터널은 ICN에 연결돼 있다
- **텍스트 채널(팀짜기, 음성 채널 채팅)에서 LAUNCH_ACTIVITY가 되는지**: 1단계에서 확인. 안 되면 음성 채널 로켓 아이콘으로 켜는 안내로 대체
- **Entry Point 커맨드와 `sync_commands()` 충돌 여부**: 11절 4번
- **맥미니 네트워크 끊김**: 카운트다운 표시는 영향 없음. 끊긴 동안의 클릭은 늦게 도착하고, 유예를 넘기면 자동 배정된다
- **cloudflared 재시작 시 finance 순단**: 8-2. 작업 시각을 사용자와 맞춘다
- **세션 토큰이 메모리에만 있다**: 봇 재시작 시 클라이언트가 자동 재인증(5절)
