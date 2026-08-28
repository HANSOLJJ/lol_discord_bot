##
# @file paths.py
# @brief 프로젝트의 모든 데이터/산출물 파일 경로를 한곳에 모은 단일 소스(single source of truth).
# @details 폴더 구조가 바뀌면 이 파일만 수정한다. 모든 경로는 프로젝트 루트(=봇 실행 cwd) 기준 상대경로.
#          got_champe.py / game_recorder.py / parse_all_history.py 가 이 상수들을 import 해서 사용한다.
import os
from datetime import datetime

## 봇 설정 파일 (루트).
CONFIG_FILE = "config.json"

## 데이터 폴더 (개인 승수 + 판 상세 마스터).
DATA_DIR = "data"

## 백업 폴더 (시즌 마감 시 직전 시즌 승수를 보관).
BACKUP_DIR = "backup"


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


##
# @brief 시즌 마감 시 보관할 승수 백업 파일 경로를 반환한다.
# @details 시즌 번호와 시각을 파일명에 넣어, 같은 시즌을 다시 마감해도 기존 백업을
#          덮어쓰지 않는다.
# @param dev_mode True면 파일명에 _dev를 붙인다.
# @param season 마감되는(직전) 시즌 번호.
# @return 백업 파일 경로.
def season_backup_file(dev_mode, season):
    suffix = "_dev" if dev_mode else ""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(BACKUP_DIR, f"wins{suffix}_season{season}_{stamp}.json")
