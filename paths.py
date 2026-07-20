##
# @file paths.py
# @brief 프로젝트의 모든 데이터/산출물 파일 경로를 한곳에 모은 단일 소스(single source of truth).
# @details 폴더 구조가 바뀌면 이 파일만 수정한다. 모든 경로는 프로젝트 루트(=봇 실행 cwd) 기준 상대경로.
#          got_champe.py / game_recorder.py / parse_all_history.py 가 이 상수들을 import 해서 사용한다.
import os

## 봇 설정 파일 (루트).
CONFIG_FILE = "config.json"

## 데이터 폴더 (개인 승수 + 판 상세 마스터).
DATA_DIR = "data"


##
# @brief DEV_MODE에 따라 개인 승수 파일 경로를 반환한다.
# @param dev_mode True면 테스트용(wins_dev.json), False면 실운영(wins.json).
# @return 승수 json 파일 경로.
def wins_file(dev_mode):
    name = "wins_dev.json" if dev_mode else "wins.json"
    return os.path.join(DATA_DIR, name)


##
# @brief DEV_MODE에 따라 판 상세 마스터(history_data.json) 경로를 반환한다.
# @details 이 json이 마스터이자 lol_arena repo로 업로드되는 파일(대시보드가 직접 fetch).
# @param dev_mode True면 history_data_dev.json.
# @return json 파일 경로.
def history_json(dev_mode=False):
    suffix = "_dev" if dev_mode else ""
    return os.path.join(DATA_DIR, f"history_data{suffix}.json")
