# 액티비티 통신 규격 (protocol_version 1)

봇의 액티비티 서버(`lol_discord_bot/activity_server.py`)와 액티비티 프론트(`lol_arena/activity/`)가 주고받는 HTTP·WebSocket 형식을 고정하는 문서다.
설계 이유와 전체 흐름은 [통합 실행 계획](../.agents/plans/activity-integration/plan.md) 5~7절에 있고, 이 문서는 양쪽 구현이 똑같이 맞춰야 하는 형식만 정한다.
형식을 바꿀 때는 이 문서를 먼저 고치고 `protocol_version`을 올린다.

## 1. 1단계 범위

1단계에서 구현하는 것은 토큰 교환, 세션, WebSocket 연결, ping/pong, 상태 스냅샷, 개발용 데모 카운트다운이다.
실제 게임 상태 연결과 픽 요청(`pick`)은 4단계에서 이 문서에 추가한다. 1단계의 `state`는 데모 카운트다운 외에는 항상 게임 없음(`phase: "none"`)이다.

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
| 401 | `oauth_failed` | Discord 토큰 교환 또는 신원 확인 실패 |
| 429 | `rate_limited` | 요청 빈도 초과 |
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
| `demo_countdown` | `{ "t": "demo_countdown", "id": "d-1", "seconds": 20 }` | 아래 데모 규칙 |

- `ping`의 `c`는 클라이언트의 `performance.now()` 값이다. 서버는 해석하지 않고 그대로 돌려준다.
- 메시지는 4KB 이하이다. JSON 오류, 알 수 없는 `t`, 필드 형식 위반에는 `reply`(`ok: false`, `code: "bad_request"`)로 응답한다.

**데모 카운트다운 (개발 전용).** `DEV_MODE=true`일 때만 허용한다. `seconds`는 1~60 정수이다. 서버는 `phase: "picking"`, `turn_id: "demo-<일련번호>"`, `deadline_ms = server_ms + seconds × 1000`, `grace_ms: 2000`인 `state`를 연결된 모든 클라이언트에 보낸다. 마감과 유예가 지나면 서버가 `phase: "none"`인 `state`를 다시 보낸다. 운영 모드에서는 `reply`(`ok: false`, `code: "not_allowed"`)로 거절한다. 이 메시지는 1단계 측정용이며 4단계에서 실제 게임 상태로 대체한다.

### 서버 → 클라이언트

**hello**

```json
{
  "t": "hello",
  "protocol_version": 1,
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

```json
{
  "t": "state",
  "protocol_version": 1,
  "server_epoch": "4b0e1c9a-6a53-4a0f-9e2b-0d5b8f3c2a11",
  "game_id": null,
  "state_version": 0,
  "phase": "none",
  "round": null,
  "season": null,
  "server_ms": 1790000000000,
  "start_at_ms": null,
  "deadline_ms": null,
  "grace_ms": null,
  "turn_id": null,
  "current_index": null,
  "players": [],
  "pick_order": [],
  "champions": [],
  "selections": {},
  "auto_assigned": [],
  "me": { "id": "365414320332472332", "role": "spectator" }
}
```

- `phase`는 `none`, `starting`, `picking`, `awaiting_result`, `completed`, `aborted` 중 하나이다.
- `server_ms`와 `deadline_ms`는 서버가 같은 순간에 잡은 시각과 남은 시간으로 계산한다. 서버 내부의 마감 판정은 단조 시계로 한다.
- `state_version`은 서버 프로세스 안에서 상태가 바뀔 때마다 1씩 증가한다. 클라이언트는 같은 `server_epoch`에서 더 작거나 같은 `state_version`을 가진 `state`를 적용하지 않는다. 단, `sync` 응답으로 받은 같은 버전은 적용해도 된다.
- `me.role`은 `player` 또는 `spectator`이다. 1단계에서는 항상 `spectator`이다.
- 데모 카운트다운 중에는 `game_id`가 `"demo"`이고 `players` 등 목록 필드는 빈 값이다.

**reply**

```json
{ "t": "reply", "id": "d-1", "ok": false, "code": "not_allowed", "message": "운영 모드에서는 데모 카운트다운을 쓸 수 없습니다.", "state_version": 3 }
```

- `code`는 기계가 분기할 값이고, `message`는 화면에 보여줄 한국어 문장이다. 성공이면 `ok: true`, `code: "ok"`이다.

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
