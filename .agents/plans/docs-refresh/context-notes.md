<!-- 문서 갱신 작업의 주요 결정과 배경 기록 -->
# 문서 최신화 결정 기록

## 2026-09-29
- 코디네이터가 2026-09-29에 구성한 Cloudflare 터널 및 맥미니 운영 환경 사실을 공식 문서화함.
- `pick.hansoljj.com`은 초기 계획에만 있었고 현재 사용하지 않으므로 문서에서 사용하지 않음을 명확히 기록함.
- `arena.hansoljj.com`은 Cloudflare Pages 사용자 지정 도메인에서 분리되었으며, 현재는 맥미니 정적 웹 서버(8791)로 인입되어 `lol.hansoljj.com`으로 301 리다이렉트됨.
- `lol-dev.hansoljj.com` 캐시 바이패스 규칙은 Vite 개발 서버가 제공하는 무해시 CSS 파일을 디스코드 액티비티가 장시간(4시간) 캐싱하여 깨지는 이슈를 방지하기 위해 필수적임.
- 운영 전환 체크리스트 5단계를 `docs/INFRA.md`에 집약하여 향후 운영 봇의 액티비티 전환 시 참조할 수 있도록 함.
- README.md는 세부 기술 스펙보다 핵심 규칙, 디렉터리 구조, 주소 표, 일상 명령 및 문서 목록으로 구성하여 첫 진입자에게 명확한 길잡이를 제공함.
- 코디네이터 추가 지시 반영:
  - `docs/INFRA.md`를 Cloudflare, DNS, 터널, Pages, 캐시 규칙, URL 매핑의 단일 기준 문서로 확립.
  - `docs/INFRA.md` 끝에 인프라 변경 이력 표를 추가하여 과거 계획과의 차이를 명확히 함.
  - `.agents/plans/`의 계획 문서(`activity-integration`, `macmini-deploy`, `match-history`)는 결정 기록이므로 본문을 유지하되, Cloudflare/터널/주소 관련 절 아래에 `> 현재 설정은 docs/INFRA.md가 기준이다. 이 절은 당시 계획 기록이다.` 한 줄 안내를 삽입함.
  - `handover.md`를 `docs/archive/handover-workers-2026-08.md`로 이동하고 상단에 폐기 안내문 삽입 및 README 아카이브 섹션에 링크.
- 모든 문서 내 상대 링크 및 URL의 실효성 검증 완료.
