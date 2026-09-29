<!-- 봇·웹 저장소 통합 작업 체크리스트 -->
# 봇·웹 저장소 통합 체크리스트

계획은 [plan.md](plan.md), 결정 기록은 [context-notes.md](context-notes.md)에 있다.

- [x] 사용자가 2절 기본안(기준 저장소, web/ 위치, 이력 보존, lol_arena 유지)을 확인한다(2026-09-28 "1번 진행").
- [x] 봇 `HANSOLJJ/activity-server`를 main에 병합한다(서버 v2 검증 후).
- [x] lol_arena `HANSOLJJ/activity-frontend`를 main에 병합한다(f4b1634).
- [x] lol_arena `HANSOLJJ/dashboard-tabs`를 main에 병합한다(68cec77).
- [x] ~~lol_arena 루트 index.html 미커밋 서식 변경의 처리를 사용자와 정한다. 합칠 때는 커밋된 버전만 들어갔다.~~ (취소: lol_arena 지원 중단·로컬 클론 삭제로 서식 처리 불필요)
- [x] 봇 저장소에 lol_arena를 이력째 `web/`으로 가져온다(87d8e03). 봇 쪽 미커밋 서식 변경 때문에 `git subtree add` 대신 `merge -s ours --allow-unrelated-histories` + `read-tree --prefix=web/ -u`를 썼다.
- [x] `web/history_data.json` 추적을 끊는다(1f6f22b). 루트 .gitignore의 `history_data.json` 규칙이 그대로 적용된다.
- [x] 문서·워크스페이스·Orca 등록의 경로를 고친다. 통신 규격 문서는 고쳤다. 계획 문서의 옛 `lol_arena/` 경로는 이력 기록이라 그대로 둔다. (확인 필요: 워크스페이스·Orca 등록 경로 잔존 여부) / Orca 저장소 등록 경로도 lol_discord_bot으로 정리(2026-09-29)
- [x] 봇 테스트(97개), web/activity build·lint·test(214개)를 통과한다.
- [x] dev 봇과 액티비티 개발 서버를 새 위치에서 실행해 확인한다. (맥미니 dev 배포·어드밴티지 dev 확인에 포함)
- [x] 사용자가 push한다. (web/ 병합분이 origin/main ba0ae02까지 반영됨)
