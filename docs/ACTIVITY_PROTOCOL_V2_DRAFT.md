# 액티비티 통신 규격 v2 초안 (protocol_version 2)

> 상태: 초안. 사용자 확인 뒤 [ACTIVITY_PROTOCOL.md](ACTIVITY_PROTOCOL.md)를 이 내용으로 교체하고 이 파일은 지운다.
> 지금 구현(활동 서버·프론트)은 v1 문서를 따른다.

v1에서 바뀌지 않는 것은 다시 적지 않는다. 토큰 교환(`POST /pick-api/token`), 세션, WebSocket 연결, 요청 ID, `ping`/`pong`, `sync`, `reply` 형식, 서버 송신 규칙, 클라이언트 시계 보정은 v1 문서 2~6절을 그대로 따른다.
v2는 실제 게임 상태, 픽, 승리 팀 입력, 번복을 더한다. 설계 이유는 [통합 실행 계획](../.agents/plans/activity-integration/plan.md) 4~7절과 15절에 있다.

## 1. v1과 달라지는 점

- `hello`와 `state`의 `protocol_version`이 2가 된다. 클라이언트는 2가 아니면 입력을 막고 새로고침 안내를 보여 준다.
- `state`에 실제 게임 내용(선수, 픽 순서, 챔피언 후보, 선택, 결과)과 내 권한(`me`)이 채워진다.
- 클라이언트 → 서버 메시지에 `pick`, `result`, `reverse`가 생긴다.
- 개발용 `demo_countdown`은 없어진다. 받으면 모르는 `t`로 보고 `bad_request`로 응답한다. 개발 중 시험은 DEV_MODE의 실제 게임 흐름으로 한다(6절).
- 종료 코드 4403이 생긴다(5절).

## 2. 게임 진행과 phase

게임은 지금처럼 디스코드 `/게임시작`으로만 시작한다. 액티비티에는 시작 버튼을 두지 않는다.

| phase | 언제 | 채워지는 시간·차례 필드 |
|---|---|---|
| `none` | 서버가 켜진 뒤 아직 게임이 없을 때 | 모두 `null`, 목록은 빈 값 |
| `starting` | `/게임시작` 직후, 자동 시작 전 | `start_at_ms` |
| `picking` | 픽 진행 중 | `deadline_ms`, `grace_ms`, `turn_id`, `current_index` |
| `awaiting_result` | 6명이 모두 고른 뒤, 승리 팀 입력 전 | 모두 `null` |
| `completed` | 승리 팀이 기록된 뒤, 다음 `/게임시작` 전까지 | 모두 `null`, `result` 채움 |
| `aborted` | v2 서버는 보내지 않는다(예약) | 클라이언트는 `none`처럼 처리한다 |

- `starting`의 길이는 config `auto_start_seconds`(현재 15초)이다. `start_at_ms`가 되면 서버가 `picking`으로 바꾼다. 클라이언트가 먼저 시작시키지 않는다.
- `completed` 화면은 다음 `/게임시작`까지 남는다. 그 사이에 번복할 수 있다.
- 결과를 입력하지 않은 채 `/게임시작`을 다시 하면 이전 판은 기록 없이 버려지고, 새 `game_id`의 `starting`이 온다. 지금 봇과 같은 동작이다.
- 서버가 재시작되면 진행 중이던 판은 이어지지 않는다. 새 `server_epoch`의 `none`이 온다.

## 3. state

모든 필드는 v1 규칙대로 항상 보낸다. 해당하지 않으면 `null` 또는 빈 값이다. `me`는 받는 사람마다 다르므로 서버는 소켓마다 따로 만든다.

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
    "can_pick": true,
    "can_report": false,
    "can_reverse": false
  }
}
```

### 필드 규칙

- `game_id`: 서버가 판마다 만드는 문자열이다. 서버를 재시작해도 다시 쓰지 않는다. 클라이언트는 같은지 비교만 한다.
- `round`, `season`: 이 판이 기록될 라운드와 시즌이다. `/게임시작` 때 정해지고, `/승리`로 기록될 때 같은 값을 쓴다. `none`이면 `null`이다.
- `turn_id`: 차례마다 새로 만드는 문자열이다. 픽이 확정되거나 자동 배정되면 바뀐다. 클라이언트는 같은지 비교만 한다.
- `current_index`: `pick_order`에서 지금 고르는 사람의 위치(0~5)이다.
- `deadline_ms`: 이 차례의 마감이다. 차례가 시작될 때 `pick_timeout`(현재 20초)으로 정하고, 차례 안에서 바뀌지 않는다. v1 봇의 embed 모드처럼 카운트 중 무한대로 두지 않는다.
- `grace_ms`: 마감 뒤 서버가 늦게 도착한 픽을 더 받아 주는 시간이다(config `pick_grace_seconds`, 현재 2초). 화면은 마감에서 0을 보여 주고, 그 뒤에는 `마감 확인 중…`을 표시한다.
- `ddragon_version`: 챔피언 초상화 경로에 쓰는 Data Dragon 버전이다. 액티비티는 `/ddragon/cdn/{ddragon_version}/img/champion/{champions[].id}.png`로 초상화를 불러온다. `none`이면 `null`이다.
- `players`: 6명이다. 순서는 TEAM 1 세 명, TEAM 2 세 명이고 팀 안의 순서는 `/게임시작` 때 나뉜 순서이다.
  - `name`은 서버 별명(없으면 사용자 이름)이다.
  - `wins`는 이번 시즌 누적 승수이다. 픽 순서가 승수가 낮은 사람부터이기 때문에 보여 준다.
  - 아바타는 v2에 넣지 않는다. 디자인에 없고, 디스코드 CDN 이미지를 액티비티에서 쓰려면 URL 매핑을 따로 검토해야 한다.
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
| `can_pick` | 지금 `pick`을 보낼 수 있는가. `picking`이고 내가 `current_index`의 사람일 때 참이다 |
| `can_report` | 지금 `result`를 보낼 수 있는가. `awaiting_result`이고 `player`일 때 참이다 |
| `can_reverse` | 지금 `reverse`를 보낼 수 있는가. `completed`이고 `player`일 때 참이다 |

DEV_MODE에서는 권한이 넓어진다(6절). 클라이언트는 버튼 활성화를 `me`로만 정한다. `me`가 참이어도 서버가 거절할 수 있으므로 `reply`로 결과를 확인한다.

## 4. 클라이언트 → 서버

v1의 `ping`, `sync`에 아래 세 가지를 더한다. 모두 v1 규칙대로 `id`가 있고 4KB 이하이다.

| `t` | 형식 |
|---|---|
| `pick` | `{ "t": "pick", "id": "k-7", "game_id": "g-1790000000000", "turn_id": "g-1790000000000:2", "champion_id": "Ahri" }` |
| `result` | `{ "t": "result", "id": "r-1", "game_id": "g-1790000000000", "winner": "team1" }` |
| `reverse` | `{ "t": "reverse", "id": "v-1", "game_id": "g-1790000000000", "expected_winner": "team1" }` |

### 공통 처리

- 서버는 메시지를 받은 직후, 락을 기다리기 전에 접수 시각을 단조 시계로 기록한다. 클라이언트가 보낸 시각은 판정에 쓰지 않는다.
- 판정과 상태 변경은 봇의 게임 락(`pick_lock`) 안에서 한다. 디스코드 명령(`/승리`, `/번복`, 채널 버튼)과 같은 락, 같은 처리 함수를 쓴다.
- 같은 사용자가 같은 `game_id`에 같은 `id`를 다시 보내면, 다시 처리하지 않고 처음 보낸 `reply`를 그대로 돌려준다. 같은 `id`로 내용이 다른 요청을 보내면 `bad_request`이다. 이 기록은 그 판이 끝날 때까지(다음 `/게임시작`까지) 보관한다.
- 상태가 바뀌면 서버는 연결된 모든 소켓에 새 `state`를 보낸 뒤, 요청한 소켓에 `reply`를 보낸다. `reply`의 `state_version`은 처리 직후 버전이다.

### pick

판정 순서는 아래와 같다. 먼저 걸린 코드로 거절한다.

1. `game_id`가 현재 판이 아니다 → `stale_game`
2. `phase`가 `picking`이 아니다 → `wrong_phase`
3. `turn_id`가 현재 차례가 아니다 → `stale_turn` (이미 다음 차례로 넘어갔거나 자동 배정이 끝남)
4. 보낸 사람이 지금 차례가 아니다 → `not_your_turn` (DEV_MODE 예외는 6절)
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
액티비티에서는 화면에 떠 있는 판만 번복한다. 더 이전 판은 지금처럼 `/번복 라운드:N`으로 한다. 디스코드 `/번복`으로 현재 판을 뒤집어도 서버는 `result`를 고친 `state`를 보낸다.

### reply 코드

| `code` | 뜻 |
|---|---|
| `ok` | 처리 완료 |
| `bad_request` | 형식 위반, 모르는 `t`, 같은 `id`로 다른 내용 |
| `not_allowed` | 권한 없음 |
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

`message`는 v1처럼 화면에 그대로 보여 줄 한국어 문장이다.

## 5. 관전과 접속 권한

- 이 판의 6명은 `player`이다.
- 6명이 아니어도 봇이 들어가 있는 길드의 멤버면 `spectator`로 같은 `state`를 받는다. 입력 권한은 없다.
- 봇이 들어가 있는 어느 길드의 멤버도 아니면, 서버는 WebSocket 업그레이드 직후 종료 코드 4403으로 닫는다. 클라이언트는 재접속하지 않고 "이 서버 멤버만 볼 수 있습니다"를 보여 준다.
- 액티비티가 실제로 어느 채널에서 열렸는지(Activity Instance API) 확인하는 것은 v2에 넣지 않는다.

| 종료 코드 | 의미 | 클라이언트 동작 |
|---|---|---|
| 4403 | 인증은 됐지만 볼 권한이 없음 | 재접속하지 않고 안내 표시 |

## 6. DEV_MODE

- 게임은 지금처럼 `wins_dev.json`의 6명으로 만든다. 이들은 실제로 접속하지 않을 수 있다.
- DEV_MODE에서는 봇이 들어가 있는 길드(TEST2)의 멤버를 모두 시험 사용자로 본다. 시험 사용자는 누구 차례든 대신 `pick`할 수 있고, `result`와 `reverse`도 보낼 수 있다. 이때 `me.can_pick`, `can_report`, `can_reverse`도 그에 맞게 참이 된다.
- 운영 모드에서는 이 예외가 없다.

## 7. 봇 쪽 동작 (규격 밖이지만 함께 바뀌는 것)

- config에 `pick_mode`를 둔다. `"embed"`는 지금 방식(채널 버튼과 매초 편집)이고, `"activity"`는 액티비티 방식이다. 운영 전환 전까지 운영 봇은 `"embed"`, dev 봇은 `"activity"`로 둔다.
- `"activity"`에서는 팀짜기 채널에 현황판 메시지 하나와 "픽 화면 열기" 버튼(LAUNCH_ACTIVITY, 응답 type 12)만 둔다. 챔피언 버튼과 매초 편집은 없다. 현황판은 시작·픽·자동 배정·완료 때만 고친다.
- `"embed"`에서는 액티비티 서버가 항상 `none`을 보낸다. 두 방식을 한 판에 섞지 않는다.
- 결과 기록과 번복은 디스코드 명령과 액티비티가 같은 함수를 부른다. `/승리`, `/번복`은 예비 경로로 남는다.
- 지금 `fetch_champion_data()`는 챔피언마다 한국어 이름과 이미지 주소만 남긴다. `champions[].id`와 `ddragon_version`을 보내려면 Data Dragon 영문 ID와 버전도 함께 보관해야 한다. 판 기록(`history_data.json`)에는 지금처럼 한국어 이름을 저장한다.

## 8. 화면이 phase별로 보여 줄 것 (참고)

화면 배치는 디자인 캔버스를 따른다. 여기서는 어떤 데이터로 무엇을 그리는지만 적는다.

| phase | 화면 |
|---|---|
| `none` | 대기 화면 "진행 중인 게임이 없습니다. 팀짜기 채널에서 /게임시작" |
| `starting` | 팀 구성, 픽 순서, 후보 8개, `start_at_ms`까지 남은 초 |
| `picking` | 위와 같고, 지금 고르는 사람 노란색 강조, 남은 초(5초 이하 빨강), 뽑힌 챔피언 잠금. `me.can_pick`이 참이면 후보 카드를 누를 수 있다 |
| `awaiting_result` | 픽 결과와 승리 팀 버튼 두 개(`me.can_report`) |
| `completed` | 결과와 번복 버튼(`me.can_reverse`), 번복됐으면 표시 |
