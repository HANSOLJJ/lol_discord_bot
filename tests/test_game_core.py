# 공통 게임 함수(판 만들기·자동 배정·승리 기록·번복)가 예전 embed 모드와 같은 동작을 하는지 확인하는 회귀 테스트
##
# @file test_game_core.py
# @brief game_core.GameCore의 공통 함수가 예전 got_champe.py(/게임시작, 자동 배정, VictorySelect.callback,
#        ReverseConfirmView.confirm)와 같은 문구·저장 순서·실패 시 원복을 지키는지 검증한다.
# @details 파일 저장 함수는 호출을 기록하는 가짜로 주입한다. 실제 파일·디스코드는 쓰지 않는다.
import random
import unittest

from game_core import GameCore, MAX_PLAYERS, pick_random_champions
from game_recorder import SeasonMismatchError


##
# @brief 테스트용 멤버 (디스코드 Member와 같은 id·display_name·mention 속성).
class Member:

    def __init__(self, user_id, name):
        self.id = user_id
        self.name = name
        self.display_name = name
        self.mention = f"<@{user_id}>"

    def __repr__(self):
        return f"Member({self.id})"


##
# @brief 호출 순서를 기록하는 가짜 저장소. wins·판 기록을 메모리에 둔다.
class FakeStore:

    def __init__(self):
        self.calls = []  # [(이름, 인자...)]
        self.saved_wins = None
        self.fail_save = False
        self.record_error = None  # record_game이 던질 예외
        self.games = []  # 판 기록 [{round, season, team1, team2, winner}]
        self.season = 2

    def save_wins(self, data):
        self.calls.append(("save_wins", data.get("total_rounds")))
        if self.fail_save:
            raise OSError("디스크 가득 참")
        self.saved_wins = data

    def record_game(self, round_num, teams, winner, dev_mode):
        self.calls.append(("record_game", round_num, winner, dev_mode))
        if self.record_error is not None:
            raise self.record_error
        self.games.append(
            {
                "round": round_num,
                "season": self.season,
                "team1": [{"id": p["id"], "champ": p["champ"]} for p in teams["team1"]],
                "team2": [{"id": p["id"], "champ": p["champ"]} for p in teams["team2"]],
                "winner": winner,
                "names": {p["id"]: p["name"] for p in teams["team1"] + teams["team2"]},
            }
        )
        return self.season

    def find_game(self, round_num, dev_mode):
        for g in reversed(self.games):
            if g["season"] == self.season and (round_num is None or g["round"] == round_num):
                return dict(g)
        return None

    def set_game_winner(self, round_num, winner, dev_mode):
        self.calls.append(("set_game_winner", round_num, winner))
        for g in reversed(self.games):
            if g["season"] == self.season and g["round"] == round_num:
                old = g["winner"]
                g["winner"] = winner
                return old
        raise ValueError("없음")

    def get_season(self, dev_mode):
        return self.season


CHAMPIONS = [{"id": f"Champ{i}", "name": f"챔피언{i}", "image": ""} for i in range(20)]


##
# @brief 테스트용 GameCore를 만든다.
# @param store FakeStore.
# @param dev_mode DEV_MODE 여부.
# @param seed 난수 시드.
def make_core(store, dev_mode=True, seed=1):
    core = GameCore(
        dev_mode=dev_mode,
        save_wins=store.save_wins,
        record_game=store.record_game,
        find_game=store.find_game,
        set_game_winner=store.set_game_winner,
        get_season=store.get_season,
        wall_ms=lambda: 1790000000000,
        rng=random.Random(seed),
    )
    core.config = {"champion_count": 8, "pick_mode": "embed"}
    core.champion_list = list(CHAMPIONS)
    return core


def members(n=6, start=101):
    return [Member(start + i, f"선수{i}") for i in range(n)]


##
# @brief 판을 만들고 모두 고른 상태로 만든다(embed 픽 흐름과 같은 상태 변화).
def play_until_all_picked(core, people):
    core.new_game(people, "embed")
    core.game_started = True
    for member in list(core.pick_order):
        champ = next(c["name"] for c in core.current_game_champions if c["name"] not in core.excluded)
        core.selected_users[member.id] = champ
        core.excluded.add(champ)
        core.current_pick_index += 1


class NewGameTest(unittest.TestCase):

    def setUp(self):
        self.store = FakeStore()
        self.core = make_core(self.store)

    def test_dev_mode_uses_first_six_and_orders_by_wins(self):
        people = members(8)
        self.core.wins_data = {"total_rounds": 5, "101": {"name": "a", "wins": 3}, "102": {"name": "b", "wins": 1}}
        result = self.core.new_game(people, "embed")
        self.assertTrue(result.ok)
        self.assertFalse(result.pool_reset)
        chosen = {m.id for m in self.core.pick_order}
        self.assertEqual(chosen, {101, 102, 103, 104, 105, 106})  # DEV_MODE: 앞의 6명
        wins = [self.core.wins_of(m.id) for m in self.core.pick_order]
        self.assertEqual(wins, sorted(wins))  # 승수 낮은 사람부터
        self.assertEqual(self.core.pick_order[-1].id, 101)
        self.assertEqual(len(self.core.current_teams["team1"]), 3)
        self.assertEqual(len(self.core.current_teams["team2"]), 3)
        self.assertEqual(
            {m.id for t in self.core.current_teams.values() for m in t}, chosen
        )
        self.assertEqual(len(self.core.current_game_champions), 8)

    def test_prod_mode_samples_six_of_online(self):
        core = make_core(self.store, dev_mode=False)
        core.new_game(members(10), "embed")
        self.assertEqual(len(core.pick_order), MAX_PLAYERS)
        self.assertEqual(len({m.id for m in core.pick_order}), MAX_PLAYERS)

    def test_resets_previous_game_state(self):
        play_until_all_picked(self.core, members())
        self.core.victory_processed = True
        old_id = self.core.current_game_id
        self.core.new_game(members(), "embed")
        self.assertEqual(self.core.current_game_id, old_id + 1)
        self.assertEqual(self.core.selected_users, {})
        self.assertEqual(self.core.auto_assigned_users, set())
        self.assertFalse(self.core.game_started)
        self.assertFalse(self.core.victory_processed)
        self.assertEqual(self.core.current_pick_index, 0)

    def test_candidates_skip_excluded_and_reset_pool_when_exhausted(self):
        self.core.excluded = {c["name"] for c in CHAMPIONS[:13]}  # 남은 챔피언 7개 < 8
        result = self.core.new_game(members(), "embed")
        self.assertTrue(result.ok)
        self.assertTrue(result.pool_reset)
        self.assertEqual(self.core.excluded, set())

    def test_not_enough_champions_fails(self):
        self.core.champion_list = CHAMPIONS[:5]
        result = self.core.new_game(members(), "embed")
        self.assertFalse(result.ok)
        self.assertEqual(result.champ_count, 8)
        self.assertIsNone(self.core.game_uid)

    def test_pick_random_champions_filters_by_name(self):
        picked = pick_random_champions(CHAMPIONS, {"챔피언0"}, 19, random.Random(3))
        self.assertEqual(len(picked), 19)
        self.assertNotIn("챔피언0", [c["name"] for c in picked])
        self.assertEqual(pick_random_champions(CHAMPIONS, {"챔피언0"}, 20), [])


class AutoAssignTest(unittest.TestCase):

    def setUp(self):
        self.store = FakeStore()
        self.core = make_core(self.store)
        self.core.new_game(members(), "embed")
        self.core.game_started = True

    def test_assigns_remaining_candidate_and_advances(self):
        first = self.core.pick_order[0]
        taken = self.core.current_game_champions[0]["name"]
        self.core.excluded.add(taken)
        champ = self.core.auto_assign(0)
        self.assertIsNotNone(champ)
        self.assertNotEqual(champ, taken)
        self.assertIn(champ, [c["name"] for c in self.core.current_game_champions])
        self.assertEqual(self.core.selected_users[first.id], champ)
        self.assertIn(champ, self.core.excluded)
        self.assertEqual(self.core.auto_assigned_users, {first.id})
        self.assertEqual(self.core.current_pick_index, 1)

    def test_does_nothing_when_already_picked(self):
        first = self.core.pick_order[0]
        self.core.selected_users[first.id] = "챔피언X"
        self.assertIsNone(self.core.auto_assign(0))
        self.assertEqual(self.core.current_pick_index, 0)
        self.assertEqual(self.core.auto_assigned_users, set())


class RecordResultTest(unittest.TestCase):
    """예전 VictorySelect.callback과 같은 문구·저장 순서·원복을 확인한다."""

    def setUp(self):
        self.store = FakeStore()
        self.core = make_core(self.store)
        self.core.wins_data = {"total_rounds": 86, "101": {"name": "선수0", "wins": 10}}
        self.core.round_counter = 87
        self.people = members()
        self.changes = []
        self.core.add_listener(lambda: self.changes.append(1))

    def test_rejects_without_game(self):
        outcome = self.core.record_result_locked("team1")
        self.assertEqual(outcome.code, "no_game")
        self.assertEqual(outcome.message, "⚠️ 먼저 `/게임시작`으로 팀을 구성해주세요!")
        self.assertEqual(self.store.calls, [])

    def test_rejects_when_someone_has_not_picked(self):
        self.core.new_game(self.people, "embed")
        outcome = self.core.record_result_locked("team1")
        first = self.core.current_teams["team1"][0]
        self.assertEqual(outcome.code, "not_picked")
        self.assertEqual(outcome.message, f"❌ {first.mention} 님이 챔피언을 선택하지 않았습니다!")
        self.assertFalse(self.core.victory_processed)
        self.assertEqual(self.store.calls, [])

    def test_success_saves_wins_then_records_game(self):
        play_until_all_picked(self.core, self.people)
        team1 = list(self.core.current_teams["team1"])
        team2 = list(self.core.current_teams["team2"])
        selections = dict(self.core.selected_users)

        outcome = self.core.record_result_locked("team1")

        self.assertEqual(outcome.code, "ok")
        self.assertEqual(outcome.message, "✅ **TEAM1** 승리 기록 완료!")
        self.assertEqual(outcome.round, 87)
        self.assertEqual(outcome.teams, {"team1": team1, "team2": team2})
        self.assertEqual(outcome.selections, selections)
        self.assertIsNone(outcome.season_warning)
        # 승수 저장이 판 기록보다 먼저다
        self.assertEqual(self.store.calls, [("save_wins", 87), ("record_game", 87, "team1", True)])
        for m in team1:
            self.assertEqual(self.core.wins_of(m.id), 11 if m.id == 101 else 1)
        for m in team2:
            self.assertEqual(self.core.wins_of(m.id), 10 if m.id == 101 else 0)
        self.assertEqual(self.core.wins_data["total_rounds"], 87)
        self.assertIs(self.core.wins_data, self.store.saved_wins)
        self.assertEqual(self.core.round_counter, 88)
        self.assertEqual(self.core.session_rounds, [87])
        for m in team1:
            self.assertEqual(self.core.overall_results[m.id], {"mention": m.mention, "results": ["O"]})
        for m in team2:
            self.assertEqual(self.core.overall_results[m.id]["results"], ["X"])
        self.assertTrue(self.core.victory_processed)
        self.assertEqual(self.core.current_teams, {})  # 예전처럼 기록 뒤 비운다
        self.assertEqual(self.core.result["winner"], "team1")
        game = self.store.games[0]
        self.assertEqual(game["team1"], [{"id": str(m.id), "champ": selections[m.id]} for m in team1])
        self.assertEqual(game["names"][str(team1[0].id)], team1[0].display_name)
        self.assertTrue(self.changes)

    def test_second_record_is_rejected(self):
        play_until_all_picked(self.core, self.people)
        self.core.record_result_locked("team2")
        outcome = self.core.record_result_locked("team1")
        self.assertEqual(outcome.code, "already_recorded")
        self.assertEqual(outcome.message, "⚠️ 이미 승리 처리가 완료되었습니다!")
        self.assertEqual(self.core.round_counter, 88)

    def test_save_failure_changes_nothing_and_can_retry(self):
        play_until_all_picked(self.core, self.people)
        before = dict(self.core.wins_data)
        self.store.fail_save = True
        outcome = self.core.record_result_locked("team1")
        self.assertEqual(outcome.code, "record_failed")
        self.assertEqual(outcome.message, "❌ 전적 저장에 실패했습니다. 다시 선택해주세요: 디스크 가득 참")
        self.assertFalse(self.core.victory_processed)
        self.assertEqual(self.core.wins_data, before)
        self.assertEqual(self.core.round_counter, 87)
        self.assertEqual(self.core.overall_results, {})
        self.assertEqual(self.core.session_rounds, [])
        self.assertNotEqual(self.core.current_teams, {})
        self.assertEqual([c[0] for c in self.store.calls], ["save_wins"])  # 판 기록까지 가지 않는다

        self.store.fail_save = False
        self.assertEqual(self.core.record_result_locked("team1").code, "ok")

    def test_season_mismatch_warns_but_keeps_victory(self):
        play_until_all_picked(self.core, self.people)
        self.store.record_error = SeasonMismatchError("라운드 회귀")
        outcome = self.core.record_result_locked("team2")
        self.assertEqual(outcome.code, "ok")
        self.assertEqual(outcome.season_warning, "⚠️ 판 기록이 중단되었습니다.\n라운드 회귀")
        self.assertTrue(self.core.victory_processed)
        self.assertFalse(self.core.result["history_recorded"])

    def test_other_record_error_is_ignored(self):
        play_until_all_picked(self.core, self.people)
        self.store.record_error = ValueError("깨진 파일")
        outcome = self.core.record_result_locked("team2")
        self.assertEqual(outcome.code, "ok")
        self.assertIsNone(outcome.season_warning)


class ReverseTest(unittest.TestCase):
    """예전 ReverseConfirmView.confirm과 같은 저장 순서·원복을 확인한다."""

    def setUp(self):
        self.store = FakeStore()
        self.core = make_core(self.store)
        self.core.wins_data = {"total_rounds": 0}
        self.core.round_counter = 1
        play_until_all_picked(self.core, members())
        self.core.record_result_locked("team1")
        self.store.calls.clear()
        self.record = self.store.find_game(1, True)
        self.team1_ids = [p["id"] for p in self.record["team1"]]
        self.team2_ids = [p["id"] for p in self.record["team2"]]

    def test_flips_history_then_wins_and_today_results(self):
        wins_before = {uid: self.core.wins_of(uid) for uid in self.team1_ids + self.team2_ids}
        result = self.core.reverse_locked(self.record)
        self.assertEqual(result, (1, "team1", "team2"))
        self.assertEqual(self.store.calls, [("set_game_winner", 1, "team2"), ("save_wins", 1)])
        for uid in self.team1_ids:
            self.assertEqual(self.core.wins_of(uid), wins_before[uid] - 1)
        for uid in self.team2_ids:
            self.assertEqual(self.core.wins_of(uid), wins_before[uid] + 1)
        self.assertEqual(self.core.wins_data["total_rounds"], 1)  # 판 수는 그대로
        for uid in self.team1_ids:
            self.assertEqual(self.core.overall_results[int(uid)]["results"], ["X"])
        for uid in self.team2_ids:
            self.assertEqual(self.core.overall_results[int(uid)]["results"], ["O"])
        # 화면에 떠 있는 판이므로 결과도 고친다
        self.assertEqual(self.core.result["winner"], "team2")
        self.assertEqual(self.core.result["corrected"], {"from": "team1", "at_ms": 1790000000000})

    def test_save_failure_restores_history_and_keeps_wins(self):
        wins_before = dict(self.core.wins_data)
        self.store.fail_save = True
        with self.assertRaises(OSError):
            self.core.reverse_locked(self.record)
        self.assertEqual(
            self.store.calls,
            [("set_game_winner", 1, "team2"), ("save_wins", 1), ("set_game_winner", 1, "team1")],
        )
        self.assertEqual(self.store.find_game(1, True)["winner"], "team1")
        self.assertEqual(self.core.wins_data, wins_before)
        self.assertEqual(self.core.result["winner"], "team1")
        self.assertIsNone(self.core.result["corrected"])

    def test_changed_record_is_rejected(self):
        self.store.set_game_winner(1, "team2", True)  # 미리보기 뒤에 다른 번복이 먼저 뒤집음
        self.store.calls.clear()
        with self.assertRaises(RuntimeError) as ctx:
            self.core.reverse_locked(self.record)
        self.assertEqual(str(ctx.exception), "R1 기록이 미리보기와 달라져 중단했습니다. 다시 실행해주세요.")
        self.assertEqual(self.store.calls, [])

    def test_other_round_does_not_touch_displayed_result(self):
        self.core.game_round = 99  # 화면에 떠 있는 판이 아닌 판을 번복
        self.core.reverse_locked(self.record)
        self.assertEqual(self.core.result["winner"], "team1")


if __name__ == "__main__":
    unittest.main()
