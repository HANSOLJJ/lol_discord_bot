##
# @file game_recorder.py
# @brief 승리 확정 시 판 기록을 history_data.json/.js에 추가하고 호스팅에 배포하는 모듈.
# @details 봇(got_champe.py)이 판마다 호출한다. 로컬 마스터 데이터(history_data.json)와
#          대시보드 로드용(history_data.js)을 갱신한 뒤, 설정이 있으면 호스팅에 SFTP로
#          자동 업로드한다. 업로드 실패는 봇 동작에 영향을 주지 않는다.
import json
import os
import threading
from datetime import datetime, timezone


##
# @brief DEV_MODE에 따라 사용할 데이터 파일 경로를 반환한다.
# @param dev_mode True면 테스트용(history_data_dev.*), False면 실운영(history_data.*).
# @return (json_path, js_path) 튜플.
def _file_paths(dev_mode):
    base = "history_data_dev" if dev_mode else "history_data"
    return base + ".json", base + ".js"


##
# @brief history_data.js를 호스팅(SFTP)에 업로드한다.
# @details .env의 ARENA_SSH_HOST/USER/PASS/REMOTE_PATH가 모두 설정된 경우에만 동작하며,
#          미설정 시 조용히 반환한다. 업로드 중 반쪽 파일 노출을 막기 위해 임시 파일에
#          올린 뒤 원자적으로 rename 한다. 모든 예외는 내부에서 삼켜 로그만 남긴다.
# @param local_js 업로드할 로컬 .js 파일 경로.
# @return 없음.
def _upload_to_hosting(local_js):
    host = os.getenv("ARENA_SSH_HOST")
    user = os.getenv("ARENA_SSH_USER")
    password = os.getenv("ARENA_SSH_PASS")
    remote = os.getenv("ARENA_REMOTE_PATH")
    if not all([host, user, password, remote]):
        return  # 미설정이면 조용히 스킵 (로컬 기록만)
    try:
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=user, password=password, timeout=15)
        sftp = ssh.open_sftp()
        tmp = remote + ".tmp"
        sftp.put(local_js, tmp)
        sftp.posix_rename(tmp, remote)  # 원자적 교체 (업로드 중 반쪽 파일 노출 방지)
        sftp.close()
        ssh.close()
        print("[UPLOAD] history_data.js -> 호스팅 반영 완료")
    except Exception as e:
        print(f"[WARN] 호스팅 업로드 실패 (로컬 기록은 정상): {e}")


##
# @brief 호스팅 업로드를 백그라운드 스레드에서 실행한다.
# @details 승리 처리(async 이벤트 루프)를 막지 않도록 daemon 스레드로 분리한다.
#          dev 모드에서는 테스트 데이터를 배포하지 않도록 스킵한다.
# @param dev_mode True면 업로드하지 않음.
# @return 없음.
def upload_async(dev_mode=False):
    if dev_mode:
        return
    _, js_path = _file_paths(dev_mode)
    threading.Thread(target=_upload_to_hosting, args=(js_path,), daemon=True).start()


##
# @brief 한 판 결과를 history_data 파일에 append하고 .js 재생성 + 호스팅 업로드까지 수행한다.
# @details 라운드 번호가 직전 기록 이하로 회귀하면(예: R32 다음에 R1) 새 시즌으로 판정한다
#          (시즌 시작 = wins.json 리셋 = round_counter 1부터 재시작). 파일이 없으면
#          빈 스켈레톤을 생성한다. players 매핑은 처음 보는 id만 추가해 기존 이름을 보존한다.
# @param round_num 현재 라운드 번호(round_counter).
# @param teams {"team1": [{"id","name","champ"}]x3, "team2": [...]} 형태의 양 팀 정보.
# @param winner 승리 팀 키. "team1" 또는 "team2".
# @param dev_mode True면 history_data_dev.*에 기록(테스트 분리).
# @return int 기록된 시즌 번호.
def record_game(round_num, teams, winner, dev_mode=False):
    json_path, js_path = _file_paths(dev_mode)

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

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("// 자동 생성 - 봇이 판마다 갱신. 직접 수정 금지.\n")
        f.write("window.HISTORY_DATA = ")
        json.dump(data, f, ensure_ascii=False)
        f.write(";\n")

    # 호스팅 자동 반영 (백그라운드, 실패해도 무해 - 다음 성공 업로드가 전체 파일이라 자동 만회)
    upload_async(dev_mode)

    return season
