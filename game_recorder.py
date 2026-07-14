# 승리 확정 시 판 기록을 history_data.json/.js에 추가하는 모듈 (봇 직접 기록, 대시보드 데이터 소스)
import json
import os
from datetime import datetime, timezone


def _file_paths(dev_mode):
    base = "history_data_dev" if dev_mode else "history_data"
    return base + ".json", base + ".js"


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

    return season
