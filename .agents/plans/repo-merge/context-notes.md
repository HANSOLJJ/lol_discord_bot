<!-- 봇·웹 저장소 통합 작업의 결정과 근거 기록 -->
# 봇·웹 저장소 통합 결정 기록

## 2026-09-28 (코디네이터 기록)

- 사용자 결정: 두 저장소를 합친다. 앱은 디스코드 앱 인증을 받는 방향으로 간다.
- 확인한 현황: 두 저장소 모두 GitHub 공개 저장소이다(`HANSOLJJ/lol_discord_bot`, `HANSOLJJ/lol_arena`). 봇 저장소는 2026-09-16 이후 로컬 커밋이 원격에 올라가지 않았다. lol_arena는 봇이 판마다 history_data.json을 GitHub API로 커밋해 2026-09-26까지 갱신됐다.
- 기준 저장소를 봇 저장소로 둔 이유: 맥미니의 봇 실행 경로, pm2 설정, `paths.py`의 상대경로가 모두 봇 저장소 루트 기준이다. 웹은 빌드 결과만 서빙하면 되므로 하위 폴더로 들어가도 영향이 작다.
- 합치는 시점을 진행 중인 세 브랜치 병합 뒤로 둔 이유: `git subtree add` 뒤에는 lol_arena 쪽 브랜치를 그대로 병합할 수 없고 경로를 옮겨 다시 적용해야 한다.
- 맥미니 배포 준비물(정적 서버, pm2 설정, 배포 스크립트, 장애 알림)은 합친 저장소 구조(`web/`)를 기준으로 만든다.

## 2026-09-28 합치기 실행 (코디네이터 기록)

- 사용자가 기본안대로 진행하라고 했다.
- 봇 main에 서버 v2 브랜치를 병합했고, lol_arena main에 픽 화면·대시보드(`HANSOLJJ/activity-frontend`)와 5개 탭 이관(`HANSOLJJ/dashboard-tabs`)을 병합했다. 두 브랜치 모두 루트 index.html·history_data.json을 건드리지 않아, lol_arena의 미커밋 서식 변경은 그대로 남겼다.
- `git subtree add`는 작업 트리에 수정이 있으면 거부한다. 봇 저장소에는 사용자의 미커밋 서식 변경(game_recorder.py 등)이 있어서, 같은 결과를 내는 수동 방식을 썼다: lol_arena main을 fetch → `merge -s ours --no-commit --allow-unrelated-histories FETCH_HEAD` → `read-tree --prefix=web/ -u FETCH_HEAD` → 커밋. 사용자 파일은 건드리지 않았다.
- 합친 뒤 `web/activity`에서 `npm ci`(잠금 파일 그대로)로 의존성을 설치하고 build·lint·test 214개, 봇 unittest 97개가 통과했다.
- lol_arena 저장소는 지우지 않았다. 맥미니 전환 전까지 사이트 공개(Pages)와 봇의 history_data.json 백업 업로드 대상으로 쓴다. 앞으로 웹 코드는 봇 저장소의 `web/`에서 고친다.
