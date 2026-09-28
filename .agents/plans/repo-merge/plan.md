<!-- 봇 저장소와 lol_arena 저장소를 하나로 합치는 계획 -->
# 봇·웹 저장소 통합 계획

체크리스트는 [checklist.md](checklist.md), 결정과 근거는 [context-notes.md](context-notes.md)에 있다.
상위 계획은 [activity-integration/plan.md](../activity-integration/plan.md) 9-1·9-2절이다.

## 1. 목표

- 봇 코드, 웹 소스(액티비티·전적 대시보드), 통신 규격 문서와 테스트를 한 저장소에서 관리한다(2026-09-28 사용자 결정: "합칠 것").
- 맥미니에서는 이 저장소 하나만 받아서 봇(pm2 `lol`)과 정적 웹 서버(pm2 `lol-web`, 127.0.0.1:8791)를 함께 돌린다.

## 2. 기본안 (사용자 확인 필요)

| 항목 | 기본안 | 이유 |
|---|---|---|
| 기준 저장소 | `HANSOLJJ/lol_discord_bot` | 맥미니 봇 경로(`~/projects/lol_discord_bot`), pm2 cwd, `paths.py` 상대경로를 그대로 둘 수 있다 |
| 웹 위치 | 저장소 안 `web/` (지금 lol_arena 루트 → `web/`) | 계획 9-1절의 최소 변경안이다 |
| 이력 | lol_arena 이력을 보존해 가져온다(`git subtree add --prefix=web`) | 대시보드·액티비티 변경 이력이 남는다 |
| lol_arena 저장소 | 합친 뒤에도 당분간 남긴다. 맥미니 전환 전까지 GitHub Pages로 사이트를 계속 공개하고, 봇의 history_data.json 오프사이트 백업 업로드 대상으로 쓴다 | 전환 공백을 없앤다 |
| `web/history_data.json` | 합친 저장소에서는 추적하지 않는다 | 원본은 봇의 `data/history_data.json`(추적 안 함)이고, 정적 서버가 그 파일을 직접 서빙한다 |

## 3. 순서

1. 진행 중인 작업 브랜치를 각 저장소의 main에 먼저 병합한다: 봇 `HANSOLJJ/activity-server`(서버 v2), lol_arena `HANSOLJJ/activity-frontend`(대전 기록·픽 화면·약관), `HANSOLJJ/dashboard-tabs`(5개 탭 이관). 옮기는 도중에 경로가 바뀌면 이 브랜치들을 병합하기 어려워진다.
2. lol_arena main의 미커밋 변경(루트 index.html 서식 변경)을 처리한다. 사용자 결정 전까지는 커밋하지 않고 그대로 둔다.
3. 봇 저장소에서 `git subtree add --prefix=web <lol_arena 로컬 경로> main`으로 가져온다. 결과 트리와 이력을 확인한다.
4. `web/history_data.json` 추적을 끊고 `.gitignore`에 넣는다. 루트 `.gitignore`와 `web/`의 무시 규칙(node_modules, dist)을 합친다.
5. 경로를 참조하는 곳을 고친다: 문서의 lol_arena 경로, 부모 폴더의 `lol.code-workspace`, Orca 저장소 등록, 개발 서버 실행 위치.
6. 검증: 봇 테스트, `web/activity`의 build·lint·test, dev 봇과 액티비티 개발 서버 실제 실행.
7. 원격 반영(push)은 사용자가 한다.

## 4. 하지 않는 것

- lol_arena 저장소를 지우거나 보관(archive) 처리하지 않는다. 맥미니 전환이 끝난 뒤 따로 정한다.
- 봇의 GitHub 백업 업로드 경로(`ARENA_GH_REPO`)는 바꾸지 않는다.
- 작업 트리를 파괴하는 명령(`reset --hard`, `clean`)을 쓰지 않는다.
