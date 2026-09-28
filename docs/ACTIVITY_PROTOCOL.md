# 액티비티 통신 규격 (protocol_version 2)

봇의 액티비티 서버(`lol_discord_bot/activity_server.py`)와 액티비티 프론트(`lol_arena/activity/`)가 주고받는 HTTP·WebSocket 형식을 고정하는 문서다.
설계 이유와 전체 흐름은 [통합 실행 계획](../.agents/plans/activity-integration/plan.md) 5~7절에 있고, 이 문서는 양쪽 구현이 똑같이 맞춰야 하는 형식만 정한다.
형식을 바꿀 때는 이 문서를 먼저 고치고 `protocol_version`을 올린다.

## 1. 범위와 버전

v1(1단계)은 토큰 교환, 세션, WebSocket 연결, ping/pong, 상태 스냅샷, 개발용 데모 카운트다운이었다. v2(2026-09-28 확정)는 여기에 실제 게임 상태, 새 판 시작, 픽, 승리 팀 입력, 번복을 더했다. v1에서 달라진 점은 다음과 같다.

- `hello`와 `state`의 `protocol_version`이 2가 된다. 클라이언트는 2가 아니면 입력을 막고 새로고침 안내를 보여 준다.
- `state`에 실제 게임 내용(선수, 픽 순서, 챔피언 후보, 선택, 결과)과 내 권한(`me`)이 채워진다(8절).
- 클라이언트 → 서버 메시지에 `start`, `pick`, `result`, `reverse`가 생긴다(9절).
- 개발용 `demo_countdown`은 없어진다. 받으면 모르는 `t`로 보고 `bad_request`로 응답한다. 개발 중 시험은 DEV_MODE의 실제 게임 흐름으로 한다(11절).

## 2. 공통 규칙

- 서버는 `127.0.0.1:{ACTIVITY_PORT}`(기본 8790)에 바인딩하고, 모든 경로는 `/pick-api`로 시작한다.
- 클라이언트는 상대 경로(`/pick-api/...`)로 요청한다. 개발 환경에서는 Vite 프록시가, 운영에서는 Discord URL 매핑이 서버로 전달한다.
- 본문은 모두 UTF-8 JSON이다. 시각은 유닉스 밀리초 정수, Discord ID는 문자열이다.
- 해당 상태에 적용되지 않는 필드도 생략하지 않고 `null`로 보낸다.
- 받는 쪽은 모르는 필드를 무시한다. 필수 필드가 없거나 타입이 다르면 그 메시지를 적용하지 않는다.
- OAuth code, access token, client secret, 세션 토큰은 서버와 클라이언트 어느 쪽에서도 로그에 남기지 않는다. WebSocket 주소의 query 문자열도 로그에 남기지 않는다.

## 3. HTTP: `POST /pick-api/token`

Discord Embedded App SDK의 `commands.authorize`로 받은 code를 access token과 세션으로 바꾼다.

### 요청

```json
{ "code": "<commands.authorize가 돌려준 code>" }
```

- 본문은 4KB 이하이고, `code`는 1~512자 문자열이다.

### 서버 처리

1. `POST https://discord.com/api/oauth2/token`에 form 형식으로 `client_id`, `client_secret`, `grant_type=authorization_code`, `code`를 보낸다. client ID와 secret은 `DEV_MODE=true`면 `DISCORD_CLIENT_ID_DEV`, `DISCORD_CLIENT_SECRET_DEV`, 아니면 `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`를 쓴다.
2. 받은 access token으로 `GET https://discord.com/api/users/@me`를 호출해 사용자 신원을 확인한다.
3. 세션 토큰을 발급한다. URL-safe 난수 32바이트 이상이고, 수명은 발급 시점부터 1시간이며, 서버 메모리에만 보관한다.

### 성공 응답 `200`

```json
{
  "access_token": "<SDK commands.authenticate에 넘길 Discord access token>",
  "session": "<WebSocket 인증용 세션 토큰>",
  "session_expires_ms": 1790000000000,
  "user": {
    "id": "365414320332472332",
    "username": "hansol",
    "global_name": "정한솔",
    "avatar": "a1b2c3"
  }
}
```

- `global_name`과 `avatar`는 Discord가 비워 두면 `null`이다.

### 실패 응답

본문은 `{ "error": "<코드>" }`이다. Discord 응답 원문은 클라이언트에 전달하지 않는다.

| 상태 | `error` | 의미 |
|---|---|---|
| 400 | `bad_request` | 본문이 JSON이 아니거나 크기·형식 규칙 위반 |
| 401 | `oauth_failed` | Discord 토큰 교환 또는 신원 확인 실패. Discord의 오류 응답, Discord로 가는 네트워크 오류와 타임아웃을 모두 포함한다 |
| 429 | `rate_limited` | 요청 빈도 초과. 모든 요청이 Discord 프록시를 거쳐 IP 구분이 의미 없으므로 서버 전체 기준 60초당 30회로 제한한다 |
| 500 | `server_error` | 그 밖의 서버 오류 |

## 4. WebSocket: `GET /pick-api/ws?session=<세션 토큰>`

### 연결과 종료

- 세션이 없거나 만료됐으면 서버는 업그레이드 직후 종료 코드 4401로 닫는다.
- 연결 중에 세션이 만료되면 서버가 4401로 닫는다.
- 연결 직후 서버는 `hello`, `state`를 이 순서로 보낸다.

| 종료 코드 | 의미 | 클라이언트 동작 |
|---|---|---|
| 4401 | 세션 없음·만료, 또는 서버 재시작으로 세션 소실 | 토큰 교환부터 다시 한다 |
| 4400 | 규격 위반 메시지가 연속 3회 | 재접속하지 않고 새로고침 안내를 표시한다 |
| 4408 | 서버가 5초 안에 송신하지 못한 느린 연결 | 재접속한다 |
| 1001 | 서버 종료 | 재접속한다 |

### 요청 ID

클라이언트가 보내는 모든 메시지에는 `id`(1~64자 문자열)가 있고, 서버의 `pong`과 `reply`는 같은 `id`를 돌려준다.

### 클라이언트 → 서버

| `t` | 형식 | 서버 응답 |
|---|---|---|
| `ping` | `{ "t": "ping", "id": "p-3", "c": 12345.67 }` | `pong` |
| `sync` | `{ "t": "sync", "id": "s-1" }` | 현재 `state` |
| `start`, `pick`, `result`, `reverse` | 9절 | `reply`, 상태가 바뀌면 그 전에 `state` |

- `ping`의 `c`는 클라이언트의 `performance.now()` 값이다. 서버는 해석하지 않고 그대로 돌려준다.
- 메시지는 4KB 이하이다. 4KB 초과, JSON 오류, 알 수 없는 `t`, 필드 형식 위반에는 연결을 끊지 않고 `reply`(`ok: false`, `code: "bad_request"`)로 응답하며 위반 1회로 센다. 64KB를 넘는 메시지만 WebSocket 계층에서 1009로 종료된다.


### 서버 → 클라이언트

**hello**

```json
{
  "t": "hello",
  "protocol_version": 2,
  "server_epoch": "4b0e1c9a-6a53-4a0f-9e2b-0d5b8f3c2a11",
  "server_ms": 1790000000000,
  "user": { "id": "365414320332472332", "username": "hansol", "global_name": "정한솔", "avatar": "a1b2c3" }
}
```

- `server_epoch`는 서버 프로세스가 시작될 때마다 새로 만드는 UUID이다. 값이 바뀌면 클라이언트는 이전 상태를 모두 버린다.
- `protocol_version`이 클라이언트와 다르면 클라이언트는 입력을 막고 새로고침(업데이트) 안내를 표시한다.

**pong**

```json
{ "t": "pong", "id": "p-3", "c": 12345.67, "s": 1790000000123 }
```

- `id`와 `c`는 받은 `ping`의 값 그대로이다. `s`는 서버가 이 pong을 만든 순간의 유닉스 밀리초이다.

**state**

형식과 필드 규칙은 8절에 있다. 아래 두 규칙은 v1과 같다.

- `server_ms`와 `deadline_ms`는 서버가 같은 순간에 잡은 시각과 남은 시간으로 계산한다. 서버 내부의 마감 판정은 단조 시계로 한다.
- `state_version`은 서버 프로세스 안에서 상태가 바뀔 때마다 1씩 증가한다. 클라이언트는 같은 `server_epoch`에서 더 작거나 같은 `state_version`을 가진 `state`를 적용하지 않는다. 단, `sync` 응답으로 받은 같은 버전은 적용해도 된다.

**reply**

```json
{ "t": "reply", "id": "k-7", "ok": false, "code": "not_your_turn", "message": "지금은 청명사냥꾼 님의 차례입니다.", "state_version": 41 }
```

- `code`는 기계가 분기할 값이고, `message`는 화면에 보여줄 한국어 문장이다. 성공이면 `ok: true`, `code: "ok"`이다. 코드 목록은 9절에 있다.

## 5. 서버 송신 규칙

- 소켓마다 송신 작업 하나를 두고, 보낼 `state`가 밀리면 가장 최신 것만 보낸다.
- 한 메시지를 5초 안에 보내지 못하면 4408로 닫는다.
- 상태를 만드는 일은 락 안에서, 전송은 락 밖에서 한다.

## 6. 클라이언트 시계 보정 요약

계획 문서 5-2절을 그대로 따른다. 연결 후 `ping`을 5회 보내고, 요청 ID로 짝지은 샘플 가운데 왕복 시간(RTT)이 가장 작은 샘플로 기준점을 잡는다.

```js
// 보정된 서버 시각에 단조 시계의 경과 시간을 더해 남은 시간을 계산한다.
const anchorServerMs = s + (p1 - p0) / 2;
const anchorPerfMs = p1;
const estimatedServerNow = anchorServerMs + (performance.now() - anchorPerfMs);
const remaining = Math.max(0, Math.ceil((deadlineMs - estimatedServerNow) / 1000));
```

여기서 `p0`, `p1`은 ping 송신과 pong 수신 시각의 `performance.now()` 값이고, `s`는 pong의 `s`이다. 전경에서 30초마다, 그리고 `visibilitychange`로 전경에 돌아오거나 재접속할 때 다시 측정한다. 남은 시간이 0이 되면 `마감 확인 중…`을 표시하고 서버의 다음 `state`를 기다린다.

## 7. 게임 진행과 phase

게임은 액티비티의 "게임 시작" 버튼으로 시작한다. 시작부터 결과 입력, 번복까지 모두 액티비티 안에서 한다. 디스코드 `/게임시작`, `/승리`, `/번복`은 예비 경로로 남긴다.

| phase | 언제 | 채워지는 시간·차례 필드 |
|---|---|---|
| `none` | 서버가 켜진 뒤 아직 게임이 없을 때 | 모두 `null`, 목록은 빈 값 |
| `starting` | 게임 시작 직후, 자동 시작 전 | `start_at_ms` |
| `picking` | 픽 진행 중 | `deadline_ms`, `grace_ms`, `turn_id`, `current_index` |
| `awaiting_result` | 6명이 모두 고른 뒤, 승리 팀 입력 전 | 모두 `null` |
| `completed` | 승리 팀이 기록된 뒤, 다음 판 시작 전까지 | 모두 `null`, `result` 채움 |
| `aborted` | v2 서버는 보내지 않는다(예약) | 클라이언트는 `none`처럼 처리한다 |

- `starting`의 길이는 config `auto_start_seconds`(현재 15초)이다. `start_at_ms`가 되면 서버가 `picking`으로 바꾼다. 클라이언트가 먼저 시작시키지 않는다.
- 액티비티의 `start`는 `none`, `awaiting_result`, `completed`에서만 받는다. 픽 도중(`starting`, `picking`)에 실수로 판이 새로 시작되지 않게 하기 위해서이다.
- `completed` 화면은 다음 판을 시작할 때까지 남는다. 그 사이에 번복할 수 있다.
- `awaiting_result`에서 새 판을 시작하면 결과를 입력하지 않은 이전 판은 기록 없이 버려진다. 게임을 중간에 접은 경우를 위한 것이고, 화면에서는 승리 팀 버튼과 떨어진 곳에 "결과 없이 새 판" 버튼으로 둔다.
- 디스코드 `/게임시작`은 지금처럼 언제든 새 판을 시작한다. 픽 도중에 판이 멈추는 등 액티비티로 되돌릴 수 없을 때 쓴다.
- 서버가 재시작되면 진행 중이던 판은 이어지지 않는다. 새 `server_epoch`의 `none`이 온다.

## 8. state

모든 필드는 2절 규칙대로 항상 보낸다. 해당하지 않으면 `null` 또는 빈 값이다. `me`는 받는 사람마다 다르므로 서버는 소켓마다 따로 만든다.

```json
{
  "t": "state",
  "protocol_version": 2,
  "server_epoch": "4b0e1c9a-6a53-4a0f-9e2b-0d5b8f3c2a11",
  "game_id": "g-1790000000000",
  "state_version": 41,
  "phase": "picking",
  "round": 87,
  "season": 2,
  "server_ms": 1790000031000,
  "start_at_ms": null,
  "deadline_ms": 1790000045000,
  "grace_ms": 2000,
  "turn_id": "g-1790000000000:2",
  "current_index": 2,
  "ddragon_version": "15.19.1",
  "players": [
    { "id": "365414320332472332", "name": "정한솔", "team": "team1", "wins": 12 },
    { "id": "111111111111111111", "name": "사무엘", "team": "team1", "wins": 9 },
    { "id": "222222222222222222", "name": "유성호", "team": "team1", "wins": 15 },
    { "id": "333333333333333333", "name": "청명사냥꾼", "team": "team2", "wins": 7 },
    { "id": "444444444444444444", "name": "보링", "team": "team2", "wins": 11 },
    { "id": "555555555555555555", "name": "윤재철", "team": "team2", "wins": 10 }
  ],
  "pick_order": [
    "333333333333333333", "111111111111111111", "555555555555555555",
    "444444444444444444", "365414320332472332", "222222222222222222"
  ],
  "champions": [
    { "id": "Ahri", "name": "아리" },
    { "id": "MonkeyKing", "name": "오공" },
    { "id": "TwistedFate", "name": "트위스티드 페이트" },
    { "id": "Leona", "name": "레오나" },
    { "id": "Zed", "name": "제드" },
    { "id": "Annie", "name": "애니" },
    { "id": "Garen", "name": "가렌" },
    { "id": "Sona", "name": "소나" }
  ],
  "selections": {
    "333333333333333333": "Zed",
    "111111111111111111": "Sona"
  },
  "auto_assigned": ["111111111111111111"],
  "result": null,
  "me": {
    "id": "555555555555555555",
    "role": "player",
    "team": "team2",
    "can_start": false,
    "can_pick": true,
    "can_report": false,
    "can_reverse": false
  }
}
```

### 필드 규칙

- `game_id`: 서버가 판마다 만드는 문자열이다. 서버를 재시작해도 다시 쓰지 않는다. 클라이언트는 같은지 비교만 한다.
- `round`, `season`: 이 판이 기록될 라운드와 시즌이다. 판을 시작할 때 정해지고, 결과를 기록할 때 같은 값을 쓴다. `none`이면 `null`이다.
- `turn_id`: 차례마다 새로 만드는 문자열이다. 픽이 확정되거나 자동 배정되면 바뀐다. 클라이언트는 같은지 비교만 한다.
- `current_index`: `pick_order`에서 지금 고르는 사람의 위치(0~5)이다.
- `deadline_ms`: 이 차례의 마감이다. 차례가 시작될 때 `pick_timeout`(현재 20초)으로 정하고, 차례 안에서 바뀌지 않는다. v1 봇의 embed 모드처럼 카운트 중 무한대로 두지 않는다.
- `grace_ms`: 마감 뒤 서버가 늦게 도착한 픽을 더 받아 주는 시간이다(config `pick_grace_seconds`, 현재 2초). 화면은 마감에서 0을 보여 주고, 그 뒤에는 `마감 확인 중…`을 표시한다.
- `ddragon_version`: 챔피언 초상화 경로에 쓰는 Data Dragon 버전이다. 액티비티는 `/ddragon/cdn/{ddragon_version}/img/champion/{champions[].id}.png`로 초상화를 불러온다. `none`이면 `null`이다.
- `players`: 6명이다. 순서는 TEAM 1 세 명, TEAM 2 세 명이고 팀 안의 순서는 판을 시작할 때 나뉜 순서이다.
  - `name`은 서버 별명(없으면 사용자 이름)이다.
  - `wins`는 이번 시즌 누적 승수이다. 픽 순서가 승수가 낮은 사람부터이기 때문에 보여 준다.
  - 프로필 사진(아바타)은 넣지 않는다(사용자 결정).
- `pick_order`: 6명의 ID를 픽 순서대로 담는다. 승수가 낮은 사람부터이고, 승수가 같으면 무작위이다.
- `champions`: 이번 판 후보 8개이다. `id`는 Data Dragon 영문 ID이고, 요청과 `selections`에는 이 값을 쓴다. `name`은 한국어 이름이다.
- `selections`: 고른 사람의 ID → 챔피언 `id`이다. 자동 배정도 여기에 들어간다.
- `auto_assigned`: 시간이 지나 서버가 대신 고른 사람의 ID 목록이다.
- `result`: `completed`에서만 채운다.

```json
"result": {
  "winner": "team2",
  "recorded_ms": 1790000900000,
  "corrected": { "from": "team1", "at_ms": 1790000960000 }
}
```

  - `corrected`는 번복된 적이 없으면 `null`이다. 여러 번 번복하면 마지막 번복을 담는다. `from`은 그 번복 직전의 승리 팀이다.

### me

| 필드 | 뜻 |
|---|---|
| `role` | 이 판의 6명이면 `player`, 아니면 `spectator` |
| `team` | `player`면 `team1`·`team2`, 아니면 `null` |
| `can_start` | 지금 `start`를 보낼 수 있는가. `none`, `awaiting_result`, `completed`일 때 접속한 사람 누구나 참이다 |
| `can_pick` | 지금 `pick`을 보낼 수 있는가. `picking`이고 내가 `current_index`의 사람일 때 참이다 |
| `can_report` | 지금 `result`를 보낼 수 있는가. `awaiting_result`이고 `player`일 때 참이다 |
| `can_reverse` | 지금 `reverse`를 보낼 수 있는가. `completed`이고 `player`일 때 참이다 |

DEV_MODE에서는 권한이 넓어진다(11절). 클라이언트는 버튼 활성화를 `me`로만 정한다. `me`가 참이어도 서버가 거절할 수 있으므로 `reply`로 결과를 확인한다.

## 9. 클라이언트 → 서버

4절의 `ping`, `sync`에 아래 네 가지를 더한다. 모두 4절 규칙대로 `id`가 있고 4KB 이하이다.

| `t` | 형식 |
|---|---|
| `start` | `{ "t": "start", "id": "g-1", "game_id": "g-1789990000000", "guild_id": "1234567890" }` |
| `pick` | `{ "t": "pick", "id": "k-7", "game_id": "g-1790000000000", "turn_id": "g-1790000000000:2", "champion_id": "Ahri" }` |
| `result` | `{ "t": "result", "id": "r-1", "game_id": "g-1790000000000", "winner": "team1" }` |
| `reverse` | `{ "t": "reverse", "id": "v-1", "game_id": "g-1790000000000", "expected_winner": "team1" }` |

### 공통 처리

- 서버는 메시지를 받은 직후, 락을 기다리기 전에 접수 시각을 단조 시계로 기록한다. 클라이언트가 보낸 시각은 판정에 쓰지 않는다.
- 판정과 상태 변경은 봇의 게임 락(`pick_lock`) 안에서 한다. 디스코드 명령(`/게임시작`, `/승리`, `/번복`)과 같은 락, 같은 처리 함수를 쓴다.
- 같은 사용자가 같은 `game_id`에 같은 `id`를 다시 보내면, 다시 처리하지 않고 처음 보낸 `reply`를 그대로 돌려준다. 같은 `id`로 내용이 다른 요청을 보내면 `bad_request`이다. 이 기록은 다음 판을 시작할 때까지 보관한다.

### start

`game_id`는 화면에 지금 떠 있는 판의 ID이고, 게임이 없으면(`none`) `null`이다. 두 사람이 동시에 시작을 눌러 판이 두 번 만들어지는 것을 막는 데 쓴다. `guild_id`는 SDK의 `guildId`이다.

1. `game_id`가 현재 판과 다르다 → `stale_game` (다른 사람이 먼저 새 판을 시작함)
2. `phase`가 `none`, `awaiting_result`, `completed`가 아니다 → `wrong_phase`
3. `guild_id`가 `null`이거나 봇이 들어가 있지 않은 길드이다 → `not_allowed`
4. 그 길드에 온라인인 일반 사용자가 6명보다 적다 → `not_enough_players` (DEV_MODE는 `wins_dev.json`의 6명을 쓰므로 해당 없음)
5. 그 외 → 새 판을 만든다.

새 판은 지금 `/게임시작`과 같은 함수로 만든다. 온라인인 일반 사용자 가운데 6명을 무작위로 뽑고, 승수로 픽 순서를 정하고, 팀을 무작위로 나누고, 후보 8개를 뽑는다. 그 길드의 팀짜기 채널에 현황판과 "픽 화면 열기" 버튼을 보내고(12절), `starting`으로 들어간다.
- 상태가 바뀌면 서버는 연결된 모든 소켓에 새 `state`를 보낸 뒤, 요청한 소켓에 `reply`를 보낸다. `reply`의 `state_version`은 처리 직후 버전이다.

### pick

판정 순서는 아래와 같다. 먼저 걸린 코드로 거절한다.

1. `game_id`가 현재 판이 아니다 → `stale_game`
2. `phase`가 `picking`이 아니다 → `wrong_phase`
3. `turn_id`가 현재 차례가 아니다 → `stale_turn` (이미 다음 차례로 넘어갔거나 자동 배정이 끝남)
4. 보낸 사람이 지금 차례가 아니다 → `not_your_turn` (DEV_MODE 예외는 11절)
5. 접수 시각이 `deadline + grace`보다 늦다 → `timeout`
6. `champion_id`가 이번 판 후보가 아니다 → `not_candidate`
7. 다른 사람이 이미 고른 챔피언이다 → `champion_taken`
8. 그 외 → 확정. 고르는 즉시 다음 차례로 넘어가고, 취소는 없다. 6명째이면 `awaiting_result`가 된다.

마감 처리: 서버는 `deadline + grace`에 락 안에서 같은 차례가 아직 비어 있는지 다시 확인하고, 남은 후보 가운데 무작위로 자동 배정한다. 그 사람을 `auto_assigned`에 넣고 다음 차례로 넘긴다. 이미 자동 배정으로 끝난 차례는 늦게 온 픽으로 되돌리지 않는다.

### result

1. `game_id`가 현재 판이 아니다 → `stale_game`
2. `phase`가 `completed`이다 → `already_recorded`
3. `phase`가 `awaiting_result`가 아니다 → `wrong_phase`
4. 보낸 사람이 이 판의 6명이 아니다 → `not_allowed`
5. `winner`가 `team1`·`team2`가 아니다 → `bad_request`
6. 그 외 → 기록. 추가 확인 없이 바로 기록한다.

기록은 지금 `/승리`와 같은 처리를 한다. 승수 저장(`wins.json`), 오늘의 결과, 라운드 증가, 판 기록(`history_data.json`)과 업로드, 팀짜기 채널의 결과·오늘의 결과·누적 전적 메시지가 모두 같다. 승수 저장에 실패하면 `record_failed`로 응답하고 `awaiting_result`에 그대로 머문다. 판 기록만 실패하면(시즌 불일치 등) 지금처럼 채널에 경고를 보내고, 판은 `completed`로 넘어간다.

### reverse

1. `game_id`가 현재 판이 아니다 → `stale_game`
2. `phase`가 `completed`가 아니다 → `wrong_phase`
3. 보낸 사람이 이 판의 6명이 아니다 → `not_allowed`
4. 현재 기록된 승리 팀이 `expected_winner`와 다르다 → `conflict` (다른 사람이 먼저 번복함)
5. 그 외 → 승리 팀을 뒤집는다. 추가 확인은 없다.

처리는 지금 `/번복`과 같다(판 기록 → 승수 순서, 승수 저장 실패 시 판 기록 원복, 오늘의 결과 O/X 정정, 팀짜기 채널 정정 공지). 저장에 실패하면 `record_failed`이다.
액티비티에서는 화면에 떠 있는 판만 번복한다. 예를 들어 R87 결과를 입력하면 다음 판을 시작하기 전까지 R87 결과 화면이 남고, 거기 있는 번복 버튼은 R87의 승리 팀을 뒤집는다. 새 판(R88)을 시작한 뒤에 R87을 고치려면 디스코드에서 `/번복 라운드:87`을 쓴다. 디스코드 `/번복`으로 현재 판을 뒤집어도 서버는 `result`를 고친 `state`를 보낸다.

### reply 코드

| `code` | 뜻 |
|---|---|
| `ok` | 처리 완료 |
| `bad_request` | 형식 위반, 모르는 `t`, 같은 `id`로 다른 내용 |
| `not_allowed` | 권한 없음 |
| `not_enough_players` | 온라인인 사람이 6명보다 적어 판을 만들 수 없음 |
| `stale_game` | 이미 끝났거나 바뀐 판 |
| `wrong_phase` | 지금 단계에서 할 수 없는 요청 |
| `stale_turn` | 이미 지나간 차례 |
| `not_your_turn` | 내 차례가 아님 |
| `timeout` | 마감과 유예가 지난 뒤 도착 |
| `not_candidate` | 이번 판 후보가 아닌 챔피언 |
| `champion_taken` | 이미 뽑힌 챔피언 |
| `already_recorded` | 이미 결과가 기록된 판 |
| `conflict` | 번복하려던 결과가 그새 바뀜 |
| `record_failed` | 저장 실패. 상태는 바뀌지 않았다 |
| `server_error` | 그 밖의 서버 오류 |

`message`는 4절의 `reply` 설명처럼 화면에 그대로 보여 줄 한국어 문장이다.

## 10. 누가 무엇을 누를 수 있나

- 이 판의 6명은 `player`이고, 픽(자기 차례만), 승리 팀 입력, 번복을 할 수 있다.
- 6명이 아닌 사람이 액티비티를 열면 `spectator`로 같은 화면을 보기만 한다.
- 새 판 시작은 액티비티를 연 사람 누구나 할 수 있다. 온라인인 사람이 6명보다 많으면 누른 사람이 이번 판에 뽑히지 않을 수도 있기 때문이다.
- 디스코드 서버 멤버인지 따로 확인하거나 접속을 막지는 않는다. 액티비티는 디스코드 서버 안에서만 열 수 있고, 인증 전 앱은 개발팀과 앱 테스터만 쓸 수 있기 때문이다.

## 11. DEV_MODE

- 게임은 지금처럼 `wins_dev.json`의 6명으로 만든다. 이들은 실제로 접속하지 않을 수 있다.
- DEV_MODE에서는 액티비티에 접속한 사람 누구나 누구 차례든 대신 `pick`할 수 있고, `result`와 `reverse`도 보낼 수 있다. 이때 `me.can_pick`, `can_report`, `can_reverse`도 그에 맞게 참이 된다. dev 앱은 개발팀과 앱 테스터만 열 수 있으므로 따로 제한하지 않는다.
- 운영 모드에서는 이 예외가 없다.

## 12. 봇 쪽 동작 (규격 밖이지만 함께 바뀌는 것)

- config에 `pick_mode`를 둔다. `"embed"`는 지금 방식(채널 버튼과 매초 편집)이고, `"activity"`는 액티비티 방식이다. 운영 전환 전까지 운영 봇은 `"embed"`, dev 봇은 `"activity"`로 둔다.
- `"activity"`에서는 팀짜기 채널에 현황판 메시지 하나와 "픽 화면 열기" 버튼(LAUNCH_ACTIVITY, 응답 type 12)만 둔다. 챔피언 버튼과 매초 편집은 없다. 현황판은 시작·픽·자동 배정·완료 때만 고친다.
- `"embed"`에서는 액티비티 서버가 항상 `none`을 보낸다. 두 방식을 한 판에 섞지 않는다.
- 새 판 시작, 결과 기록, 번복은 디스코드 명령과 액티비티가 같은 함수를 부른다. `/게임시작`, `/승리`, `/번복`은 예비 경로로 남는다.
- 새 판을 액티비티에서 시작해도 팀짜기 채널에는 현황판과 "픽 화면 열기" 버튼이 올라간다. 아직 액티비티를 열지 않은 사람이 이 버튼으로 들어온다.
- 지금 `fetch_champion_data()`는 챔피언마다 한국어 이름과 이미지 주소만 남긴다. `champions[].id`와 `ddragon_version`을 보내려면 Data Dragon 영문 ID와 버전도 함께 보관해야 한다. 판 기록(`history_data.json`)에는 지금처럼 한국어 이름을 저장한다.

## 13. 화면이 phase별로 보여 줄 것 (참고)

화면 배치는 디자인 캔버스를 따른다. 여기서는 어떤 데이터로 무엇을 그리는지만 적는다.

| phase | 화면 |
|---|---|
| `none` | 대기 화면과 "게임 시작" 버튼(`me.can_start`) |
| `starting` | 팀 구성, 픽 순서, 후보 8개, `start_at_ms`까지 남은 초 |
| `picking` | 위와 같고, 지금 고르는 사람 노란색 강조, 남은 초(5초 이하 빨강), 뽑힌 챔피언 잠금. `me.can_pick`이 참이면 후보 카드를 누를 수 있다 |
| `awaiting_result` | 픽 결과와 승리 팀 버튼 두 개(`me.can_report`). 떨어진 곳에 작은 "결과 없이 새 판" 버튼(`me.can_start`) |
| `completed` | 결과, 번복 버튼(`me.can_reverse`), "다음 판 시작" 버튼(`me.can_start`). 번복됐으면 표시 |
