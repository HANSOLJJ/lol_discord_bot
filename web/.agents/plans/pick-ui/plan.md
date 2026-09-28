# 액티비티 픽 화면 v2 통신 규격 구현 계획

## 목표
롤 3:3 투기장 디스코드 액티비티 프론트엔드를 통신 규격 v2(ACTIVITY_PROTOCOL.md)에 맞추어 완전히 구현한다.
새 판 시작, 픽 진행(내 차례/남의 차례/경고), 승리 팀 보고, 번복 기능을 제공하며, 디자인 원본(Main, Pc, Pip 등)의 반응형 배치 및 색상 규칙을 충실히 반영한다. 개발 전용 미리보기를 구축하여 서버 없이도 모든 단계를 시각적으로 확인하고 검증할 수 있게 한다.

## 세부 단계
1. **규격 v2 프로토콜 정의 및 검증 모듈 갱신**
   - `src/lib/protocol.ts`: `PROTOCOL_VERSION = 2`, v2 `StateMessage`, `ClientMessage`(`start`, `pick`, `result`, `reverse`), `players`, `pick_order`, `champions`, `selections`, `auto_assigned`, `result`, `ddragon_version`, `me` 상세 타입 정의 및 런타임 유효성 검사.
   - `demo_countdown` 관련 코드 제거.
   - `src/lib/protocol.test.ts` 갱신.
2. **연결 및 통신 계층 갱신**
   - `src/lib/connection.ts`: `start`, `pick`, `result`, `reverse` 메서드 추가 및 `demo_countdown` 제거.
   - `src/lib/connection.test.ts` 갱신.
3. **테스트 픽스처 및 순수 뷰 로직 모듈 작성**
   - `src/test/fixtures.ts`: v2 규격 예시 기반의 phase별 목 데이터 정의.
   - `src/lib/view-logic.ts`: 현재 턴 플레이어, 챔피언 잠금 상태, 5초 경고 색상, 버튼 활성화 판정 등 순수 뷰 계산 로직 분리.
   - `src/lib/view-logic.test.ts`: 단위 테스트 작성.
4. **미리보기(DEV 전용) 및 상태 연동 훅 갱신**
   - `src/hooks/useActivity.ts`: v2 액션들(`start`, `pick`, `result`, `reverse`) 바인딩, 토스트 및 펜딩 상태 관리.
   - DEV_MODE URL query(`?preview=...`) 감지 시 고정 목 데이터로 동작하는 미리보기 브릿지 구현.
5. **픽 화면 UI 컴포넌트 및 스타일 구현**
   - 디자인 원본(Main.dc.html, Pc.dc.html, Pip.dc.html 등)의 HTML/CSS 구조 반영.
   - 세 가지 반응형 뷰 지원: 모바일 세로(390x844), PC 2단(960x600), 작은 창 요약(320x180 Pip).
   - 팀 구성, 현재 차례/카운트다운(5초 이하 빨강, 0초 마감 확인 중), 픽 순서 목록(자동 배정 뱃지), 챔피언 후보 4x2 그리드(초상화, 자물쇠 오버레이).
   - phase별 화면: none, starting, picking, awaiting_result, completed.
   - 토스트 알림 컴포넌트.
   - 초상화 로딩 실패 시 첫 글자 원형 폴백.
   - 카운트다운 렌더링 격리(초 단위 변화가 전체 트리 불필요 리렌더를 일으키지 않도록 최적화).
6. **검증 및 최종 정리**
   - `npm test`, `npm run lint`, `npm run build` 확인.
   - 논리 단위 커밋 및 결과 보고서 정리.
