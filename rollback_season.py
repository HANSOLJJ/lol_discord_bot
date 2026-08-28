##
# @file rollback_season.py
# @brief /시즌시작을 되돌리는 복구 스크립트 (승수 백업 복원 + current_season 감소).
# @details /시즌시작은 ① 승수를 backup/에 백업 후 0으로 초기화 ② history_data.json의
#          최상위 current_season을 +1 하는 두 가지만 바꾼다. 판 기록(games)은 건드리지
#          않으므로, 이 둘만 되돌리면 완전히 복구된다.
#          실행 후 봇을 재시작해야 메모리의 round_counter가 복원된 승수 기준으로 돌아온다.
#
#          사용법:
#            python rollback_season.py            # 무엇을 되돌릴지 보여주기만 함
#            python rollback_season.py --yes      # 실제 실행
#            python rollback_season.py --dev      # dev 파일 대상
#            python rollback_season.py --backup backup/wins_season2_20260828_120000.json
import argparse
import glob
import json
import os
import shutil

import paths
from game_recorder import get_current_season, set_current_season


##
# @brief 지정 모드(dev/실운영)의 승수 백업 중 가장 최근 파일을 찾는다.
# @param dev_mode True면 wins_dev_season*.json을 찾는다.
# @return 최근 백업 파일 경로. 없으면 None.
def find_latest_backup(dev_mode):
    suffix = "_dev" if dev_mode else ""
    pattern = os.path.join(paths.BACKUP_DIR, f"wins{suffix}_season*.json")
    candidates = sorted(glob.glob(pattern))
    return candidates[-1] if candidates else None


def main():
    parser = argparse.ArgumentParser(description="/시즌시작 되돌리기")
    parser.add_argument("--dev", action="store_true", help="dev 파일 대상")
    parser.add_argument("--backup", help="복원할 승수 백업 파일 (기본: 가장 최근)")
    parser.add_argument("--yes", action="store_true", help="실제로 실행")
    args = parser.parse_args()

    dev = args.dev
    wins_path = paths.wins_file(dev)
    backup_path = args.backup or find_latest_backup(dev)

    if not backup_path or not os.path.exists(backup_path):
        print(f"[ERROR] 복원할 승수 백업을 찾지 못했습니다 ({paths.BACKUP_DIR}/).")
        print("        --backup 으로 파일을 직접 지정하세요.")
        return 1

    current = get_current_season(dev)
    target = current - 1
    if target < 1:
        print(f"[ERROR] 현재 시즌이 {current}이라 더 되돌릴 수 없습니다.")
        return 1

    with open(backup_path, encoding="utf-8") as f:
        backup_wins = json.load(f)
    members = [k for k in backup_wins if k != "total_rounds"]

    print(f"대상 모드     : {'DEV' if dev else '실운영'}")
    print(f"시즌          : {current} -> {target}")
    print(f"승수 복원     : {backup_path} -> {wins_path}")
    print(f"                (총 {backup_wins.get('total_rounds')}라운드, {len(members)}명)")
    print("판 기록       : 건드리지 않음 (games 배열 그대로)")
    if not dev:
        print("업로드        : 복원 결과를 GitHub(lol_arena)에 반영")

    if not args.yes:
        print("\n실제로 되돌리려면 --yes 를 붙여 다시 실행하세요.")
        return 0

    # 되돌리기 직전 상태도 보관해 둔다 (잘못 되돌렸을 때를 대비)
    if os.path.exists(wins_path):
        pre = paths.season_backup_file(dev, f"{current}_rollback_pre")
        os.makedirs(paths.BACKUP_DIR, exist_ok=True)
        shutil.copy2(wins_path, pre)
        print(f"[SAVED] 되돌리기 전 승수 보관: {pre}")

    shutil.copy2(backup_path, wins_path)
    print(f"[OK] 승수 복원 완료: {wins_path}")

    set_current_season(target, dev)  # dev면 업로드는 내부에서 자동 스킵
    print(f"[OK] current_season {current} -> {target}")

    print("\n봇을 재시작하세요. round_counter가 복원된 total_rounds 기준으로 돌아옵니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
