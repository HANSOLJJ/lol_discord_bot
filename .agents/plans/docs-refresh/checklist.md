<!-- 문서 갱신 작업 체크리스트 -->
# 문서 최신화 작업 체크리스트

- [x] `docs/INFRA.md` 작성
  - [x] Cloudflare 터널 `lol` 구성(ID, 로컬 관리형, ingress 순서, ingress 검증 및 재시작)
  - [x] DNS CNAME 설정(`lol`, `lol-dev`, `arena`)
  - [x] finance 터널 독립성 및 주의점(Migrate 버튼 금지 등)
  - [x] Cloudflare Pages 도메인 분리 현황
  - [x] Cloudflare 캐시 규칙(lol-dev캐시 끄기 배경 및 동작)
  - [x] 디스코드 개발자 포털 설정(dev 앱 URL 매핑, 운영 앱 현황)
  - [x] 운영 전환 체크리스트(포털, .env, .env.production, config.json, 앱 인증)
- [x] `docs/DEPLOY_MACMINI.md` 개정
  - [x] INFRA.md 중복 내용 링크로 대체
  - [x] pm2 6개 프로세스(`lol`, `lol-web`, `lol-dev`, `lol-dev-web`, `lol-health`, `lol-tunnel`) 상세 정리
  - [x] 배포 절차(`deploy.sh`, `--dev`, 프론트엔드 단독 빌드, dev 액티비티 재오픈 주의사항)
  - [x] `.env` 키 설명 및 `DEV_MODE` 관리 규칙 최신화
  - [x] 데이터 원본(`data/`) 및 GitHub 오프사이트 백업 구조 명시
- [x] `README.md` 전면 개정
  - [x] 핵심 개요 및 아키텍처 요약
  - [x] 게임 규칙(팀 편성, 픽 순서, 20초 제한, 5·6위 어드밴티지 규칙)
  - [x] 채널 구성(1개 채널 지원 등 최신화)
  - [x] 저장소 디렉터리 구조
  - [x] 서비스 주소 표
  - [x] 운영 및 배포 명령 요약
  - [x] 문서 링크 정리
- [x] 검증 및 커밋
  - [x] 문서 내 모든 파일 링크 유효성 검사
  - [x] 문장 끝 콜론 금지 및 한국어 문장 검토
  - [x] 파이썬 및 프론트엔드 테스트 전체 통과 확인
  - [x] Git co-author trailer 없는 논리적 단위 커밋 수행
