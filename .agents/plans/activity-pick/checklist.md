# 체크리스트: 픽 화면 액티비티 개편

계획 원본: [docs/ACTIVITY_DESIGN.md](../../../docs/ACTIVITY_DESIGN.md) (10절 구현 순서). 결정 기록: [context-notes.md](context-notes.md).

## 0. 자동 기동 (pm2)
- [ ] `ecosystem.config.cjs` 작성·커밋
- [ ] 맥미니: `git pull` → `pm2 start ecosystem.config.cjs` → `pm2 save`
- [ ] `pm2 restart lol` 정상 종료·재기동 확인
- [ ] 재부팅 테스트 (finance와 lol 둘 다 자동 복귀)

## 1. 측정용 골격
- [ ] dev 앱 `롤랜덤챔프봇-dev` 생성 (설계 9-2절, 사용자): Bot 토큰·intents, OAuth2 id·secret·redirect, TEST2 초대, Activities, URL Mapping
- [ ] 윈도우 `.env`를 dev 앱 값으로 교체, TEST2 채널 3개 확인
- [ ] Vite·SDK·윈도우 cloudflared 설치 사용자 승인
- [ ] `activity_server.py` (token·ws·ping/pong)
- [ ] `got_champe.py` 실행 구조를 `asyncio.run(main())`으로
- [ ] `lol_arena/activity/` Vite 골격 (ready → authorize → token → ws → ping 100회 RTT 표시)
- [ ] PC·모바일 RTT 분포 기록 → context-notes (게이트: p95 < 1초)
- [ ] 텍스트 채널 LAUNCH_ACTIVITY 동작 확인
- [ ] Entry Point 커맨드와 `sync_commands()` 충돌 여부 확인

## 2. apply_pick 분리
- [ ] 락 안 판단·변경을 `apply_pick(user_id, champ_name, received_at)`로 추출
- [ ] exec 테스트 전후 동일
- [ ] DEV 서버 embed 모드 한 판

## 3. activity 모드 서버
- [ ] `config.json` `pick_ui` 스위치 (기본 `embed`)
- [ ] 선계산 마감 타이머·자동 시작
- [ ] 상태 스냅샷 + broadcast (락 안 생성, 락 밖 전송)
- [ ] ws pick 처리 (턴·세대·마감+유예·재클릭 취소)
- [ ] 현황판 embed + "픽 화면 열기" (LAUNCH_ACTIVITY raw 응답)
- [ ] `.env.example` 키 추가

## 4. 액티비티 화면
- [ ] 카운트다운 (offset 보정, rAF)
- [ ] 챔프 그리드·선택 현황·토스트·끊김 배지·재접속
- [ ] 디스코드 밖 직접 접속 안내
- [ ] `npm run build` → `lol_arena/pick/` 커밋
- [ ] dev 앱으로 한 판 (DEV_MODE)

## 5. 운영 전환
- [ ] 운영 앱 Activities·URL Mapping·OAuth
- [ ] 터널 ingress + `tunnel route dns` (작업 시각 사용자와 조율)
- [ ] 맥미니 `.env` 비밀 추가, `pick_ui: "activity"`, `pm2 restart lol`
- [ ] 실전 한 판 → 대시보드 기록 반영

## 6. 정리 (사용자가 시점 결정)
- [ ] 구 카운트다운 코드·`pick_ui` 스위치 삭제
- [ ] CLAUDE.md·README·AGENTS.md 갱신
