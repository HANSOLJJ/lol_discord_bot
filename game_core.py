# 디스코드 명령과 액티비티가 함께 쓰는 게임 상태와 판 만들기·자동 배정·승리 기록·번복 처리
##
# @file game_core.py
# @brief 게임 상태와 게임 락을 소유하고, 디스코드 응답과 분리한 공통 게임 함수를 제공한다.
# @details got_champe.py(디스코드 명령·버튼)와 activity_server.py(액티비티 요청)가 같은 객체, 같은 락,
#          같은 함수를 쓴다. 디스코드를 import하지 않고 파일 저장 함수와 시계를 주입받으므로 테스트에서
#          가짜 저장소와 가짜 시계로 검증할 수 있다. 메시지 문구와 저장 순서는 기존 /승리·/번복과 같다.
import asyncio
import copy
import logging
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

import game_recorder
from game_recorder import SeasonMismatchError

log = logging.getLogger("game")

MAX_PLAYERS = 6
DEFAULT_PICK_TIMEOUT = 20  # config.json에 pick_timeout이 없을 때 쓰는 폴백(초)
# /게임시작 후 챔피언 선택이 자동으로 시작되기까지의 시간. 예전엔 시작 버튼을 눌러야 했는데,
# 아무나 누를 수 있어서 팀·챔프 카드를 보기도 전에 픽이 시작되는 일이 있었다.
DEFAULT_AUTO_START_SECONDS = (
    10  # config.json에 auto_start_seconds가 없을 때 쓰는 폴백(초)
)
# 카운트가 0에 닿은 뒤 자동 배정까지의 유예(초). 이 안에 디스코드가 접수한 클릭은 모두 인정한다.
# 채널마다 편집 반영이 늦을 수 있어서(보통 0.3초, 느린 채널은 1~2.6초 실측) 늦게 본 사람이 화면의
# "1초"를 보고 눌러도 손해 보지 않게 하려는 것이다. 픽은 자기 차례만 할 수 있고 순서대로라서 이 여유가
# 다른 선수에게 손해가 되지 않는다. 1초로는 빠듯했다(2026-09-09 실측).
DEFAULT_PICK_GRACE_SECONDS = 2.0  # config.json에 pick_grace_seconds가 없을 때 쓰는 폴백(초)
TEAM_KEYS = ("team1", "team2")


##
# @brief 이미 선택된 챔피언을 제외하고 랜덤으로 챔피언을 뽑는다.
# @param champion_list 전체 챔피언 리스트.
# @param excluded_champs 제외할 챔피언 이름 집합.
# @param count 뽑을 챔피언 수(기본값 8).
# @param rng 난수 생성기(기본값 random 모듈).
# @return 선택된 챔피언 리스트(남은 챔피언이 count보다 적으면 빈 리스트).
def pick_random_champions(champion_list, excluded_champs, count=8, rng=random):
    available = [
        champ for champ in champion_list if champ["name"] not in excluded_champs
    ]
    if len(available) < count:
        return []
    return rng.sample(available, count)


##
# @brief new_game()의 결과.
# @details ok가 False면 챔피언 목록이 부족해 판을 만들지 못한 것이다(팀과 픽 순서는 이미 정해졌다).
@dataclass
class NewGame:
    ok: bool
    pool_reset: bool  # 챔피언 풀이 소진돼 제외 목록을 비우고 다시 뽑았는가
    champ_count: int


##
# @brief record_result_locked()의 결과.
# @details code가 "ok"가 아니면 message가 디스코드에 그대로 보낼 거절 문구다.
@dataclass
class RecordOutcome:
    code: str  # "ok" | "already_recorded" | "no_game" | "not_picked" | "record_failed"
    message: str
    round: Optional[int] = None
    team_key: Optional[str] = None
    teams: dict = field(default_factory=dict)  # {"team1": [member...], "team2": [...]} 기록 시점 사본
    selections: dict = field(default_factory=dict)  # {user_id: 챔피언 이름} 기록 시점 사본
    season_warning: Optional[str] = None  # 판 기록이 시즌 불일치로 중단됐을 때 채널에 보낼 경고


##
# @brief 게임 상태와 게임 락. 봇 프로세스에 하나만 둔다.
# @details 속성 이름은 예전 got_champe.py 전역 변수 이름을 그대로 쓴다.
class GameCore:

    ##
    # @param dev_mode DEV_MODE 여부.
    # @param save_wins 승수 데이터를 저장하는 함수(data). 실패하면 예외를 던진다.
    # @param record_game 판 기록 함수(round, teams, winner, dev_mode) → 시즌.
    # @param find_game 판 기록 조회 함수(round, dev_mode) → 판 dict 또는 None.
    # @param set_game_winner 판 기록 승자 변경 함수(round, winner, dev_mode).
    # @param get_season 현재 시즌 조회 함수(dev_mode) → int.
    # @param clock 단조 시계(초). 마감 판정에만 쓴다.
    # @param wall_ms 유닉스 밀리초 시계. 외부에 보내는 시각에만 쓴다.
    # @param sleep 비동기 대기 함수(초). 테스트에서 가짜 시계로 바꾼다.
    # @param rng 난수 생성기.
    def __init__(
        self,
        *,
        dev_mode,
        save_wins,
        record_game=game_recorder.record_game,
        find_game=game_recorder.find_game,
        set_game_winner=game_recorder.set_game_winner,
        get_season=game_recorder.get_current_season,
        clock=time.monotonic,
        wall_ms=None,
        sleep=asyncio.sleep,
        rng=random,
    ):
        self.dev_mode = dev_mode
        self.save_wins = save_wins
        self.record_game = record_game
        self.find_game = find_game
        self.set_game_winner = set_game_winner
        self.get_season = get_season
        self.clock = clock
        self.wall_ms = wall_ms or (lambda: int(time.time() * 1000))
        self.sleep = sleep
        self.rng = rng

        self.config = {}  # 설정 (pick_timeout, champion_count, channels, pick_mode ...)
        self.champion_list = []  # [{"id": 영문 ID, "name": 한국어 이름, "image": URL}, ...]
        self.ddragon_version = None  # 챔피언 데이터를 받은 Data Dragon 버전
        self.excluded = set()  # 세션 안에서 이미 나온 챔피언 이름
        self.selected_users = {}  # user_id: champ_name
        self.auto_assigned_users = set()  # 이번 게임에서 시간 초과로 자동 배정된 user_id
        self.round_counter = 1
        self.current_teams = {}  # {'team1': [member1, ...], 'team2': [member4, ...]} 승리 기록 뒤 비운다
        self.overall_results = {}  # user_id: {'mention': str, 'results': ["O", "X"]}
        # 이 세션에서 끝난 라운드 번호(순서대로). overall_results의 results 인덱스와 짝 - /번복용
        self.session_rounds = []
        self.wins_data = {}  # user_id: {'name': str, 'wins': int}
        self.pick_order = []  # 픽 순서 (member 객체 리스트)
        self.current_pick_index = 0  # 현재 픽 순서
        self.current_game_champions = []  # 현재 게임에서 제시된 챔피언 리스트
        self.game_started = False  # 챔피언 선택이 시작되었는지 여부 (자동 시작 카운트다운이 끝났는지)
        self.victory_processed = False  # 승리 처리 완료 여부 (중복 방지)
        self.current_game_id = 0  # 게임 세대 번호(판마다 +1) - 이전 게임의 버튼·타이머 무효화용
        self.lock = asyncio.Lock()  # 게임 상태 변경 직렬화 (디스코드 명령·버튼·타이머·액티비티 요청 공통)

        # 판 단위 정보 (액티비티 state용). 승리 기록 뒤에도 다음 판까지 남는다
        self.mode = None  # 이 판의 픽 방식 "embed" | "activity". 판이 없으면 None
        self.game_uid = None  # 재시작해도 다시 쓰지 않는 판 ID ("g-<유닉스 밀리초>")
        self.teams = {}  # 판을 시작할 때 나뉜 팀. current_teams와 달리 승리 기록 뒤에도 남는다
        self.game_round = None  # 이 판이 기록될 라운드
        self.game_season = None  # 이 판이 기록될 시즌
        self.result = None  # {"winner", "recorded_ms", "corrected", "history_recorded"}
        self.start_at = None  # activity 모드 자동 시작 시각(단조 시계)
        self.deadline = None  # activity 모드 현재 차례 마감(단조 시계)
        self._last_uid_ms = 0
        self._listeners = []

    # === 설정 ===

    ##
    # @brief 이번 프로세스의 픽 방식. DEV_MODE면 dev_pick_mode를 읽는다.
    # @return "embed" 또는 "activity".
    def pick_mode(self):
        key = "dev_pick_mode" if self.dev_mode else "pick_mode"
        return self.config.get(key, "embed")

    # === 변경 알림 ===

    ##
    # @brief 상태가 바뀔 때마다 부를 함수를 등록한다. 락 안에서 동기적으로 불린다.
    # @param listener 인자 없는 함수.
    def add_listener(self, listener):
        self._listeners.append(listener)

    ##
    # @brief 등록된 함수에 상태 변경을 알린다. 한 함수의 실패가 게임 처리를 막지 않는다.
    def _emit(self):
        for listener in list(self._listeners):
            try:
                listener()
            except Exception:
                log.exception("[GAME] 상태 변경 알림 실패")

    # === 조회 ===

    ##
    # @brief 멤버가 어느 팀 소속인지 확인한다.
    # @param member 확인할 멤버 객체.
    # @return "team1" 또는 "team2", 없으면 None.
    def member_team(self, member):
        if not self.current_teams:
            return None
        if member in self.current_teams.get("team1", []):
            return "team1"
        elif member in self.current_teams.get("team2", []):
            return "team2"
        return None

    ##
    # @brief 멤버의 이번 시즌 누적 승수.
    # @param member_id 멤버 ID.
    # @return 승수(없으면 0).
    def wins_of(self, member_id):
        user_data = self.wins_data.get(str(member_id))
        return user_data.get("wins", 0) if isinstance(user_data, dict) else 0

    # === 판 만들기 ===

    ##
    # @brief 승리 수 기준으로 픽 순서를 계산한다.
    # @details 승수 낮은 순으로 정렬하며(승수가 낮을수록 먼저 픽), 동률이면 랜덤하게 섞는다.
    # @param members 픽 순서를 정할 멤버 리스트.
    # @return 픽 순서대로 정렬된 멤버 리스트.
    def calculate_pick_order(self, members):
        wins_groups = defaultdict(list)
        for member in members:
            wins_groups[self.wins_of(member.id)].append(member)

        # 각 그룹 내에서 랜덤 섞기
        for wins_count in wins_groups:
            self.rng.shuffle(wins_groups[wins_count])

        # 승수 낮은 순으로 정렬하여 최종 순서 생성
        final_order = []
        for wins_count in sorted(wins_groups.keys()):
            final_order.extend(wins_groups[wins_count])
        return final_order

    ##
    # @brief 새 판을 만든다(/게임시작과 액티비티 start 공통). 락 안에서 부른다.
    # @details 세대를 올려 이전 판의 버튼·드롭다운·타이머를 무효화하고, 6명을 뽑아 픽 순서와 팀을 정하고,
    #          후보 챔피언을 뽑는다. 풀이 소진되면 제외 목록을 한 번 비우고 다시 뽑는다. 디스코드 메시지와
    #          embed 모드 카운트다운은 호출부가 맡는다.
    # @param members 후보 멤버 리스트(MAX_PLAYERS명 이상). DEV_MODE면 앞의 6명을 쓴다.
    # @param mode 이 판의 픽 방식 "embed" | "activity".
    # @return NewGame.
    def new_game(self, members, mode):
        self.current_game_id += 1
        self._cancel_timer()
        self.selected_users.clear()
        self.auto_assigned_users.clear()
        self.game_started = False
        self.victory_processed = False
        self.current_pick_index = 0
        self.mode = None
        self.game_uid = None
        self.result = None
        self.start_at = None
        self.deadline = None

        half = MAX_PLAYERS // 2
        if self.dev_mode:
            selected = members[:MAX_PLAYERS]  # 테스트 모드: wins 파일의 6명 사용
        else:
            selected = self.rng.sample(members, MAX_PLAYERS)

        self.pick_order = self.calculate_pick_order(selected)  # 픽 순서 (승수 기반)

        shuffled_for_teams = selected.copy()  # 팀 구성 (랜덤 분할)
        self.rng.shuffle(shuffled_for_teams)
        self.current_teams = {
            "team1": shuffled_for_teams[:half],
            "team2": shuffled_for_teams[half:],
        }
        self.teams = {key: list(team) for key, team in self.current_teams.items()}

        champ_count = self.config.get("champion_count", 8)
        picked = pick_random_champions(self.champion_list, self.excluded, champ_count, self.rng)
        pool_reset = False
        if not picked:
            # excluded는 세션 내 챔피언 중복을 막으려고 계속 쌓이기만 해서, 판을 거듭하면
            # 남은 챔피언이 champion_count보다 적어진다. 이때 한 번 비우고 재시도한다.
            self.excluded.clear()
            picked = pick_random_champions(self.champion_list, self.excluded, champ_count, self.rng)
            pool_reset = bool(picked)
        if not picked:
            # 챔피언 목록 자체가 부족(Data Dragon 로드 실패 등) - 버튼 0개로 진행하지 않는다
            self._emit()
            return NewGame(ok=False, pool_reset=False, champ_count=champ_count)

        self.current_game_champions = picked
        self.mode = mode
        self.game_uid = self._new_uid()
        self.game_round = self.round_counter
        try:
            self.game_season = self.get_season(self.dev_mode)
        except Exception as e:
            log.warning("[GAME] 시즌 조회 실패: %s", e)
            self.game_season = None
        self._on_new_game()
        self._emit()
        return NewGame(ok=True, pool_reset=pool_reset, champ_count=champ_count)

    ##
    # @brief 판 ID를 만든다. 같은 밀리초에 두 판이 생겨도 겹치지 않게 1씩 올린다.
    # @return "g-<유닉스 밀리초>".
    def _new_uid(self):
        ms = max(self.wall_ms(), self._last_uid_ms + 1)
        self._last_uid_ms = ms
        return f"g-{ms}"

    ##
    # @brief new_game()이 판을 만든 직후 부르는 자리. activity 모드의 자동 시작은 여기서 건다.
    def _on_new_game(self):
        pass

    ##
    # @brief 판 타이머를 멈춘다. activity 모드 타이머가 없으면 아무것도 하지 않는다.
    def _cancel_timer(self):
        pass

    # === 픽 ===

    ##
    # @brief 지금 차례가 비어 있으면 남은 후보에서 무작위로 배정하고 다음 차례로 넘긴다. 락 안에서 부른다.
    # @details embed 모드 타이머와 activity 모드 타이머가 같이 쓴다. 배정한 사람은 선택 현황에
    #          "자동 배정"으로 남도록 auto_assigned_users에 넣는다.
    # @param picker_index 배정할 차례의 인덱스(현재 차례여야 한다).
    # @return 배정한 챔피언 이름. 이미 골랐거나 남은 후보가 없으면 None.
    def auto_assign(self, picker_index):
        current_picker = self.pick_order[picker_index]
        if current_picker.id in self.selected_users:
            return None
        # 현재 게임의 챔피언 중 남은 챔피언에서 랜덤 선택
        available_champs = [
            champ
            for champ in self.current_game_champions
            if champ["name"] not in self.excluded
        ]
        if not available_champs:
            return None
        champ_name = self.rng.choice(available_champs)["name"]
        self.selected_users[current_picker.id] = champ_name
        self.excluded.add(champ_name)
        self.auto_assigned_users.add(current_picker.id)
        self.current_pick_index += 1
        return champ_name

    # === 승리 기록 ===

    ##
    # @brief 승리 팀을 기록한다(/승리 드롭다운과 액티비티 result 공통). 락 안에서 부른다.
    # @details 검증을 모두 통과한 뒤 승수를 사본에 반영해 저장하고, 저장이 성공해야 메모리와 세션 전적,
    #          라운드, 판 기록을 갱신한다. 저장이 실패하면 아무 상태도 바꾸지 않아 다시 기록할 수 있다.
    #          판 기록 실패(시즌 불일치 등)는 승리 처리에 영향을 주지 않는다.
    # @param team_key 승리 팀 "team1" 또는 "team2".
    # @return RecordOutcome.
    def record_result_locked(self, team_key):
        if self.victory_processed:
            return RecordOutcome("already_recorded", "⚠️ 이미 승리 처리가 완료되었습니다!")
        if not self.current_teams:
            return RecordOutcome("no_game", "⚠️ 먼저 `/게임시작`으로 팀을 구성해주세요!")
        # 전원이 챔피언을 골랐는지 확인한다
        problem = next(
            (
                f"❌ {member.mention} 님이 챔피언을 선택하지 않았습니다!"
                for key in self.current_teams
                for member in self.current_teams[key]
                if member.id not in self.selected_users
            ),
            None,
        )
        if problem is not None:
            return RecordOutcome("not_picked", problem)

        # 누적 전적(영구)은 사본에 갱신한 뒤 저장에 성공해야 반영한다.
        # 저장이 실패했는데 메모리만 올라가면 다음 판부터 승수가 어긋난다.
        new_wins = copy.deepcopy(self.wins_data)
        for member in self.current_teams[team_key]:
            uid_str = str(member.id)
            if uid_str in new_wins:
                new_wins[uid_str]["wins"] += 1
            else:
                # 새 유저 추가
                new_wins[uid_str] = {"name": member.display_name, "wins": 1}
        new_wins["total_rounds"] = new_wins.get("total_rounds", 0) + 1

        try:
            self.save_wins(new_wins)
        except Exception as e:
            print(f"[ERROR] 전적 저장 실패: {e}")
            return RecordOutcome(
                "record_failed", f"❌ 전적 저장에 실패했습니다. 다시 선택해주세요: {e}"
            )

        self.victory_processed = True
        self.wins_data = new_wins

        # 저장 성공 후에 세션 전적(오늘의 결과)을 반영한다
        for key in self.current_teams:
            for member in self.current_teams[key]:
                uid = member.id
                if uid not in self.overall_results:
                    self.overall_results[uid] = {"mention": member.mention, "results": []}
                self.overall_results[uid]["results"].append("O" if key == team_key else "X")

        # 라운드 번호 확정. total_rounds와 사이에 await를 두지 않아 두 카운터가 어긋나지 않는다.
        finished_round = self.round_counter
        self.round_counter += 1
        # 위 results append와 같은 순서 - /번복이 인덱스로 찾는다
        self.session_rounds.append(finished_round)

        # history_data에 판 기록 (대시보드용) - 실패해도 승리 처리에는 영향 없음
        season_warning = None
        history_recorded = False
        try:
            season = self.record_game(
                finished_round,
                {
                    tk: [
                        {
                            "id": str(m.id),
                            "name": m.display_name,
                            "champ": str(self.selected_users.get(m.id, "")),
                        }
                        for m in self.current_teams[tk]
                    ]
                    for tk in TEAM_KEYS
                },
                team_key,
                self.dev_mode,
            )
            history_recorded = True
            print(f"[RECORD] history_data: 시즌{season} R{finished_round} 기록 완료")
            # record_game 내부에서 업로드까지 처리 (백그라운드, 실패해도 무영향)
        except SeasonMismatchError as e:
            # 라운드가 회귀했는데 시즌이 그대로 = wins가 리셋됐는데 /시즌시작을 안 한 상황.
            # 잘못된 시즌으로 기록하느니 멈추고 알린다 (승수 저장은 이미 끝났다).
            print(f"[WARN] history_data 기록 중단: {e}")
            season_warning = f"⚠️ 판 기록이 중단되었습니다.\n{e}"
        except Exception as e:
            print(f"[WARN] history_data 기록 실패: {e}")

        outcome = RecordOutcome(
            "ok",
            f"✅ **{team_key.upper()}** 승리 기록 완료!",
            round=finished_round,
            team_key=team_key,
            teams={key: list(team) for key, team in self.current_teams.items()},
            selections=dict(self.selected_users),
            season_warning=season_warning,
        )
        self.result = {
            "winner": team_key,
            "recorded_ms": self.wall_ms(),
            "corrected": None,
            "history_recorded": history_recorded,
        }
        self.current_teams.clear()
        self._emit()
        return outcome

    # === 번복 ===

    ##
    # @brief 판 기록의 승자를 뒤집는다(/번복 확인 버튼과 액티비티 reverse 공통). 락 안에서 부른다.
    # @details 판 기록 → 승수 순서로 바꾸고, 승수 저장이 실패하면 판 기록을 원복한 뒤 예외를 다시 던진다.
    #          세션 "오늘의 결과" O/X도 뒤집는다. 뒤집은 판이 화면에 떠 있는 판이면 result도 고친다.
    # @param game 번복할 판 기록 스냅샷(find_game 결과). winner는 스냅샷 시점의 승자다.
    # @return (라운드, 이전 승자, 새 승자).
    # @throws RuntimeError 스냅샷 뒤에 판 기록이 바뀌었을 때. 저장 실패 예외도 그대로 던진다.
    def reverse_locked(self, game):
        round_num = game["round"]
        old_winner = game["winner"]
        new_winner = "team2" if old_winner == "team1" else "team1"

        # 미리보기 뒤에 다른 /번복이 먼저 뒤집었을 수 있다 - 스냅샷과 대조한다
        current = self.find_game(round_num, self.dev_mode)
        if current is None or current["winner"] != old_winner:
            raise RuntimeError(
                f"R{round_num} 기록이 미리보기와 달라져 중단했습니다. 다시 실행해주세요."
            )

        # 1) 판 기록 (대시보드 업로드 포함)
        self.set_game_winner(round_num, new_winner, self.dev_mode)

        # 2) 승수: 옛 승자 -1, 새 승자 +1. total_rounds는 그대로
        new_wins = copy.deepcopy(self.wins_data)
        for p in game[old_winner]:
            entry = new_wins.get(p["id"])
            if isinstance(entry, dict):
                entry["wins"] = max(0, entry["wins"] - 1)
        for p in game[new_winner]:
            entry = new_wins.setdefault(p["id"], {"name": p["id"], "wins": 0})
            entry["wins"] += 1
        try:
            self.save_wins(new_wins)
        except Exception:
            self.set_game_winner(round_num, old_winner, self.dev_mode)  # 판 기록 원복
            raise
        self.wins_data = new_wins

        # 3) 세션 "오늘의 결과" O/X (이 세션에 친 판일 때만 표시가 있다)
        if round_num in self.session_rounds:
            idx = self.session_rounds.index(round_num)
            for record in self.overall_results.values():
                if idx < len(record["results"]):
                    record["results"][idx] = "X" if record["results"][idx] == "O" else "O"

        # 4) 화면에 떠 있는 판을 뒤집었으면 결과 표시도 고친다
        if (
            self.result is not None
            and self.result["history_recorded"]
            and self.game_round == round_num
            and self.game_season == current.get("season")
        ):
            self.result = {
                **self.result,
                "winner": new_winner,
                "corrected": {"from": old_winner, "at_ms": self.wall_ms()},
            }
        self._emit()
        return round_num, old_winner, new_winner
