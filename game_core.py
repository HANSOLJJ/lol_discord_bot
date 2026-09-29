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
from pick_logic import process_pick

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
# activity 모드에서 참가자 전원이 입장하거나 "지금 시작"을 누른 뒤 픽이 시작되기까지의 시간.
DEFAULT_READY_COUNTDOWN_SECONDS = 5  # config.json에 ready_countdown_seconds가 없을 때 쓰는 폴백(초)
TEAM_KEYS = ("team1", "team2")
START_PHASES = ("none", "awaiting_result", "completed")  # 액티비티 start를 받는 phase


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
# @brief 5·6위 어드밴티지(규격 14-1절)의 이점 팀과 종류를 구한다.
# @details 순위는 픽 순서 그대로다(인덱스 0이 6위, 마지막이 1위). 6위와 5위가 같은 팀이면 그 팀이 이점 팀이고,
#          나머지 한 명이 1·2위면 밴, 3·4위면 강제픽이다.
# @param pick_order 픽 순서대로 정렬된 멤버 리스트.
# @param teams {"team1": [member...], "team2": [...]}.
# @return {"kind": "ban"|"force", "team": 팀 키}. 이점이 없으면 None.
def advantage_of(pick_order, teams):
    team_of = {m.id: key for key in TEAM_KEYS for m in teams.get(key, [])}
    team = team_of.get(pick_order[0].id)
    if team is None or team_of.get(pick_order[1].id) != team:
        return None
    third = next(i for i in range(2, len(pick_order)) if team_of.get(pick_order[i].id) == team)
    return {"kind": "ban" if third >= len(pick_order) - 2 else "force", "team": team}


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
    # @param record_game 판 기록 함수(round, teams, winner, dev_mode, advantage=) → 시즌.
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
        self.start_at = None  # activity 모드 자동 시작 시각(단조 시계). 입장 대기 중이면 None
        self.start_forced = False  # 이번 카운트다운이 "지금 시작"으로 잡혔는가(누가 나가도 취소하지 않는다)
        self.deadline = None  # activity 모드 현재 차례(또는 어드밴티지 선택) 마감(단조 시계)
        # activity 모드 5·6위 어드밴티지 {"kind", "team", "status", "champion"(한국어 이름)}. 없으면 None
        self.advantage = None
        # 액티비티에 입장한(ready를 보낸) 사용자 ID 문자열. 판과 무관하게 연결 기준으로 유지한다
        self.present = set()
        self._last_uid_ms = 0
        self._listeners = []
        self._timer = None  # activity 모드 자동 시작·차례 마감 타이머
        self._effect_tasks = set()  # 실행 중인 디스코드 후속 작업
        # 액티비티에서 온 요청 뒤의 디스코드 작업(현황판·공지)과 길드 멤버 조회를 맡는 객체.
        # got_champe가 넣고, 테스트는 가짜를 넣거나 비워 둔다
        self.effects = None

    # === 설정 ===

    ##
    # @brief 이번 프로세스의 픽 방식. DEV_MODE면 dev_pick_mode를 읽는다.
    # @return "embed" 또는 "activity".
    def pick_mode(self):
        key = "dev_pick_mode" if self.dev_mode else "pick_mode"
        return self.config.get(key, "embed")

    ##
    # @brief 게임 시작 뒤 픽이 자동으로 시작되기까지의 시간(초). DEV_MODE면 dev_auto_start_seconds가 있을 때 그것을 쓴다.
    # @return 초(0 이상).
    def auto_start_seconds(self):
        if self.dev_mode and "dev_auto_start_seconds" in self.config:
            return self.config["dev_auto_start_seconds"]
        return self.config.get("auto_start_seconds", DEFAULT_AUTO_START_SECONDS)

    ##
    # @brief activity 모드에서 전원 입장(또는 지금 시작) 뒤 픽이 시작되기까지의 시간(초).
    # @return 초(0 이상).
    def ready_countdown_seconds(self):
        return self.config.get("ready_countdown_seconds", DEFAULT_READY_COUNTDOWN_SECONDS)

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
        self.start_forced = False
        self.deadline = None
        self.advantage = None

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
    # @brief new_game()이 판을 만든 직후 부른다. activity 모드면 어드밴티지를 정하고 입장 대기를 시작한다.
    # @details 참가자 전원이 이미 입장해 있으면 바로 카운트다운을 건다. DEV_MODE는 참가자가 가상 유저라 입장이
    #          성립하지 않으므로 예전처럼 auto_start_seconds 뒤 고정 자동 시작한다. embed 모드의 자동 시작
    #          카운트다운은 got_champe가 채널 메시지로 센다. embed 모드에는 어드밴티지가 없다.
    def _on_new_game(self):
        if self.mode != "activity":
            return
        advantage = advantage_of(self.pick_order, self.teams)
        if advantage is not None:
            self.advantage = {**advantage, "status": "pending", "champion": None}
        if self.dev_mode:
            self.start_at = self.clock() + self.auto_start_seconds()
            self._set_timer(self._auto_start(self.current_game_id, self.start_at))
        else:
            self._sync_countdown()

    ##
    # @brief 참가자 전원(이번 판 pick_order 전체)이 입장해 있는가.
    def _all_present(self):
        return all(str(m.id) in self.present for m in self.pick_order)

    ##
    # @brief 입장 대기 카운트다운을 건다. 락 안에서 부른다.
    # @param forced "지금 시작"으로 잡은 카운트다운이면 True(누가 나가도 취소하지 않는다).
    def _start_countdown(self, forced):
        self.start_at = self.clock() + self.ready_countdown_seconds()
        self.start_forced = forced
        self._set_timer(self._auto_start(self.current_game_id, self.start_at))

    ##
    # @brief 입장 현황에 맞춰 starting 카운트다운을 걸거나 취소한다. 락 안에서 부른다.
    # @details 운영(DEV 아님) activity 판의 starting에서, "지금 시작"이 아닐 때만 움직인다.
    #          전원 입장이면 카운트다운을 걸고, 카운트다운 중 누가 나가면 취소하고 입장 대기로 돌아간다.
    def _sync_countdown(self):
        if self.dev_mode or self.visible_phase() != "starting" or self.start_forced:
            return
        ready = self._all_present()
        if ready and self.start_at is None:
            self._start_countdown(forced=False)
        elif not ready and self.start_at is not None:
            self.start_at = None
            self._cancel_timer()

    ##
    # @brief 액티비티 입장 집합을 바꾼다. 액티비티 서버가 입장 사용자가 바뀔 때마다 부른다.
    # @details 바뀌었으면 starting 카운트다운을 맞추고 state를 알린다.
    # @param user_ids 지금 입장한 사용자 ID 문자열들(관전자 포함, snapshot이 참가자만 거른다).
    async def set_present(self, user_ids):
        async with self.lock:
            present = set(user_ids)
            if present == self.present:
                return
            self.present = present
            self._sync_countdown()
            self._emit()

    ##
    # @brief activity 모드 판 타이머(자동 시작 또는 현재 차례 마감)를 새로 건다. 이전 타이머는 멈춘다.
    # @param coro 타이머 코루틴.
    def _set_timer(self, coro):
        self._cancel_timer()
        self._timer = asyncio.create_task(coro)

    ##
    # @brief activity 모드 판 타이머를 멈춘다. 타이머 자신이 부른 경우(자동 배정 뒤 다음 차례)는 멈추지 않는다.
    def _cancel_timer(self):
        timer, self._timer = self._timer, None
        if timer is not None and not timer.done() and timer is not asyncio.current_task():
            timer.cancel()

    # === 픽 ===

    ##
    # @brief 지금 차례가 비어 있으면 남은 후보에서 무작위로 배정하고 다음 차례로 넘긴다. 락 안에서 부른다.
    # @details embed 모드 타이머와 activity 모드 타이머가 같이 쓴다. 배정한 사람은 선택 현황에
    #          "자동 배정"으로 남도록 auto_assigned_users에 넣는다. 어드밴티지가 있으면 픽과 같은 규칙
    #          (_advantage_violation)으로 후보를 거른다.
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
            and self._advantage_violation(current_picker, champ["name"]) is None
        ]
        if not available_champs:
            return None
        champ_name = self.rng.choice(available_champs)["name"]
        self.selected_users[current_picker.id] = champ_name
        self.excluded.add(champ_name)
        self.auto_assigned_users.add(current_picker.id)
        self.current_pick_index += 1
        return champ_name

    ##
    # @brief 멤버가 판을 시작할 때 나뉜 팀 가운데 어디 소속인지 확인한다(승리 기록 뒤에도 남는 teams 기준).
    # @param member 확인할 멤버 객체.
    # @return "team1" 또는 "team2", 없으면 None.
    def _team_key(self, member):
        return next((key for key in TEAM_KEYS if member in self.teams.get(key, [])), None)

    ##
    # @brief 이 사람이 이 챔피언을 고르면 어드밴티지 규칙(규격 14-5절)에 걸리는지 판정한다.
    # @details 확정된 어드밴티지가 있을 때만 적용한다. 밴 챔피언은 아무도 못 고르고, 강제픽 챔피언은 상대 팀만
    #          고를 수 있으며, 상대 팀의 마지막 차례에 강제픽이 남아 있으면 그 챔피언만 고를 수 있다.
    # @param picker 고르는 차례의 멤버.
    # @param champ_name 고르려는 챔피언 이름.
    # @return (code, message). 걸리지 않으면 None.
    def _advantage_violation(self, picker, champ_name):
        adv = self.advantage
        if adv is None or adv["status"] != "chosen":
            return None
        chosen = adv["champion"]
        if adv["kind"] == "ban":
            if champ_name == chosen:
                return "champion_banned", "이번 판에서 밴된 챔피언입니다."
            return None
        if champ_name == chosen:
            if self._team_key(picker) == adv["team"]:
                return "champion_reserved", "상대 팀만 고를 수 있는 강제픽 챔피언입니다."
            return None
        opponents = [m for m in self.pick_order if self._team_key(m) not in (None, adv["team"])]
        if opponents and opponents[-1] is picker and chosen not in self.selected_users.values():
            return "must_pick_forced", f"강제픽 챔피언({chosen})을 골라야 하는 차례입니다."
        return None

    ##
    # @brief 판 기록(history_data.json)에 남길 어드밴티지. 확정된 판만 남긴다(규격 14-6절).
    # @return {"kind", "team", "champion"(한국어 이름)} 또는 None.
    def _advantage_record(self):
        adv = self.advantage
        if adv is None or adv["status"] != "chosen":
            return None
        return {"kind": adv["kind"], "team": adv["team"], "champion": adv["champion"]}

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
                advantage=self._advantage_record(),
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

    # === activity 모드: 시계와 타이머 ===

    ##
    # @brief 마감 뒤 늦게 도착한 픽을 더 받아 주는 유예(초).
    def _grace(self):
        return self.config.get("pick_grace_seconds", DEFAULT_PICK_GRACE_SECONDS)

    ##
    # @brief 목표 단조 시각까지 기다린다. sleep이 조금 일찍 깨어나도 목표 전이면 다시 기다린다.
    # @param target 목표 단조 시각.
    async def _sleep_until(self, target):
        while (remaining := target - self.clock()) > 0:
            await self.sleep(remaining)

    ##
    # @brief 자동 시작 시각이 되면 어드밴티지 선택(있을 때) 또는 픽을 시작한다. 락 안에서 세대와 시작 여부를
    #        다시 확인한다.
    # @details 그 사이 카운트다운이 취소되거나 다시 잡혔으면(start_at이 달라졌으면) 아무것도 하지 않는다.
    # @param game_id 타이머를 건 판의 세대 번호.
    # @param start_at 자동 시작 단조 시각.
    async def _auto_start(self, game_id, start_at):
        await self._sleep_until(start_at)
        async with self.lock:
            if game_id != self.current_game_id or self.game_started or self.start_at != start_at:
                return
            self.game_started = True
            self.start_at = None
            if self.advantage is not None:
                self._start_advantage()
            else:
                self._start_turn(0)
            self._emit()
        self._run_effect("board_changed")

    ##
    # @brief 어드밴티지 선택을 시작한다. 마감은 픽 차례와 같은 pick_timeout이고, 마감+유예에 건너뛰기 타이머를
    #        건다. 락 안에서 부른다.
    def _start_advantage(self):
        self.deadline = self.clock() + self.config.get("pick_timeout", DEFAULT_PICK_TIMEOUT)
        self._set_timer(self._expire_advantage(self.current_game_id, self.deadline))

    ##
    # @brief 마감+유예가 지나도록 아무도 고르지 않았으면 이번 판을 어드밴티지 없이(skipped) 픽으로 넘긴다.
    # @details 그 사이 확정됐거나 새 판이 시작됐으면 아무것도 하지 않는다.
    # @param game_id 타이머를 건 판의 세대 번호.
    # @param deadline 어드밴티지 선택 마감(단조 시각).
    async def _expire_advantage(self, game_id, deadline):
        await self._sleep_until(deadline + self._grace())
        async with self.lock:
            if (
                game_id != self.current_game_id
                or self.visible_phase() != "advantage"
                or self.deadline != deadline
            ):
                return
            self.advantage["status"] = "skipped"
            log.info("[GAME] 어드밴티지 시간 초과 (game=%s)", self.game_uid)
            self._start_turn(0)
            self._emit()
        self._run_effect("board_changed")

    ##
    # @brief 차례를 시작한다. 마감을 지금 pick_timeout으로 정하고, 마감+유예에 자동 배정 타이머를 건다.
    #        락 안에서 부른다.
    # @param index 시작할 차례(pick_order 인덱스).
    def _start_turn(self, index):
        self.deadline = self.clock() + self.config.get("pick_timeout", DEFAULT_PICK_TIMEOUT)
        self._set_timer(self._expire_turn(self.current_game_id, index, self.deadline))

    ##
    # @brief 마감+유예가 지나면 락 안에서 같은 차례가 아직 비어 있는지 다시 확인하고 자동 배정한다.
    # @details 그 사이 픽이 확정됐거나 새 판이 시작됐으면 아무것도 하지 않는다. 이미 자동 배정으로 끝난
    #          차례는 늦게 온 픽이 stale_turn으로 거절되므로 한 차례는 한 번만 확정된다.
    # @param game_id 타이머를 건 판의 세대 번호.
    # @param index 타이머를 건 차례.
    # @param deadline 그 차례의 마감(단조 시각).
    async def _expire_turn(self, game_id, index, deadline):
        await self._sleep_until(deadline + self._grace())
        async with self.lock:
            if (
                game_id != self.current_game_id
                or index != self.current_pick_index
                or self.deadline != deadline
            ):
                return
            champ_name = self.auto_assign(index)
            if champ_name is None:
                return
            log.info("[GAME] 자동 배정 (game=%s, turn=%d, champ=%s)", self.game_uid, index, champ_name)
            self._after_turn()
            self._emit()
        self._run_effect("board_changed")

    ##
    # @brief 차례가 끝난 뒤(픽 확정·자동 배정) 다음 차례를 시작하거나, 6명이 다 골랐으면 타이머를 멈춘다.
    #        락 안에서 부른다.
    def _after_turn(self):
        if self.current_pick_index < len(self.pick_order):
            self._start_turn(self.current_pick_index)
        else:
            self.deadline = None
            self._cancel_timer()

    ##
    # @brief effects의 후속 작업을 백그라운드로 실행한다. 락 밖에서 부른다.
    # @param name effects 메서드 이름.
    # @param args 인자.
    def _run_effect(self, name, *args):
        method = getattr(self.effects, name, None)
        if method is None:
            return

        async def run():
            try:
                await method(*args)
            except Exception:
                log.exception("[GAME] 디스코드 후속 작업 실패 (%s)", name)

        task = asyncio.create_task(run())
        self._effect_tasks.add(task)
        task.add_done_callback(self._effect_tasks.discard)

    ##
    # @brief 타이머와 후속 작업을 멈춘다(봇 종료 때).
    async def close(self):
        self._cancel_timer()
        tasks = list(self._effect_tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    # === activity 모드: 화면에 보이는 상태 ===

    ##
    # @brief 액티비티가 볼 수 있는 판인가. embed 모드 판은 액티비티에 보이지 않는다(phase none).
    def _visible(self):
        return self.game_uid is not None and self.mode == "activity"

    ##
    # @brief 액티비티에 보이는 판 ID. 보이는 판이 없으면 None.
    def visible_game_id(self):
        return self.game_uid if self._visible() else None

    ##
    # @brief 액티비티에 보이는 phase.
    # @return "none" | "starting" | "advantage" | "picking" | "awaiting_result" | "completed".
    def visible_phase(self):
        if not self._visible():
            return "none"
        if self.victory_processed:
            return "completed"
        if not self.game_started:
            return "starting"
        if self.advantage is not None and self.advantage["status"] == "pending":
            return "advantage"
        if self.current_pick_index < len(self.pick_order):
            return "picking"
        return "awaiting_result"

    ##
    # @brief 현재 차례 ID. 차례마다 새로 만든다.
    def turn_id(self):
        return f"{self.game_uid}:{self.current_pick_index}"

    ##
    # @brief 연결과 무관한 state 본문을 만든다(규격 8절, `me` 제외). await가 없어 한 순간의 상태다.
    # @details server_ms와 start_at_ms·deadline_ms는 같은 순간에 잡은 단조 시각과 유닉스 밀리초로 계산한다.
    # @param now_mono 기준 단조 시각(생략하면 지금).
    # @param now_ms now_mono와 같은 순간의 유닉스 밀리초.
    # @return state dict에서 t·protocol_version·server_epoch·state_version·me를 뺀 부분.
    def snapshot(self, now_mono=None, now_ms=None):
        if now_mono is None:
            now_mono, now_ms = self.clock(), self.wall_ms()
        phase = self.visible_phase()
        state = {
            "game_id": None,
            "phase": phase,
            "round": None,
            "season": None,
            "server_ms": now_ms,
            "start_at_ms": None,
            "deadline_ms": None,
            "grace_ms": None,
            "turn_id": None,
            "current_index": None,
            "ddragon_version": None,
            "players": [],
            "pick_order": [],
            "champions": [],
            "selections": {},
            "auto_assigned": [],
            "result": None,
            "advantage": None,
            "present": [],
        }
        if phase == "none":
            return state

        def at_ms(mono):
            return now_ms + round((mono - now_mono) * 1000)

        champ_ids = {c["name"]: c["id"] for c in self.current_game_champions}
        state.update(
            game_id=self.game_uid,
            round=self.game_round,
            season=self.game_season,
            ddragon_version=self.ddragon_version,
            players=[
                {
                    "id": str(m.id),
                    "name": m.display_name,
                    "team": key,
                    "wins": self.wins_of(m.id),
                }
                for key in TEAM_KEYS
                for m in self.teams.get(key, [])
            ],
            pick_order=[str(m.id) for m in self.pick_order],
            champions=[{"id": c["id"], "name": c["name"]} for c in self.current_game_champions],
            selections={
                str(uid): champ_ids.get(name, name) for uid, name in self.selected_users.items()
            },
            auto_assigned=[
                str(m.id) for m in self.pick_order if m.id in self.auto_assigned_users
            ],
        )
        state["present"] = [p["id"] for p in state["players"] if p["id"] in self.present]
        adv = self.advantage
        if adv is not None:
            state["advantage"] = {
                "kind": adv["kind"],
                "team": adv["team"],
                "status": adv["status"],
                "champion_id": champ_ids.get(adv["champion"]) if adv["status"] == "chosen" else None,
            }
        if phase == "starting":
            # 입장 대기 중에는 카운트다운이 없다
            state["start_at_ms"] = at_ms(self.start_at) if self.start_at is not None else None
        elif phase == "advantage":
            state.update(deadline_ms=at_ms(self.deadline), grace_ms=round(self._grace() * 1000))
        elif phase == "picking":
            state.update(
                deadline_ms=at_ms(self.deadline),
                grace_ms=round(self._grace() * 1000),
                turn_id=self.turn_id(),
                current_index=self.current_pick_index,
            )
        elif phase == "completed":
            state["result"] = {
                "winner": self.result["winner"],
                "recorded_ms": self.result["recorded_ms"],
                "corrected": self.result["corrected"],
            }
        return state

    ##
    # @brief state를 받는 사람의 권한(규격 8절 me)을 만든다. DEV_MODE면 누구나 대신 누를 수 있다(11절).
    # @param snapshot snapshot()의 결과.
    # @param user_id 받는 사람의 Discord ID(문자열).
    # @return me dict.
    def me(self, snapshot, user_id):
        phase = snapshot["phase"]
        player = next((p for p in snapshot["players"] if p["id"] == user_id), None)
        can_act = player is not None or self.dev_mode
        current = (
            snapshot["pick_order"][snapshot["current_index"]] if phase == "picking" else None
        )
        adv_team = snapshot["advantage"]["team"] if snapshot["advantage"] is not None else None
        return {
            "id": user_id,
            "role": "player" if player is not None else "spectator",
            "team": player["team"] if player is not None else None,
            "can_start": self.pick_mode() == "activity" and phase in START_PHASES,
            "can_start_now": phase == "starting" and snapshot["start_at_ms"] is None and can_act,
            "can_pick": phase == "picking" and (self.dev_mode or current == user_id),
            "can_advantage": phase == "advantage"
            and (self.dev_mode or (player is not None and player["team"] == adv_team)),
            "can_report": phase == "awaiting_result" and can_act,
            "can_reverse": phase == "completed" and can_act,
        }

    ##
    # @brief 보낸 사람이 이 판의 6명인가.
    # @param user_id Discord ID(문자열).
    def _is_player(self, user_id):
        return any(str(m.id) == user_id for m in self.pick_order)

    # === activity 모드: 요청 처리 (규격 9절) ===

    ##
    # @brief start 요청. 규격 9절 판정 순서대로 확인하고 /게임시작과 같은 new_game()으로 판을 만든다.
    # @param user_id 보낸 사람 Discord ID(문자열).
    # @param game_id 화면에 떠 있던 판 ID(없으면 None).
    # @param guild_id SDK의 guildId(없으면 None).
    # @return (code, message).
    async def activity_start(self, user_id, game_id, guild_id):
        if self.pick_mode() != "activity":
            return "not_allowed", "지금은 채널 버튼 방식이라 액티비티에서 시작할 수 없습니다."
        async with self.lock:
            if game_id != self.visible_game_id():
                return "stale_game", "다른 사람이 먼저 새 판을 시작했습니다."
            if self.visible_phase() not in START_PHASES:
                return "wrong_phase", "챔피언 선택 중에는 새 판을 시작할 수 없습니다."
            resolve = getattr(self.effects, "resolve_members", None)
            members = resolve(guild_id) if guild_id is not None and resolve else None
            if members is None:
                return "not_allowed", "봇이 들어가 있는 디스코드 서버에서만 시작할 수 있습니다."
            if len(members) < MAX_PLAYERS:
                return (
                    "not_enough_players",
                    f"온라인인 사람이 {MAX_PLAYERS}명 필요합니다. (현재 {len(members)}명)",
                )
            result = self.new_game(members, "activity")
            if not result.ok:
                return "server_error", "챔피언 데이터가 부족해 판을 만들지 못했습니다."
            log.info("[GAME] 액티비티에서 새 판 (game=%s, by=%s)", self.game_uid, user_id)
            message = f"ROUND {self.game_round} 게임을 시작했습니다."
        self._run_effect("game_started", guild_id, result)
        return "ok", message

    ##
    # @brief start_now 요청. 입장 대기 중에 참가자 전원을 기다리지 않고 카운트다운을 강제로 건다.
    # @details 이렇게 잡은 카운트다운은 누가 나가도 취소하지 않는다.
    # @param user_id 보낸 사람 Discord ID(문자열).
    # @param game_id 요청의 판 ID.
    # @return (code, message).
    async def activity_start_now(self, user_id, game_id):
        async with self.lock:
            if game_id != self.visible_game_id():
                return "stale_game", "이미 끝났거나 바뀐 판입니다."
            if self.visible_phase() != "starting":
                return "wrong_phase", "지금은 시작할 수 없습니다."
            if not self.dev_mode and not self._is_player(user_id):
                return "not_allowed", "이 판의 참가자만 시작할 수 있습니다."
            if self.start_at is not None:
                return "wrong_phase", "이미 시작 카운트다운 중입니다."
            self._start_countdown(forced=True)
            log.info("[GAME] 지금 시작 (game=%s, by=%s)", self.game_uid, user_id)
            self._emit()
        return "ok", f"{self.ready_countdown_seconds()}초 뒤 시작합니다."

    ##
    # @brief pick 요청. 규격 9절 판정 순서대로 확인하고 확정하면 바로 다음 차례로 넘긴다.
    # @param user_id 보낸 사람 Discord ID(문자열).
    # @param game_id 요청의 판 ID.
    # @param turn_id 요청의 차례 ID.
    # @param champion_id 고른 챔피언의 Data Dragon 영문 ID.
    # @param received_at 서버가 메시지를 받은 단조 시각(락을 기다리기 전에 잡은 값).
    # @return (code, message).
    async def activity_pick(self, user_id, game_id, turn_id, champion_id, received_at):
        async with self.lock:
            if game_id != self.visible_game_id():
                return "stale_game", "이미 끝났거나 바뀐 판입니다."
            if self.visible_phase() != "picking":
                return "wrong_phase", "지금은 챔피언을 고를 수 없습니다."
            if turn_id != self.turn_id():
                return "stale_turn", "이미 지나간 차례입니다."
            picker = self.pick_order[self.current_pick_index]
            if not self.dev_mode and str(picker.id) != user_id:
                return "not_your_turn", f"지금은 {picker.display_name} 님의 차례입니다."
            if received_at > self.deadline + self._grace():
                return "timeout", "선택 시간이 지났습니다."
            champ = next(
                (c for c in self.current_game_champions if c["id"] == champion_id), None
            )
            if champ is None:
                return "not_candidate", "이번 판 후보가 아닌 챔피언입니다."
            violation = self._advantage_violation(picker, champ["name"])
            if violation is not None:
                return violation
            # 중복 확인과 기록은 embed 모드 버튼과 같은 공통 판정(process_pick)을 쓴다
            res = process_pick(
                game_started=self.game_started,
                pick_order=self.pick_order,
                current_pick_index=self.current_pick_index,
                selected_users=self.selected_users,
                excluded=self.excluded,
                auto_assigned_users=self.auto_assigned_users,
                user_id=picker.id,
                champ_name=champ["name"],
                clicked_at=received_at,
                current_pick_deadline=self.deadline,
                pick_grace_seconds=self._grace(),
                dev_mode=self.dev_mode,
                max_players=MAX_PLAYERS,
            )
            if res.kind != "pick":
                if res.reason == "already_picked_champ":
                    return "champion_taken", "이미 선택된 챔피언입니다."
                log.error("[GAME] 예상하지 못한 픽 판정: %s", res.reason)
                return "server_error", "선택을 처리하지 못했습니다."
            self.current_pick_index = res.current_pick_index
            log.info("[GAME] 픽 (game=%s, by=%s, champ=%s)", self.game_uid, user_id, champ["name"])
            self._after_turn()
            self._emit()
        self._run_effect("board_changed")
        return "ok", f"{champ['name']} 선택 완료!"

    ##
    # @brief advantage 요청. 규격 14-4절 판정 순서대로 확인하고, 먼저 온 한 번을 확정한 뒤 바로 픽을 시작한다.
    # @param user_id 보낸 사람 Discord ID(문자열).
    # @param game_id 요청의 판 ID.
    # @param champion_id 밴하거나 강제픽으로 정할 챔피언의 Data Dragon 영문 ID.
    # @param received_at 서버가 메시지를 받은 단조 시각(락을 기다리기 전에 잡은 값).
    # @return (code, message).
    async def activity_advantage(self, user_id, game_id, champion_id, received_at):
        async with self.lock:
            if game_id != self.visible_game_id():
                return "stale_game", "이미 끝났거나 바뀐 판입니다."
            if self.visible_phase() != "advantage":
                return "wrong_phase", "지금은 어드밴티지를 고를 수 없습니다."
            adv = self.advantage
            if not self.dev_mode and not any(
                str(m.id) == user_id for m in self.teams.get(adv["team"], [])
            ):
                return "not_allowed", "어드밴티지 팀만 고를 수 있습니다."
            if received_at > self.deadline + self._grace():
                return "timeout", "선택 시간이 지났습니다."
            champ = next(
                (c for c in self.current_game_champions if c["id"] == champion_id), None
            )
            if champ is None:
                return "not_candidate", "이번 판 후보가 아닌 챔피언입니다."
            adv["status"] = "chosen"
            adv["champion"] = champ["name"]
            log.info(
                "[GAME] 어드밴티지 (game=%s, by=%s, kind=%s, champ=%s)",
                self.game_uid, user_id, adv["kind"], champ["name"],
            )
            self._start_turn(0)
            self._emit()
        self._run_effect("board_changed")
        label = "밴" if adv["kind"] == "ban" else "강제픽"
        return "ok", f"{champ['name']} {label} 확정!"

    ##
    # @brief result 요청. 규격 9절 판정 순서대로 확인하고 /승리와 같은 record_result_locked()로 기록한다.
    # @param user_id 보낸 사람 Discord ID(문자열).
    # @param game_id 요청의 판 ID.
    # @param winner 승리 팀 문자열.
    # @return (code, message).
    async def activity_result(self, user_id, game_id, winner):
        async with self.lock:
            if game_id != self.visible_game_id():
                return "stale_game", "이미 끝났거나 바뀐 판입니다."
            phase = self.visible_phase()
            if phase == "completed":
                return "already_recorded", "이미 결과가 기록된 판입니다."
            if phase != "awaiting_result":
                return "wrong_phase", "아직 결과를 입력할 수 없습니다."
            if not self.dev_mode and not self._is_player(user_id):
                return "not_allowed", "이 판의 참가자만 결과를 입력할 수 있습니다."
            if winner not in TEAM_KEYS:
                return "bad_request", "승리 팀이 올바르지 않습니다."
            outcome = self.record_result_locked(winner)
            if outcome.code == "record_failed":
                return "record_failed", "전적 저장에 실패했습니다. 다시 시도해 주세요."
            if outcome.code != "ok":
                log.error("[GAME] 예상하지 못한 기록 결과: %s", outcome.code)
                return "server_error", "결과를 기록하지 못했습니다."
        self._run_effect("result_recorded", outcome)
        return "ok", f"TEAM {winner[-1]} 승리를 기록했습니다."

    ##
    # @brief reverse 요청. 규격 9절 판정 순서대로 확인하고 /번복과 같은 reverse_locked()로 화면의 판을 뒤집는다.
    # @param user_id 보낸 사람 Discord ID(문자열).
    # @param game_id 요청의 판 ID.
    # @param expected_winner 보낸 사람이 본 현재 승리 팀.
    # @return (code, message).
    async def activity_reverse(self, user_id, game_id, expected_winner):
        async with self.lock:
            if game_id != self.visible_game_id():
                return "stale_game", "이미 끝났거나 바뀐 판입니다."
            if self.visible_phase() != "completed":
                return "wrong_phase", "아직 결과가 기록되지 않았습니다."
            if not self.dev_mode and not self._is_player(user_id):
                return "not_allowed", "이 판의 참가자만 결과를 바꿀 수 있습니다."
            if self.result["winner"] != expected_winner:
                return "conflict", "그사이 다른 사람이 결과를 바꿨습니다."
            record = (
                self.find_game(self.game_round, self.dev_mode)
                if self.result["history_recorded"]
                else None
            )
            if record is None or record.get("season") != self.game_season:
                return "record_failed", "판 기록을 찾지 못해 번복할 수 없습니다."
            try:
                _, _, new_winner = self.reverse_locked(record)
            except Exception as e:
                log.error("[GAME] 번복 실패 R%s: %s", self.game_round, e)
                return "record_failed", "번복을 저장하지 못했습니다. 다시 시도해 주세요."
        self._run_effect("result_reversed", record)
        return "ok", f"ROUND {record['round']} 결과를 TEAM {new_winner[-1]} 승리로 바꿨습니다."
