# 전적 대시보드 "대전 기록" 화면 구현 계획

작성일: 2026-09-28.
이 문서는 `arena.hansoljj.com` 대시보드를 `lol_arena/activity`의 Vite·React·TypeScript 프로젝트로 이관하는 첫 단계인 "대전 기록" 화면 구현 계획서이다.

## 1. 목표 및 범위
- `activity/dashboard.html` 및 `src/dashboard/main.tsx`를 통한 다중 페이지(Multi-Page) 대시보드 엔트리포인트 구축.
- 순수 함수 모듈(`src/dashboard/lib/`): 데이터 검증, 세션 분할, 필터링(기간·플레이어·챔피언), 한국 시간 포맷팅, 번복 데이터 정리.
- 대시보드 UI(`src/dashboard/`): 헤더(마지막 갱신 및 새로고침), 탭 네비게이션(가로 스크롤 모바일 대응, 레거시 탭 링크), 필터 바(기간/플레이어 칩 6개/챔피언 드롭다운/결과 카운트), 경기 카드 목록(최신순, 승리 강조, 30개 단위 페이지네이션, 모바일 반응형).
- Data Dragon 챔피언 초상화 로딩 및 폴백 지원.
- 열린 화면 자동 갱신(visibilitychange 이벤트 및 20초 주기 HEAD 요청 ETag/Last-Modified 비교).
- `vite.config.ts` 멀티 엔트리 빌드 및 프록시 설정.
- 기존 액티비티 파일(`src/App.tsx`, `src/lib/`, `src/components/`, `src/hooks/`, `src/test/`) 및 저장소 루트 파일 수정 금지.

## 2. 모듈 분리 구조
- `src/dashboard/lib/types.ts`: 전적 데이터, 세션, 경기, 필터 상태 타입 정의.
- `src/dashboard/lib/validation.ts`: JSON 데이터 유효성 검증.
- `src/dashboard/lib/session.ts`: 6시간 공백 기준 세션 분할 및 세션 라벨 포맷팅.
- `src/dashboard/lib/filter.ts`: 기간, 다중 플레이어 칩(교집합 출전), 챔피언 필터 로직.
- `src/dashboard/lib/time.ts`: KST 변환 및 날짜/시각 포맷팅.
- `src/dashboard/lib/ddragon.ts`: Data Dragon 버전 및 챔피언 초상화 URL 매핑.
- `src/dashboard/lib/*.test.ts`: 단위 테스트 스위트.
- `src/dashboard/hooks/useHistoryData.ts`: 데이터 로드, 폴링(20초 HEAD), visibilitychange 갱신 훅.
- `src/dashboard/components/`:
  - `DashboardHeader.tsx`: 타이틀, 마지막 갱신 시각, 새로고침 버튼.
  - `DashboardTabs.tsx`: 탭 목록 (대전 기록 활성, 나머지 레거시 링크), 모바일 가로 스크롤.
  - `DashboardFilters.tsx`: 기간 셀렉트, 6개 플레이어 칩, 챔피언 셀렉트, 판수 요약.
  - `GameCard.tsx`: 판 헤더, TEAM 1 vs TEAM 2 대진, 번복 배지, 반응형 그리드.
  - `GameList.tsx`: 30개 단위 페이지네이션 및 "더 보기" 버튼.
  - `ChampionPortrait.tsx`: Data Dragon 이미지 또는 첫 글자 원형 폴백.
- `src/dashboard/DashboardApp.tsx`: 대시보드 메인 컴포넌트 및 상태 관리.

## 3. 검증 전략
- `npm test`: 신규 순수 함수 및 기존 액티비티 테스트 전체 통과 (회귀 방지).
- `npm run lint`: oxlint 0 warnings, 0 errors.
- `npm run build`: `tsc -b` 타입 검사 및 Vite 빌드로 `dist/index.html`과 `dist/dashboard.html` 생성 검증.
