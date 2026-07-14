# 승리 확정 시 판 기록을 history_data.json/.js에 추가하는 모듈 (봇 직접 기록, 대시보드 데이터 소스)
import json
import os
import threading
from datetime import datetime, timezone


def _file_paths(dev_mode):
    base = "history_data_dev" if dev_mode else "history_data"
    return base + ".json", base + ".js"


def _upload_to_hosting(local_js):
    """history_data.js를 호스팅(SFTP)에 업로드. .env에 ARENA_SSH_* 설정이 있을 때만 동작."""
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


def upload_async(dev_mode=False):
    """백그라운드 스레드로 호스팅 업로드 (승리 처리 흐름을 막지 않음). dev 모드는 스킵."""
    if dev_mode:
        return
    _, js_path = _file_paths(dev_mode)
    threading.Thread(target=_upload_to_hosting, args=(js_path,), daemon=True).start()


def record_game(round_num, teams, winner, dev_mode=False):
    """
    한 판 결과를 history_data 파일에 append하고 .js를 재생성.

    Args:
        round_num (int): 현재 라운드 번호 (round_counter)
        teams (dict): {"team1": [{"id": str, "name": str, "champ": str}]x3, "team2": [...]}
        winner (str): "team1" 또는 "team2"
        dev_mode (bool): True면 history_data_dev.*에 기록 (테스트 분리)

    Returns:
        int: 기록된 시즌 번호
    """
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
    # (시즌 시작 = wins.json 리셋 = round_counter가 1부터 재시작)
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
