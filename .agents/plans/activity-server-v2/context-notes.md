# 액티비티 서버 v2 결정 기록

## 2026-09-28 코디네이터 확인

- embed 모드에서는 액티비티 state가 항상 `none`이고 `me.can_start=false`이다. `start`는 `not_allowed`로 거절한다.
- activity 모드에서 6명이 모두 고르면 채널에 "6명 모두 선택 완료"와 승리 드롭다운을 보내지 않고 현황판만 고친다. `/승리`는 예비 경로로 동작한다.
- activity 모드 채널 메시지는 현황판 하나로 합친다. 제목에 ROUND N, TEAM 1·TEAM 2 명단, 선택 현황·픽순, "픽 화면 열기" 버튼. 팀 구성 embed, 챔피언 버튼 메시지, "챔피언 선택을 시작합니다" 알림은 보내지 않는다. 결과·오늘의 결과·누적 전적·번복 공지는 그대로다.

## 2026-09-28 구현 판단

- got_champe.py는 import하면 봇이 실행되고 `.env`를 읽으므로 테스트에서 import하지 않는다. 그래서 공통 함수를 디스코드와 무관한 `game_core.py`에 두고, 저장 함수(`save_wins`, `record_game` 등)와 시계를 주입받게 했다.
- 승리 기록은 판정·승수 저장·판 기록을 락 안에서 한 번에 한다. 원래는 락 안에서 래치만 세우고 저장은 락 밖에서 했지만, 락 안 작업이 동기 파일 쓰기뿐이라 번복과 같은 방식으로 맞췄다. 저장 실패 시 `victory_processed`가 세워지지 않는 결과는 원래(세웠다가 되돌림)와 같다.
- 번복 대상 판은 `find_game(라운드)`로 찾는데, 시즌 불일치로 판 기록이 남지 않은 판은 같은 라운드 번호의 예전 판을 잘못 찾을 수 있다. 그래서 판 기록 성공 여부를 `result`에 남기고, 기록이 없으면 액티비티 번복을 `record_failed`로 거절한다.
- activity 모드 채널 현황판은 기존 champion_messages·push_channel_embed(채널별 편집 합치기·최소 간격)를 그대로 쓴다. flush_embed_updates에 activity 분기 하나만 더해 설명 문구에 남은 초를 넣지 않는다. 현황판 field 0이 선택 현황이어야 기존 편집 함수가 맞게 고친다.
- LAUNCH_ACTIVITY는 `bot.http.request(Route(POST /interactions/{id}/{token}/callback), json={"type": 12})`로 보내고 `interaction.response._responded`를 세워 py-cord가 다시 응답하지 않게 했다. py-cord 웹훅 어댑터(create_interaction_response)는 `data: {}`를 항상 붙여 보내는데 type 12에서 이를 받아 주는지 확인할 수 없어 규격 문서대로 type만 보내는 원시 요청을 골랐다. 실제 디스코드에서 확인이 필요하다.
- 액티비티에서 시작한 판은 명령 채널이 없으므로 get_game_channels(guild, None)으로 config channels에만 보낸다. 이 판의 결과·번복 공지도 같은 채널(current_game_channels)로 보낸다. /게임시작으로 시작한 activity 판은 예전처럼 명령 채널도 포함한다.
- activity 모드에서 챔피언 풀 소진 안내("♻️ ...")는 채널에 보내지 않고 로그만 남긴다. 채널 메시지를 현황판 하나로 합친다는 결정에 맞췄다.
- 요청 멱등성 기록은 판이 바뀔 때(state의 game_id가 바뀔 때) 비운다. 새 판을 만든 start 요청 자신의 reply는 비운 뒤 다시 넣어, 재전송하면 stale_game이 아니라 처음 reply가 간다. 같은 요청이 처리 중에 다시 오면 같은 Future를 기다려 한 번만 처리한다.
- 게임 요청은 연결별 태스크로 처리해 다음 메시지 수신을 막지 않는다. 접수 시각은 수신 직후 잡으므로 앞 요청이 락을 기다리는 동안 들어온 픽도 실제 도착 시각으로 판정된다.
