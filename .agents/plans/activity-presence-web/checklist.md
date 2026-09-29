# 체크리스트

- [x] protocol.ts: v4, present·paused, me 권한, ClientMessage 4종, isState 검증, reply 문구 3종
- [x] fixtures.ts·preview.ts: 새 필드, 빠진 can_advantage, 입장 대기·정지 미리보기
- [x] protocol 테스트(v4 검증)
- [x] connection.ts: #readySent, notifyRendered, requestStartNow/Pause/Resume
- [x] connection 테스트(ready 한 번, 재연결 시 재전송, 요청 형식)
- [x] view-logic.ts: 입장 수, canStartNow/canPause/canResume, 정지 고정 초, 이탈·재입장 알림
- [x] view-logic 테스트
- [x] useActivity: notifyRendered, 액션 3종, 이탈 알림 토스트
- [x] TeamRoster 점, Header 입장 n/N
- [x] TurnCountdown 대기·지금 시작·일시정지/재개·배너·5초
- [x] PipView 표시(버튼 없음)
- [x] npm test / build / lint 통과
- [ ] 완료 보고
