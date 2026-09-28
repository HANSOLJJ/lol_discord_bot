# 액티비티 서버 v2 체크리스트

- [x] game_core.py: 상태·lock·new_game·auto_assign·record_result_locked·reverse_locked 추출
- [x] got_champe.py가 game_core를 쓰도록 변경 (embed 동작 유지)
- [x] fetch_champion_data가 영문 ID·버전 보관
- [x] embed 회귀 테스트 (판 만들기·승리 기록·번복·자동 배정)
- [x] activity 모드: 시계·마감·자동 시작·자동 배정 타이머
- [x] activity 판정: start·pick·result·reverse, snapshot·me, DEV_MODE 대리 입력
- [x] 규칙 테스트
- [ ] activity_server v2: protocol 2, 요청 처리, 멱등성, demo 제거
- [ ] WS 왕복 테스트
- [ ] got_champe activity 모드: 현황판·픽 화면 열기(LAUNCH_ACTIVITY)·액티비티 시작 연결·공지
- [ ] config.json pick_mode·dev_pick_mode
- [ ] 전체 테스트·py_compile·보고
