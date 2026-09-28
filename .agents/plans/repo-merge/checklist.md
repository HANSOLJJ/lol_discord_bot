<!-- 봇·웹 저장소 통합 작업 체크리스트 -->
# 봇·웹 저장소 통합 체크리스트

계획은 [plan.md](plan.md), 결정 기록은 [context-notes.md](context-notes.md)에 있다.

- [ ] 사용자가 2절 기본안(기준 저장소, web/ 위치, 이력 보존, lol_arena 유지)을 확인한다.
- [ ] 봇 `HANSOLJJ/activity-server`를 main에 병합한다(서버 v2 검증 후).
- [ ] lol_arena `HANSOLJJ/activity-frontend`를 main에 병합한다(픽 화면 수정·약관 검증 후).
- [ ] lol_arena `HANSOLJJ/dashboard-tabs`를 main에 병합한다.
- [ ] lol_arena 루트 index.html 미커밋 서식 변경의 처리를 사용자와 정한다.
- [ ] 봇 저장소에 `git subtree add --prefix=web`으로 lol_arena를 가져온다.
- [ ] `web/history_data.json` 추적을 끊고 무시 규칙을 합친다.
- [ ] 문서·워크스페이스·Orca 등록의 경로를 고친다.
- [ ] 봇 테스트, web/activity build·lint·test를 통과한다.
- [ ] dev 봇과 액티비티 개발 서버를 새 위치에서 실행해 확인한다.
- [ ] 사용자가 push한다.
