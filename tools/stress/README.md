# 액티비티 v4 스트레스 테스트

실제 액티비티 서버(`ActivityServer.start()`)를 가짜 디스코드 로그인으로 띄우고, 가상 참가자·관전자 여러 명의 WebSocket으로 입장·퇴장·일시정지·지금 시작·픽을 무작위로 섞어 보내면서 불변식을 검사한다. 2026-09-29 Codex(gpt-6-astra)가 만든 도구를 저장소로 옮겼다. 정식 단위 테스트(`tests/`)가 확인하지 못하는 "순서가 뒤섞인 경우"를 찾는 용도이다.

## 실행

저장소 루트에서 실행한다. 결과는 `tools/stress/out/`(git 추적 안 함)에 쌓인다.

```bash
# 고정 시나리오 전체 + 무작위 시드 300개 (약 1분)
uv run python -B tools/stress/presence_stress.py --seeds 300 --output run.jsonl

# 무작위 시드 하나만 재현
uv run python -B tools/stress/presence_stress.py --random-only --start-seed 9 --seeds 1 --output seed9.jsonl

# 특정 시나리오만, 테스트 서버(handler cancellation 켜짐) 조건으로
uv run python -B tools/stress/presence_stress.py --case pending_presence --seeds 0 --testserver --output ts.jsonl

# 연결 종료 중 핸들러 취소 비교 (운영 서버 10회 + 테스트 서버 10회)
uv run python -B tools/stress/cancellation_repro.py
```

실패하면 JSONL에 traceback, state, 전체 요청 순서가 남고 종료 코드 1로 끝난다. 서버 경고·오류는 `out/server.log`에 쌓인다.

## 시나리오

입장·퇴장 반복과 다중 연결, 정지·재개 경계(연타, 동시 재개, 마감 직전·유예 중·카운트다운 마지막 순간), 지금 시작과 마지막 입장 경합, 밴·강제픽 판의 정지·재개, heartbeat 끊김(짧은 설정·기본 10초), 타이머와 요청의 락 경합, 락 대기 중 ready·연결 종료, embed 모드와 DEV_MODE, 그리고 이것들을 섞은 무작위 시드.

## 검사하는 불변식

- 한 판은 한 번만 시작하고 후속 작업도 한 번만 실행된다.
- 같은 사용자의 여러 연결은 한 명으로 세고, 관전자는 입장에 들어가지 않는다. 마지막 ready 연결이 끊기면 빠진다.
- 일반 카운트다운은 이탈 시 취소되고 재입장 시 다시 5초로 시작한다. 지금 시작으로 잡은 카운트다운은 이탈로 취소되지 않는다.
- 정지 중에는 남은 시간이 줄지 않고 마감 시각이 null이며, 재개하면 남은 시간이 복원된다. 정지 중 pick·advantage·start_now는 `paused`로 거절된다.
- 한 차례의 결과가 바뀌지 않고 자동 배정·챔피언 중복이 없다. 픽이 끝나면 awaiting_result가 된다. 밴·강제픽 규칙은 정지·재개 뒤에도 유지된다.
- 모든 연결의 마지막 state와 버전이 같아지고 버전이 거꾸로 가지 않는다. 미처리 예외·경고·종료 뒤 남은 태스크가 없다.

## 기록

- 2026-09-29 첫 실행(`9ef45aa`): 고정 46개 + 무작위 시드 300개(동작 21,000회, 불변식 검사 35,110회) 모두 통과. 테스트 서버(handler cancellation) 조건에서만 연결 종료 정리가 중단되는 문제를 찾았고, `703f4e2`에서 정리 작업을 `asyncio.shield`로 보호해 고쳤다. 이후 `cancellation_repro.py`는 두 서버 모두 10/10 통과.
- heartbeat 실측: 서버에 직접 붙은 조용한 끊김은 기본 설정(10초 + 응답 대기 5초)에서 약 15.7초에 감지됐다. 운영은 디스코드 프록시를 거쳐 감지가 보장되지 않는다(규격 §15).
