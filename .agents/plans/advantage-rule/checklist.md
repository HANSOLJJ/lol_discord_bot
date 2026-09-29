<!-- 5·6위 어드밴티지 규칙 구현 체크리스트 -->
# 5·6위 어드밴티지 체크리스트

- [x] 규칙 확정과 규격 14절 작성(protocol_version 3)
- [x] 서버 구현과 테스트 (claude 워커, d9ec56b·953415c·639ef9b, 테스트 144개)
- [x] 픽 화면 구현과 미리보기 (agy 워커)
  - [x] 규격 v3: protocol.ts 버전 3 업데이트, advantage 및 me.can_advantage 타입/검증, 요청/응답 메시지 처리
  - [x] 뷰 계산 로직: 밴·강제픽·마지막 차례 및 advantage 클릭 판정 (view-logic.ts, view-logic.test.ts)
  - [x] UI 컴포넌트: TurnCountdown, ChampionGrid, TeamRoster, PipView, ActivityScreen 업데이트
  - [x] 미리보기 데이터 추가 (preview.ts, fixtures.ts)
  - [x] 테스트 전체 통과 (npm test, npm run lint, npm run build)
- [x] 코디네이터 검증, main 병합(a72b191), push, 맥미니 반영(`scripts/deploy.sh --dev`). 맥미니 테스트: 파이썬 144개, 웹 227개
- [x] 코디네이터 화면 다듬기(d3e0bfd): 어드밴티지 제목 잘림, 규칙상 못 고르는 카드 흐리게, 미리보기 팀 배치를 규칙에 맞춤
- [x] 디스코드 dev 액티비티에서 밴·강제픽 판 각각 확인 (사용자 확인 완료)
