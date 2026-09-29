# 5·6위 어드밴티지(밴·강제픽)의 이점 판정·선택 단계·픽 규칙·자동 배정·판 기록을 가짜 시계로 검증하는 테스트
##
# @file test_advantage.py
# @brief game_core.GameCore의 5·6위 어드밴티지 규칙(docs/ACTIVITY_PROTOCOL.md 14절) 테스트.
# @details 팀과 픽 순서는 test_activity_rules.arrange로 고정한다. 0~2가 TEAM 1, 3~5가 TEAM 2이고,
#          순서 튜플은 6위부터 적는다.
import asyncio
import json
import os
import tempfile
import unittest
from unittest import mock

import game_recorder
from game_core import advantage_of
from tests.test_activity_rules import (
    BAN_TEAM1,
    FORCE_TEAM2,
    NO_ADVANTAGE,
    RulesBase,
    arrange,
    settle,
)
from tests.test_game_core import FakeStore, Member, make_core, members

TEAMS = {"team1": [0, 1, 2], "team2": [3, 4, 5]}


##
# @brief 인덱스로 적은 순서와 팀을 멤버 객체로 바꿔 advantage_of를 부른다.
def judge(order):
    people = members(6)
    teams = {key: [people[i] for i in idx] for key, idx in TEAMS.items()}
    return advantage_of([people[i] for i in order], teams)


class AdvantageOfTest(unittest.TestCase):

    def test_bottom_two_on_different_teams_has_no_advantage(self):
        self.assertIsNone(judge(NO_ADVANTAGE))
        self.assertIsNone(judge((0, 3, 1, 2, 4, 5)))

    def test_kind_by_rank_of_remaining_member(self):
        # 나머지 한 명의 위치(인덱스 2~5 = 4위·3위·2위·1위)로 종류가 정해진다
        cases = [
            ((0, 1, 2, 3, 4, 5), "force"),  # 4위
            ((0, 1, 3, 2, 4, 5), "force"),  # 3위
            ((0, 1, 3, 4, 2, 5), "ban"),  # 2위
            ((0, 1, 3, 4, 5, 2), "ban"),  # 1위
        ]
        for order, kind in cases:
            with self.subTest(order=order):
                self.assertEqual(judge(order), {"kind": kind, "team": "team1"})

    def test_team2_advantage(self):
        self.assertEqual(judge(FORCE_TEAM2), {"kind": "force", "team": "team2"})
        self.assertEqual(judge((4, 5, 0, 1, 2, 3)), {"kind": "ban", "team": "team2"})


class NewGameAdvantageTest(unittest.IsolatedAsyncioTestCase):

    async def test_ties_follow_random_pick_order(self):
        # 승수가 모두 같으면 픽 순서가 무작위다. 이점은 그때 정해진 pick_order를 그대로 따른다
        kinds = set()
        for seed in range(30):
            with self.subTest(seed=seed):
                core = make_core(FakeStore(), dev_mode=False, seed=seed)
                core.new_game(members(8), "activity")
                await core.close()
                team_of = {m.id: key for key, team in core.teams.items() for m in team}
                rank6, rank5 = core.pick_order[0], core.pick_order[1]
                if team_of[rank6.id] != team_of[rank5.id]:
                    self.assertIsNone(core.advantage)
                    kinds.add(None)
                    continue
                team = team_of[rank6.id]
                third = next(m for m in core.teams[team] if m not in (rank6, rank5))
                kind = "ban" if core.pick_order.index(third) >= 4 else "force"
                self.assertEqual(
                    core.advantage, {"kind": kind, "team": team, "status": "pending", "champion": None}
                )
                kinds.add(kind)
        self.assertEqual(kinds, {None, "ban", "force"})  # 시드 30개로 세 경우가 모두 나온다


##
# @brief 어드밴티지가 있는 판을 advantage phase까지 진행하는 도우미를 더한 테스트 기반.
class AdvantageBase(RulesBase):
    order = BAN_TEAM1

    async def asyncSetUp(self):
        await super().asyncSetUp()
        arrange(self.core, self.order)

    def ids(self, team):
        return [p["id"] for p in self.state()["players"] if p["team"] == team]

    async def open_advantage(self):
        code, _ = await self.start()
        self.assertEqual(code, "ok")
        await self.begin()
        self.assertEqual(self.state()["phase"], "advantage")

    async def advantage(self, user_id, champion_id=None, game_id=None, received_at=None):
        s = self.state()
        return await self.core.activity_advantage(
            user_id,
            game_id if game_id is not None else s["game_id"],
            champion_id if champion_id is not None else s["champions"][0]["id"],
            received_at if received_at is not None else self.clock(),
        )

    async def choose(self, index=0):
        """이점 팀의 첫 사람이 후보 index를 골라 확정하고 그 챔피언 ID를 돌려준다."""
        s = self.state()
        champ = s["champions"][index]["id"]
        code, _ = await self.advantage(self.ids(s["advantage"]["team"])[0], champ)
        self.assertEqual(code, "ok")
        return champ


class AdvantagePhaseTest(AdvantageBase):

    async def test_starting_shows_pending_then_advantage_phase(self):
        await self.start()
        s = self.state()
        self.assertEqual(s["phase"], "starting")
        self.assertEqual(
            s["advantage"], {"kind": "ban", "team": "team1", "status": "pending", "champion_id": None}
        )
        self.assertFalse(self.me(self.ids("team1")[0])["can_advantage"])
        await self.begin()
        s = self.state()
        self.assertEqual(s["phase"], "advantage")
        self.assertEqual(s["deadline_ms"] - s["server_ms"], 20000)
        self.assertEqual(s["grace_ms"], 2000)
        self.assertIsNone(s["turn_id"])
        self.assertIsNone(s["current_index"])
        self.assertIsNone(s["start_at_ms"])
        team1, team2 = self.ids("team1"), self.ids("team2")
        for uid in team1:
            self.assertTrue(self.me(uid)["can_advantage"])
            self.assertFalse(self.me(uid)["can_pick"])
        for uid in team2 + ["999"]:
            self.assertFalse(self.me(uid)["can_advantage"])
        await settle()
        self.assertIn(("board_changed",), self.effects.calls)

    async def test_rejection_codes_in_order(self):
        await self.start()
        s = self.state()
        team1, team2 = self.ids("team1"), self.ids("team2")
        self.assertEqual((await self.advantage(team1[0], game_id="g-old"))[0], "stale_game")
        self.assertEqual((await self.advantage(team1[0]))[0], "wrong_phase")  # starting
        await self.begin()
        limit = self.core.deadline + 2
        cases = [
            (dict(user_id=team2[0], game_id="g-old", champion_id="Nope"), "stale_game"),
            (dict(user_id=team2[0], champion_id="Nope", received_at=limit + 1), "not_allowed"),
            (dict(user_id="999", champion_id="Nope"), "not_allowed"),
            (dict(user_id=team1[1], champion_id="Nope", received_at=limit + 0.001), "timeout"),
            (dict(user_id=team1[1], champion_id="Nope", received_at=limit), "not_candidate"),
        ]
        for kwargs, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual((await self.advantage(**kwargs))[0], expected)
        self.assertEqual(self.state()["advantage"]["status"], "pending")
        champ = s["champions"][2]
        code, message = await self.advantage(team1[2], champ["id"])
        self.assertEqual((code, message), ("ok", f"{champ['name']} 밴 확정!"))
        after = self.state()
        self.assertEqual(after["phase"], "picking")
        self.assertEqual(after["advantage"]["status"], "chosen")
        self.assertEqual(after["advantage"]["champion_id"], champ["id"])
        self.assertEqual((after["current_index"], after["turn_id"]), (0, f"{after['game_id']}:0"))
        self.assertEqual(after["deadline_ms"] - after["server_ms"], 20000)  # 픽 첫 차례는 새 20초
        # 확정된 뒤에는 다시 고를 수 없다
        self.assertEqual((await self.advantage(team1[0], s["champions"][3]["id"]))[0], "wrong_phase")
        self.assertEqual(self.state()["advantage"]["champion_id"], champ["id"])

    async def test_first_of_concurrent_requests_wins(self):
        await self.open_advantage()
        s = self.state()
        team1 = self.ids("team1")
        results = await asyncio.gather(
            self.advantage(team1[0], s["champions"][0]["id"]),
            self.advantage(team1[1], s["champions"][1]["id"]),
        )
        self.assertEqual([code for code, _ in results], ["ok", "wrong_phase"])
        self.assertEqual(self.state()["advantage"]["champion_id"], s["champions"][0]["id"])

    async def test_timeout_skips_to_picking(self):
        await self.open_advantage()
        await self.clock.advance(21.9)
        self.assertEqual(self.state()["phase"], "advantage")  # 유예 중
        await self.clock.advance(0.1)
        s = self.state()
        self.assertEqual(s["phase"], "picking")
        self.assertEqual(
            s["advantage"], {"kind": "ban", "team": "team1", "status": "skipped", "champion_id": None}
        )
        self.assertEqual(s["current_index"], 0)
        self.assertEqual(s["deadline_ms"] - s["server_ms"], 20000)
        self.assertEqual((await self.advantage(self.ids("team1")[0]))[0], "wrong_phase")
        # 건너뛴 판은 규칙 없이 진행한다
        self.assertEqual((await self.pick(champion_id=s["champions"][0]["id"]))[0], "ok")

    async def test_confirm_cancels_skip_timer(self):
        await self.open_advantage()
        await self.clock.advance(10)
        await self.choose()
        await self.clock.advance(12.5)  # 어드밴티지 마감+유예가 지나도 건너뛰지 않는다
        s = self.state()
        self.assertEqual(s["advantage"]["status"], "chosen")
        self.assertEqual((s["phase"], s["current_index"]), ("picking", 0))

    async def test_new_game_clears_advantage(self):
        await self.open_advantage()
        arrange(self.core, NO_ADVANTAGE)
        async with self.core.lock:
            self.core.new_game(self.people, "activity")  # /게임시작
        self.assertIsNone(self.state()["advantage"])
        await self.begin()
        self.assertEqual(self.state()["phase"], "picking")


class BanPickTest(AdvantageBase):

    async def test_banned_champion_rejected_for_everyone(self):
        await self.open_advantage()
        banned = await self.choose(0)
        for _ in range(6):
            self.assertEqual((await self.pick(champion_id=banned))[0], "champion_banned")
            self.assertEqual((await self.pick(champion_id="Nope"))[0], "not_candidate")
            s = self.state()
            free = next(
                c["id"] for c in s["champions"]
                if c["id"] != banned and c["id"] not in s["selections"].values()
            )
            self.assertEqual((await self.pick(champion_id=free))[0], "ok")
        self.assertEqual(self.state()["phase"], "awaiting_result")

    async def test_timeout_checked_before_ban(self):
        await self.open_advantage()
        banned = await self.choose(0)
        late = self.core.deadline + 3
        self.assertEqual((await self.pick(champion_id=banned, received_at=late))[0], "timeout")

    async def test_auto_assign_never_gives_banned(self):
        for seed in range(5):
            with self.subTest(seed=seed):
                gid = self.state()["game_id"]
                self.assertEqual((await self.start(game_id=gid))[0], "ok")
                self.core.rng.seed(seed)
                await self.begin()
                banned = await self.choose(seed)
                for _ in range(6):
                    await self.clock.advance(22)
                s = self.state()
                self.assertEqual(s["phase"], "awaiting_result")
                self.assertEqual(len(s["auto_assigned"]), 6)
                self.assertNotIn(banned, s["selections"].values())


class ForcePickTest(AdvantageBase):
    order = FORCE_TEAM2  # TEAM 2 강제픽. TEAM 1(상대 팀)의 마지막 차례는 인덱스 5

    async def asyncSetUp(self):
        await super().asyncSetUp()
        await self.open_advantage()
        self.forced = await self.choose(0)
        s = self.state()
        self.others = [c["id"] for c in s["champions"] if c["id"] != self.forced]
        self.team = {p["id"]: p["team"] for p in s["players"]}

    async def pick_other(self):
        taken = set(self.state()["selections"].values())
        return await self.pick(champion_id=next(c for c in self.others if c not in taken))

    async def test_state_and_message(self):
        s = self.state()
        self.assertEqual(
            s["advantage"],
            {"kind": "force", "team": "team2", "status": "chosen", "champion_id": self.forced},
        )

    async def test_advantage_team_cannot_pick_forced(self):
        self.assertEqual(self.team[self.picker_id()], "team2")
        self.assertEqual((await self.pick(champion_id=self.forced))[0], "champion_reserved")
        self.assertEqual((await self.pick_other())[0], "ok")

    async def test_last_opponent_must_pick_forced(self):
        for _ in range(5):  # 인덱스 0~4: 아무도 강제픽을 고르지 않는다
            self.assertEqual((await self.pick_other())[0], "ok")
        self.assertEqual(self.state()["current_index"], 5)
        self.assertEqual(self.team[self.picker_id()], "team1")
        code, message = await self.pick_other()
        self.assertEqual(code, "must_pick_forced")
        name = next(c["name"] for c in self.state()["champions"] if c["id"] == self.forced)
        self.assertEqual(message, f"강제픽 챔피언({name})을 골라야 하는 차례입니다.")
        self.assertEqual((await self.pick(champion_id=self.forced))[0], "ok")
        self.assertEqual(self.state()["phase"], "awaiting_result")

    async def test_earlier_opponent_takes_forced_then_rest_free(self):
        self.assertEqual((await self.pick_other())[0], "ok")  # 0: TEAM 2
        self.assertEqual((await self.pick_other())[0], "ok")  # 1: TEAM 2
        self.assertEqual(self.team[self.picker_id()], "team1")
        self.assertEqual((await self.pick(champion_id=self.forced))[0], "ok")  # 2: TEAM 1이 강제픽
        for _ in range(3):  # 마지막 차례도 자유롭게 고른다
            self.assertEqual((await self.pick_other())[0], "ok")
        self.assertEqual(self.state()["phase"], "awaiting_result")

    async def test_non_last_opponent_may_pick_other(self):
        await self.pick_other()
        await self.pick_other()
        self.assertEqual(self.team[self.picker_id()], "team1")
        self.assertEqual((await self.pick_other())[0], "ok")

    async def test_auto_assign_gives_forced_on_last_opponent_turn(self):
        for _ in range(5):
            await self.pick_other()
        await self.clock.advance(22)
        s = self.state()
        last = s["pick_order"][5]
        self.assertEqual(s["auto_assigned"], [last])
        self.assertEqual(s["selections"][last], self.forced)

    async def test_auto_assign_keeps_forced_for_opponents(self):
        for seed in range(8):
            with self.subTest(seed=seed):
                if seed:
                    gid = self.state()["game_id"]
                    self.assertEqual((await self.start(game_id=gid))[0], "ok")
                    await self.begin()
                    self.forced = await self.choose(seed % 8)
                self.core.rng.seed(seed)
                for _ in range(6):
                    await self.clock.advance(22)
                s = self.state()
                self.assertEqual(s["phase"], "awaiting_result")
                holders = [uid for uid, champ in s["selections"].items() if champ == self.forced]
                self.assertEqual(len(holders), 1)  # 상대 팀 누군가는 반드시 강제픽을 한다
                self.assertEqual(self.team[holders[0]], "team1")


class DevModeAdvantageTest(AdvantageBase):
    dev_mode = True
    order = FORCE_TEAM2

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.dev_people = [Member(900 + i, f"가상{i}") for i in range(6)]
        self.effects.guild_members = {"guild-1": self.dev_people}

    async def test_anyone_chooses_and_rules_use_picker_team(self):
        tester = "555"  # 이 판의 6명이 아닌 접속자
        await self.open_advantage()
        self.assertTrue(self.me(tester)["can_advantage"])
        s = self.state()
        forced = s["champions"][0]["id"]
        self.assertEqual((await self.advantage(tester, forced))[0], "ok")
        # 강제픽 판정은 보낸 사람이 아니라 지금 차례인 사람의 팀으로 한다
        self.assertEqual((await self.pick(user_id=tester, champion_id=forced))[0], "champion_reserved")
        others = [c["id"] for c in s["champions"] if c["id"] != forced]
        for champ in others[:5]:
            self.assertEqual((await self.pick(user_id=tester, champion_id=champ))[0], "ok")
        self.assertEqual((await self.pick(user_id=tester, champion_id=others[5]))[0], "must_pick_forced")
        self.assertEqual((await self.pick(user_id=tester, champion_id=forced))[0], "ok")


class EmbedModeAdvantageTest(AdvantageBase):
    pick_mode = "embed"

    async def test_embed_game_has_no_advantage(self):
        async with self.core.lock:
            self.core.new_game(self.people, "embed")  # /게임시작(embed), 배치는 BAN_TEAM1
        self.assertIsNone(self.core.advantage)
        self.assertIsNone(self.state()["advantage"])
        self.core.game_started = True
        for i in range(6):
            self.assertIsNotNone(self.core.auto_assign(i))
        self.assertEqual(len(self.core.selected_users), 6)


class AdvantageRecordTest(AdvantageBase):

    async def finish(self):
        for _ in range(6):
            s = self.state()
            banned = s["advantage"]["champion_id"] if s["advantage"] else None
            free = next(
                c["id"] for c in s["champions"]
                if c["id"] != banned and c["id"] not in s["selections"].values()
            )
            self.assertEqual((await self.pick(champion_id=free))[0], "ok")
        code, _ = await self.core.activity_result(self.ids("team1")[0], self.state()["game_id"], "team1")
        self.assertEqual(code, "ok")

    async def test_chosen_advantage_is_recorded_with_korean_name(self):
        await self.open_advantage()
        champ = self.state()["champions"][4]
        await self.advantage(self.ids("team1")[0], champ["id"])
        await self.finish()
        self.assertEqual(
            self.store.games[0]["advantage"],
            {"kind": "ban", "team": "team1", "champion": champ["name"]},
        )
        # 완료 뒤에도 state에 남는다
        self.assertEqual(self.state()["advantage"]["status"], "chosen")

    async def test_skipped_advantage_is_not_recorded(self):
        await self.open_advantage()
        await self.clock.advance(22)
        await self.finish()
        self.assertNotIn("advantage", self.store.games[0])

    async def test_game_without_advantage_is_not_recorded(self):
        arrange(self.core, NO_ADVANTAGE)
        await self.start_picking()
        await self.finish()
        self.assertNotIn("advantage", self.store.games[0])


class RecorderAdvantageFieldTest(unittest.TestCase):

    def test_record_game_writes_field_only_when_given(self):
        teams = {
            key: [{"id": str(i), "name": f"p{i}", "champ": f"챔{i}"} for i in idx]
            for key, idx in TEAMS.items()
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "history_data_dev.json")
            with mock.patch.object(game_recorder.paths, "history_json", lambda dev_mode=False: path):
                game_recorder.record_game(1, teams, "team1", dev_mode=True)
                adv = {"kind": "force", "team": "team2", "champion": "제드"}
                game_recorder.record_game(2, teams, "team2", dev_mode=True, advantage=adv)
            with open(path, encoding="utf-8") as f:
                games = json.load(f)["games"]
        self.assertNotIn("advantage", games[0])
        self.assertEqual(games[1]["advantage"], adv)


if __name__ == "__main__":
    unittest.main()
