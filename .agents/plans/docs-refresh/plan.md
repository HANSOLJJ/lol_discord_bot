<!-- 문서 최신화 및 인프라 구조 정리 계획 -->
# 문서 최신화 및 인프라 구조 정리 계획

## 1. 개요 및 목적
리그 오브 레전드 3:3 투기장 디스코드 봇은 웹 전적 대시보드 및 디스코드 액티비티(`web/activity`)가 통합되고 맥미니 환경에서 pm2 프로세스로 운영되는 구조로 발전했습니다.
현재 `README.md`는 봇 단독 운영 시절의 오래된 내용(arena.dcom.co.kr, GitHub Pages 배포, 3개 채널 필수 제약 등)이 남아 있어 실제 시스템 구조와 불일치합니다.
또한 2026-09-29 코디네이터가 구성한 Cloudflare 터널, DNS, 캐시 규칙, 디스코드 개발자 포털 설정 및 운영 전환 체크리스트가 저장소 내 문서로 체계화되어 있지 않습니다.
본 작업은 새로 합류한 개발자나 에이전트가 저장소 문서만으로 전체 아키텍처와 운영 절차를 파악할 수 있도록 문서를 정비합니다.

## 2. 작업 대상 및 범위
1. `docs/INFRA.md` (신규 작성)
   - Cloudflare 터널(`lol`), DNS CNAME, ingress 라우팅 순서, 캐시 바이패스 규칙 정리
   - finance 터널과의 완전 분리 배경 및 주의사항
   - Cloudflare Pages 도메인 분리 현황
   - 디스코드 개발자 포털 dev/운영 앱 설정 및 운영 전환 체크리스트
2. `docs/DEPLOY_MACMINI.md` (개정)
   - 인프라 세부사항은 `docs/INFRA.md`로 링크하고 맥미니 운영 절차에 집중
   - 6개 pm2 프로세스 구성 및 역할 최신화
   - 배포(`scripts/deploy.sh`, `--dev`, 프론트엔드 단독 빌드) 및 로그 확인 절차 정리
   - `.env` 환경변수 키 목록 최신화 및 `DEV_MODE` 관리 방식 명시
   - 데이터 원본(`data/`)과 GitHub API 기반 오프사이트 백업 구조 명시
3. `README.md` (전면 개정)
   - 프로젝트 개요 및 아키텍처 요약
   - 게임 핵심 규칙 (팀 편성, 픽 순서, 20초 제한, 5·6위 어드밴티지 규칙 v3)
   - 서비스 주소 표 및 디렉터리 구조
   - 일상 운영 명령어 요약 및 세부 문서 목록 링크
4. 계획 및 결정 기록 (`.agents/plans/docs-refresh/`)

## 3. 성공 기준
- 사실 관계가 코드(`config.json`, `ecosystem.config.cjs`, `web_server.py`, `scripts/deploy.sh`, `scripts/healthcheck.py`, `docs/ACTIVITY_PROTOCOL.md`)와 정확히 일치함.
- 세 문서가 각각 독립된 논리적 단위로 커밋되고 커밋 메시지는 한국어 단일 문장으로 작성됨.
- Git co-author trailer를 일절 사용하지 않음.
- 문서 내 모든 상호 링크가 실제 존재하는 파일을 정확히 가리킴.
- 전체 유닛 테스트(`python -m unittest discover tests`, `npm test`)가 통과함.
