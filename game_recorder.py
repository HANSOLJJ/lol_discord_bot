##
# @file game_recorder.py
# @brief 승리 확정 시 판 기록을 history_data.json에 추가하고 GitHub Pages에 배포하는 모듈.
# @details 봇(got_champe.py)이 판마다 호출한다. 로컬 마스터 데이터(history_data.json)를 갱신한 뒤,
#          설정이 있으면 GitHub Contents API로 이 json을 lol_arena 리포에 커밋한다(대시보드가 직접 fetch).
#          업로드 실패는 봇 동작에 영향을 주지 않는다.
import base64
import json
import os
import threading
from datetime import datetime, timezone

import paths


##
# @brief 로컬 파일을 GitHub Contents API로 리포에 커밋(생성/갱신)한다.
# @details .env의 ARENA_GH_TOKEN/ARENA_GH_REPO가 설정된 경우에만 동작하며, 미설정 시 조용히
#          반환한다. 기존 파일이면 현재 sha를 조회해 함께 PUT하고(없으면 신규 생성),
#          sha 경합(409)이면 재조회 후 1회 재시도한다. Contents API는 단일 커밋이라 별도 원자성
#          처리가 필요없다. 모든 예외는 내부에서 삼켜 로그만 남긴다.
# @param local_path 업로드할 로컬 파일 경로.
# @param remote_path 리포 내 대상 경로(예: "history_data.json").
# @param message 커밋 메시지.
# @return bool 성공하면 True, 미설정/실패면 False.
def _github_put_file(local_path, remote_path, message):
    token = os.getenv("ARENA_GH_TOKEN")
    repo = os.getenv("ARENA_GH_REPO")  # 예: "HANSOLJJ/lol_arena"
    if not token or not repo:
        return False  # 미설정이면 조용히 스킵 (로컬 기록만)
    branch = os.getenv("ARENA_GH_BRANCH", "main")
    try:
        import requests
        url = f"https://api.github.com/repos/{repo}/contents/{remote_path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        with open(local_path, "rb") as f:
            content_b64 = base64.b64encode(f.read()).decode()

        def _get_sha():  # 기존 파일 sha 조회 (없으면 404 → None → 신규 생성)
            r = requests.get(url, headers=headers, params={"ref": branch}, timeout=15)
            return r.json().get("sha") if r.status_code == 200 else None

        body = {"message": message, "content": content_b64, "branch": branch}
        sha = _get_sha()
        if sha:
            body["sha"] = sha
        r = requests.put(url, headers=headers, json=body, timeout=15)
        if r.status_code == 409:  # sha 경합 → 재조회 후 1회 재시도
            body["sha"] = _get_sha()
            r = requests.put(url, headers=headers, json=body, timeout=15)
        if r.status_code in (200, 201):
            print(f"[UPLOAD] {remote_path} -> GitHub Pages 반영 완료")
            return True
        print(f"[WARN] GitHub 업로드 실패 {r.status_code}: {r.text[:200]}")
        return False
    except Exception as e:
        print(f"[WARN] GitHub 업로드 실패 (로컬 기록은 정상): {e}")
        return False


##
# @brief history_data.json을 GitHub 리포에 커밋해 GitHub Pages에 반영한다.
# @param local_json 업로드할 로컬 json 파일 경로.
# @return 없음.
def _upload_to_github(local_json):
    remote = os.getenv("ARENA_GH_PATH", "history_data.json")
    _github_put_file(local_json, remote, "chore: update history_data.json")


##
# @brief GitHub Pages 업로드를 백그라운드 스레드에서 실행한다.
# @details 승리 처리(async 이벤트 루프)를 막지 않도록 daemon 스레드로 분리한다.
#          dev 모드에서는 테스트 데이터를 배포하지 않도록 스킵한다.
# @param dev_mode True면 업로드하지 않음.
# @return 없음.
def upload_async(dev_mode=False):
    if dev_mode:
        return
    json_path = paths.history_json(dev_mode)
    threading.Thread(target=_upload_to_github, args=(json_path,), daemon=True).start()


##
# @brief 한 판 결과를 history_data.json에 append하고 GitHub Pages 업로드까지 수행한다.
# @details 라운드 번호가 직전 기록 이하로 회귀하면(예: R32 다음에 R1) 새 시즌으로 판정한다
#          (시즌 시작 = wins.json 리셋 = round_counter 1부터 재시작). 파일이 없으면
#          빈 스켈레톤을 생성한다. players 매핑은 처음 보는 id만 추가해 기존 이름을 보존한다.
# @param round_num 현재 라운드 번호(round_counter).
# @param teams {"team1": [{"id","name","champ"}]x3, "team2": [...]} 형태의 양 팀 정보.
# @param winner 승리 팀 키. "team1" 또는 "team2".
# @param dev_mode True면 history_data_dev.*에 기록(테스트 분리).
# @return int 기록된 시즌 번호.
def record_game(round_num, teams, winner, dev_mode=False):
    json_path = paths.history_json(dev_mode)

    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {
            "generated_at": None,
            "channels": [],
            "total_games": 0,
            "players": {},
            "sessions_summary": [],
            "games": [],
        }

    games = data["games"]
    # 시즌 판정: 라운드가 직전 기록 이하로 돌아가면 새 시즌
    if not games:
        season = 1
    elif round_num <= games[-1]["round"]:
        season = games[-1]["season"] + 1
    else:
        season = games[-1]["season"]

    now = datetime.now(timezone.utc).isoformat()
    games.append({
        "round": round_num,
        "round_orig": round_num,
        "season": season,
        "team1": [{"id": p["id"], "champ": p["champ"]} for p in teams["team1"]],
        "team2": [{"id": p["id"], "champ": p["champ"]} for p in teams["team2"]],
        "winner": winner,
        "time": now,
        "sources": ["BOT"],
    })

    # 이름 매핑은 처음 보는 id만 추가 (기존 이름 보존)
    for p in teams["team1"] + teams["team2"]:
        data["players"].setdefault(p["id"], p.get("name") or p["id"])

    data["total_games"] = len(games)
    data["generated_at"] = now

    # 대상 폴더(data/)가 없으면 생성
    os.makedirs(os.path.dirname(json_path), exist_ok=True)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # GitHub Pages 자동 반영 (백그라운드, 실패해도 무해 - 다음 성공 업로드가 전체 파일이라 자동 만회)
    upload_async(dev_mode)

    return season
