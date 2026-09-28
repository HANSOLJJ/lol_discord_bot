# 대전 기록 화면 구현 체크리스트

- [x] 1. 환경 설정 및 빌드 구성
  - [x] `activity/vite.config.ts`에 `dashboard.html` 엔트리 추가 및 `/history_data.json` 프록시 설정
  - [x] `activity/dashboard.html` 생성 (Pretendard 웹폰트 링크, 뷰포트, 타이틀, 루트 엘리먼트)
- [x] 2. 순수 함수 라이브러리 및 단위 테스트 구현 (`src/dashboard/lib/`)
  - [x] `types.ts`: 도메인 타입 정의
  - [x] `validation.ts` & `validation.test.ts`: JSON 데이터 유효성 검증 및 거부 테스트
  - [x] `time.ts` & `time.test.ts`: KST 변환 (`9월 27일 (일) 03:31` 형식) 테스트
  - [x] `session.ts` & `session.test.ts`: 6시간 공백 기준 세션 분할, 라벨 포맷팅, 기본 기간(최신 시즌) 테스트
  - [x] `filter.ts` & `filter.test.ts`: 기간 필터, 다중 플레이어 칩 필터, 챔피언 필터 테스트
  - [x] `ddragon.ts` & `ddragon.test.ts`: Data Dragon 매핑 및 URL 생성 (기본 주소 인자 지원)
- [x] 3. 커스텀 훅 및 자동 갱신 구현 (`src/dashboard/hooks/`)
  - [x] `useHistoryData.ts`: 초기 로드, visibilitychange 감지, 20초 주기 HEAD 요청 ETag/Last-Modified 비교 폴링, 수동 갱신
  - [x] `useChampionPortraits.ts`: Data Dragon 초상화 매핑 로드 훅
- [x] 4. React 컴포넌트 및 스타일 구현 (`src/dashboard/components/`, `src/dashboard/`)
  - [x] 공통 스타일 변수 및 리셋 CSS
  - [x] `DashboardHeader.tsx`: 타이틀, 갱신 시각, 새로고침 버튼
  - [x] `DashboardTabs.tsx`: 가로 스크롤 탭 바, 레거시 링크 탭
  - [x] `DashboardFilters.tsx`: 기간/플레이어 칩/챔피언 드롭다운/결과 판수
  - [x] `ChampionPortrait.tsx`: 초상화 이미지 및 첫 글자 원형 폴백
  - [x] `GameCard.tsx`: 머리줄, 승리팀 강조, 패배팀 불투명도, 번복 배지, 양 팀 플레이어 목록
  - [x] `GameList.tsx`: 30개 단위 페이지네이션 및 "더 보기" 버튼
  - [x] `DashboardApp.tsx`: 대시보드 통합 화면
  - [x] `main.tsx`: 대시보드 마운트 엔트리포인트
- [x] 5. 검증 및 빌드 확인
  - [x] `npm test` 전체 통과 확인
  - [x] `npm run lint` 경고 0건 확인
  - [x] `npm run build` 다중 페이지 빌드(`dist/index.html`, `dist/dashboard.html`) 생성 확인
  - [x] 변경 사항 커밋 및 완료 보고

---

## 2차 수정 작업 (2026-09-28 검토 반영)
- [x] 6. 순수 함수 및 단위 테스트 구현 (`src/dashboard/lib/`)
  - [x] `types.ts`: `SortOrder`, `RecordSummary` 타입 정의
  - [x] `filter.ts`: 공백 무시 챔피언 검색, 같은 팀(최대 3명) 필터, 승패 요약 계산, 정렬 로직 구현
  - [x] `filter.test.ts`: 챔피언 검색, 같은 팀 조건, 승패 요약, 정렬 단위 테스트 검증
- [x] 7. UI 컴포넌트 및 스타일 수정 (`src/dashboard/components/`, `DashboardApp.tsx`)
  - [x] `DashboardFilters.tsx`: 챔피언 검색창, 정렬 드롭다운, 칩 최대 3개 제한, 승패 요약, 모바일 필터 접기/펼치기
  - [x] `DashboardTabs.module.css`: 가로 스크롤바 숨김 처리
  - [x] `GameCard.tsx` & `.module.css`: 일치 챔피언/선택 플레이어 줄 강조, 480px 이하 좌우 2열 배치 및 이름/챔피언 2줄 스택
  - [x] `DashboardApp.tsx`: 정렬 상태, 검색어 상태 연동 및 GameCard 강조 props 전달
- [x] 8. 2차 수정 최종 검증 및 빌드 확인
  - [x] `npm test` 전체 통과 확인
  - [x] `npm run lint` 경고 0건 확인
  - [x] `npm run build` 다중 페이지 빌드 생성 확인
  - [x] 변경 사항 커밋 및 완료 보고
