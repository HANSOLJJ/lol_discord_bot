# 액티비티 요청(start·pick·result·reverse)의 판정 순서·마감·자동 배정·권한 규칙을 가짜 시계로 검증하는 테스트
##
# @file test_activity_rules.py
# @brief game_core.GameCore의 activity 모드 규칙(docs/ACTIVITY_PROTOCOL.md 7~11절) 테스트.
# @details 단조 시계와 sleep을 FakeClock으로 바꿔 실제 20초를 기다리지 않는다. 저장소는 test_game_core의
#          FakeStore를 쓴다.
import asyncio
import random
import unittest
from unittest import mock

import game_core
from game_core import GameCore
from tests.test_game_core import CHAMPIONS, FakeStore, Member, members

START_MS = 1790000000000
# 픽 순서(6위부터)를 뽑힌 6명의 인덱스로 적는다. 0~2가 TEAM 1, 3~5가 TEAM 2다(arrange 참고).
NO_ADVANTAGE = (0, 3, 1, 4, 2, 5)  # 6위·5위가 다른 팀
BAN_TEAM1 = (0, 1, 3, 4, 5, 2)  # 6위·5위가 TEAM 1, 나머지 한 명이 1위
FORCE_TEAM2 = (3, 4, 0, 5, 1, 2)  # 6위·5위가 TEAM 2, 나머지 한 명이 3위. TEAM 1의 마지막 차례는 인덱스 5


##
# @brief 팀 나누기와 후보 뽑기를 고정하는 난수 생성기. 섞지 않고, 뽑기는 앞에서부터 가져온다.
class ArrangedRng(random.Random):

    def shuffle(self, x):
        pass

    def sample(self, population, k):
        return list(population[:k])


##
# @brief 새 판의 팀과 픽 순서를 고정한다. 뽑힌 앞 6명 가운데 0~2가 TEAM 1, 3~5가 TEAM 2가 되고,
#        픽 순서는 order(6위부터)를 따른다. 자동 배정의 무작위 선택은 그대로 남긴다.
# @param core GameCore.
# @param order 픽 순서가 될 인덱스 6개.
def arrange(core, order=NO_ADVANTAGE):
    core.rng = ArrangedRng(0)
    core.calculate_pick_order = lambda selected: [selected[i] for i in order]


##
# @brief 손으로 넘기는 단조 시계. sleep은 advance()로 시각이 목표를 지나야 깨어난다.
class FakeClock:

    def __init__(self, start=1000.0):
        self.now = start
        self._start = start
        self._sleepers = []

    def __call__(self):
        return self.now

    def wall_ms(self):
        return START_MS + round((self.now - self._start) * 1000)

    async def sleep(self, delay):
        fut = asyncio.get_running_loop().create_future()
        self._sleepers.append((self.now + delay, fut))
        await fut

    ##
    # @brief 시각을 넘기고, 목표가 지난 sleep을 깨운 뒤 태스크들이 돌 틈을 준다.
    async def advance(self, seconds):
        self.now += seconds
        for target, fut in self._sleepers:
            if target <= self.now and not fut.done():
                fut.set_result(None)
        self._sleepers = [(t, f) for t, f in self._sleepers if not f.done()]
        await settle()


async def settle():
    for _ in range(30):
        await asyncio.sleep(0)


##
# @brief 길드 멤버 조회와 디스코드 후속 작업을 기록하는 가짜 effects.
class FakeEffects:

    def __init__(self, guild_members):
        self.guild_members = guild_members  # {guild_id: [member]}
        self.calls = []

    def resolve_members(self, guild_id):
        return self.guild_members.get(guild_id)

    async def game_started(self, guild_id, result):
        self.calls.append(("game_started", guild_id))

    async def board_changed(self):
        self.calls.append(("board_changed",))

    async def result_recorded(self, outcome):
        self.calls.append(("result_recorded", outcome.round, outcome.team_key))

    async def result_reversed(self, record):
        self.calls.append(("result_reversed", record["round"], record["winner"]))


##
# @brief activity 모드 GameCore와 가짜 시계·저장소·effects를 준비하는 테스트 기반.
class RulesBase(unittest.IsolatedAsyncioTestCase):
    dev_mode = False
    pick_mode = "activity"

    async def asyncSetUp(self):
        self.clock = FakeClock()
        self.store = FakeStore()
        self.people = members(7)  # 온라인 7명
        self.effects = FakeEffects({"guild-1": self.people, "guild-small": self.people[:5]})
        self.core = GameCore(
            dev_mode=self.dev_mode,
            save_wins=self.store.save_wins,
            record_game=self.store.record_game,
            find_game=self.store.find_game,
            set_game_winner=self.store.set_game_winner,
            get_season=self.store.get_season,
            clock=self.clock,
            wall_ms=self.clock.wall_ms,
            sleep=self.clock.sleep,
        )
        self.core.config = {
            "pick_timeout": 20,
            "auto_start_seconds": 15,
            "ready_countdown_seconds": 5,
            "pick_grace_seconds": 2,
            "champion_count": 8,
            "pick_mode": "embed",
            "dev_pick_mode": "embed",
            ("dev_pick_mode" if self.dev_mode else "pick_mode"): self.pick_mode,
        }
        self.core.champion_list = list(CHAMPIONS)
        self.core.ddragon_version = "15.19.1"
        self.core.wins_data = {"total_rounds": 86}
        self.core.round_counter = 87
        self.core.effects = self.effects
        arrange(self.core)  # 이점이 없는 배치. 어드밴티지 테스트는 다시 arrange한다
        self.changes = 0
        self.core.add_listener(self._on_change)

    async def asyncTearDown(self):
        await self.core.close()

    def _on_change(self):
        self.changes += 1

    def state(self):
        return self.core.snapshot()

    def me(self, user_id):
        return self.core.me(self.state(), user_id)

    async def start(self, user_id="101", game_id=None, guild_id="guild-1"):
        return await self.core.activity_start(user_id, game_id, guild_id)

    async def enter_all(self):
        """이번 판 참가자 전원을 입장시킨다."""
        await self.core.set_present(self.state()["pick_order"])

    async def begin(self):
        """starting 판을 시작 시각까지 넘긴다. 운영은 전원 입장 뒤 5초, DEV_MODE는 고정 15초 자동 시작이다."""
        if self.dev_mode:
            await self.clock.advance(15)
        else:
            await self.enter_all()
            await self.clock.advance(5)

    async def start_picking(self):
        """새 판을 만들고 시작 시각까지 넘겨 picking으로 만든다."""
        code, _ = await self.start()
        self.assertEqual(code, "ok")
        await self.begin()
        self.assertEqual(self.state()["phase"], "picking")

    def picker_id(self):
        s = self.state()
        return s["pick_order"][s["current_index"]]

    def free_champion(self):
        taken = set(self.state()["selections"].values())
        return next(c["id"] for c in self.state()["champions"] if c["id"] not in taken)

    async def pick(self, user_id=None, champion_id=None, turn_id=None, game_id=None, received_at=None):
        s = self.state()
        return await self.core.activity_pick(
            user_id if user_id is not None else self.picker_id(),
            game_id if game_id is not None else s["game_id"],
            turn_id if turn_id is not None else s["turn_id"],
            champion_id if champion_id is not None else self.free_champion(),
            received_at if received_at is not None else self.clock(),
        )

    async def pick_all(self):
        for _ in range(6):
            code, _ = await self.pick()
            self.assertEqual(code, "ok")
        self.assertEqual(self.state()["phase"], "awaiting_result")


class StartTest(RulesBase):

    async def test_start_creates_starting_game(self):
        code, message = await self.start()
        self.assertEqual((code, message), ("ok", "ROUND 87 게임을 시작했습니다."))
        s = self.state()
        self.assertEqual(s["phase"], "starting")
        self.assertTrue(s["game_id"].startswith("g-"))
        self.assertEqual((s["round"], s["season"]), (87, 2))
        self.assertIsNone(s["start_at_ms"])  # 참가자 입장 대기
        self.assertEqual(s["present"], [])
        self.assertIsNone(s["deadline_ms"])
        self.assertIsNone(s["turn_id"])
        self.assertEqual(s["ddragon_version"], "15.19.1")
        self.assertEqual(len(s["players"]), 6)
        self.assertEqual([p["team"] for p in s["players"]], ["team1"] * 3 + ["team2"] * 3)
        self.assertEqual(sorted(s["pick_order"]), sorted(p["id"] for p in s["players"]))
        self.assertEqual(len(s["champions"]), 8)
        for champ in s["champions"]:
            self.assertEqual(champ["id"], "Champ" + champ["name"][3:])
        self.assertEqual((s["selections"], s["auto_assigned"], s["result"]), ({}, [], None))
        await settle()
        self.assertIn(("game_started", "guild-1"), self.effects.calls)

    async def test_auto_start_switches_to_picking_at_start_at(self):
        await self.start()
        await self.enter_all()
        s = self.state()
        self.assertEqual(s["start_at_ms"] - s["server_ms"], 5000)
        await self.clock.advance(4.9)
        self.assertEqual(self.state()["phase"], "starting")
        await self.clock.advance(0.1)
        s = self.state()
        self.assertEqual(s["phase"], "picking")
        self.assertEqual(s["current_index"], 0)
        self.assertEqual(s["turn_id"], f"{s['game_id']}:0")
        self.assertEqual(s["deadline_ms"] - s["server_ms"], 20000)
        self.assertEqual(s["grace_ms"], 2000)
        self.assertIsNone(s["start_at_ms"])

    async def test_deadline_stays_fixed_within_turn(self):
        await self.start_picking()
        first = self.state()["deadline_ms"]
        await self.clock.advance(7)
        s = self.state()
        self.assertEqual(s["deadline_ms"], first)
        self.assertEqual(s["deadline_ms"] - s["server_ms"], 13000)

    async def test_start_only_in_none_awaiting_completed(self):
        await self.start()
        gid = self.state()["game_id"]
        self.assertEqual((await self.start(game_id=gid))[0], "wrong_phase")  # starting
        await self.begin()
        self.assertEqual((await self.start(game_id=gid))[0], "wrong_phase")  # picking
        await self.pick_all()
        # 결과 없이 새 판 (awaiting_result)
        self.assertEqual((await self.start(game_id=gid))[0], "ok")
        self.assertNotEqual(self.state()["game_id"], gid)
        self.assertEqual(self.store.calls, [])  # 이전 판은 기록 없이 버려진다

    async def test_start_after_completed(self):
        await self.start_picking()
        await self.pick_all()
        gid = self.state()["game_id"]
        await self.core.activity_result(self.state()["players"][0]["id"], gid, "team1")
        self.assertEqual(self.state()["phase"], "completed")
        self.assertEqual((await self.start(game_id=gid))[0], "ok")
        self.assertEqual(self.state()["round"], 88)

    async def test_concurrent_starts_make_one_game(self):
        results = await asyncio.gather(self.start("101"), self.start("102"))
        codes = sorted(code for code, _ in results)
        self.assertEqual(codes, ["ok", "stale_game"])
        self.assertEqual(self.core.current_game_id, 1)

    async def test_stale_game_is_checked_before_phase(self):
        await self.start()
        code, _ = await self.start(game_id="g-1")  # 화면이 다른 판을 보고 있다
        self.assertEqual(code, "stale_game")

    async def test_unknown_or_missing_guild_not_allowed(self):
        self.assertEqual((await self.start(guild_id=None))[0], "not_allowed")
        self.assertEqual((await self.start(guild_id="guild-x"))[0], "not_allowed")
        self.assertEqual(self.state()["phase"], "none")

    async def test_not_enough_players(self):
        code, message = await self.start(guild_id="guild-small")
        self.assertEqual(code, "not_enough_players")
        self.assertEqual(message, "온라인인 사람이 6명 필요합니다. (현재 5명)")

    async def test_discord_new_game_cancels_activity_timer(self):
        await self.start()
        await self.enter_all()
        await self.clock.advance(3)
        async with self.core.lock:
            self.core.new_game(self.people, "activity")  # /게임시작이 다시 실행됨
        # 같은 6명이 이미 입장해 있어 새 판은 바로 카운트다운을 건다
        s = self.state()
        self.assertEqual(s["start_at_ms"] - s["server_ms"], 5000)
        await self.clock.advance(4.9)
        self.assertEqual(self.state()["phase"], "starting")  # 이전 판의 자동 시작이 새 판을 시작시키지 않는다
        await self.clock.advance(0.1)
        self.assertEqual(self.state()["phase"], "picking")


class PresenceStartTest(RulesBase):
    """입장 대기 → 참가자 전원 입장 또는 지금 시작 → 5초 카운트다운 → 픽 시작."""

    async def test_waits_without_presence(self):
        await self.start()
        await self.clock.advance(100)
        s = self.state()
        self.assertEqual((s["phase"], s["start_at_ms"]), ("starting", None))

    async def test_present_lists_only_players(self):
        self.assertEqual(self.state()["present"], [])
        await self.core.set_present(["101", "999"])
        self.assertEqual(self.state()["present"], [])  # 판이 없으면 비어 있다
        await self.start()
        s = self.state()
        ids = [p["id"] for p in s["players"]]
        await self.core.set_present([ids[4], "999", ids[1]])  # 999는 관전자
        self.assertEqual(self.state()["present"], [ids[1], ids[4]])  # players 순서
        self.assertIsNone(self.state()["start_at_ms"])  # 전원이 아니다

    async def test_same_presence_does_not_emit(self):
        await self.start()
        await self.core.set_present(["101"])
        before = self.changes
        await self.core.set_present(["101"])
        self.assertEqual(self.changes, before)

    async def test_players_already_present_start_countdown_on_new_game(self):
        await self.core.set_present([str(m.id) for m in self.people])
        await self.start()
        s = self.state()
        self.assertEqual(s["start_at_ms"] - s["server_ms"], 5000)
        await self.clock.advance(5)
        self.assertEqual(self.state()["phase"], "picking")

    async def test_leaving_during_countdown_cancels_and_reentry_restarts(self):
        await self.start()
        ids = self.state()["pick_order"]
        await self.enter_all()
        await self.clock.advance(3)
        await self.core.set_present(ids[1:])
        s = self.state()
        self.assertEqual((s["phase"], s["start_at_ms"]), ("starting", None))
        self.assertTrue(self.me(ids[1])["can_start_now"])
        await self.clock.advance(10)
        self.assertEqual(self.state()["phase"], "starting")  # 취소된 타이머는 시작시키지 않는다
        await self.core.set_present(ids)
        s = self.state()
        self.assertEqual(s["start_at_ms"] - s["server_ms"], 5000)  # 처음부터 다시 5초
        await self.clock.advance(5)
        self.assertEqual(self.state()["phase"], "picking")

    async def test_start_now_forces_countdown_that_survives_leaving(self):
        await self.start()
        s = self.state()
        ids = s["pick_order"]
        await self.core.set_present(ids[:2])
        code, message = await self.core.activity_start_now(ids[0], s["game_id"])
        self.assertEqual((code, message), ("ok", "5초 뒤 시작합니다."))
        s = self.state()
        self.assertEqual(s["start_at_ms"] - s["server_ms"], 5000)
        self.assertFalse(self.me(ids[0])["can_start_now"])
        await self.core.set_present([])  # 모두 나가도 지금 시작은 취소하지 않는다
        self.assertIsNotNone(self.state()["start_at_ms"])
        await self.core.set_present(ids)  # 전원이 들어와도 카운트다운을 다시 잡지 않는다
        await self.clock.advance(5)
        self.assertEqual(self.state()["phase"], "picking")

    async def test_start_now_rejections_in_order(self):
        self.assertEqual((await self.core.activity_start_now("101", None))[0], "wrong_phase")  # none
        await self.start()
        s = self.state()
        gid, player = s["game_id"], s["pick_order"][0]
        self.assertEqual((await self.core.activity_start_now(player, "g-old"))[0], "stale_game")
        self.assertEqual((await self.core.activity_start_now("999", gid))[0], "not_allowed")
        self.assertFalse(self.me("999")["can_start_now"])
        self.assertTrue(self.me(player)["can_start_now"])
        self.assertEqual((await self.core.activity_start_now(player, gid))[0], "ok")
        self.assertEqual((await self.core.activity_start_now(player, gid))[0], "wrong_phase")  # 카운트다운 중
        await self.clock.advance(5)
        self.assertEqual((await self.core.activity_start_now(player, gid))[0], "wrong_phase")  # picking
        self.assertFalse(self.me(player)["can_start_now"])

    async def test_all_present_counts_this_games_players(self):
        with mock.patch.object(game_core, "MAX_PLAYERS", 2):
            arrange(self.core, (0, 1))
            await self.start()
            ids = self.state()["pick_order"]
            self.assertEqual(len(ids), 2)
            await self.core.set_present(ids[:1])
            self.assertIsNone(self.state()["start_at_ms"])
            await self.core.set_present(ids)
            await self.clock.advance(5)
            self.assertEqual(self.state()["phase"], "picking")


class PauseTest(RulesBase):
    """수동 일시정지·재개: 남은 시간 보존, 정지 중 요청 거절, 판정 순서."""

    async def pause(self, user_id, game_id=None):
        return await self.core.activity_pause(user_id, game_id or self.state()["game_id"])

    async def resume(self, user_id, game_id=None):
        return await self.core.activity_resume(user_id, game_id or self.state()["game_id"])

    async def test_pause_resume_keeps_remaining_time_in_picking(self):
        await self.start_picking()
        ids = self.state()["pick_order"]
        await self.clock.advance(7)
        self.assertEqual(await self.pause(ids[3]), ("ok", "일시정지했습니다."))
        s = self.state()
        self.assertEqual(s["paused"], {"by": ids[3], "remaining_ms": 13000})
        self.assertIsNone(s["deadline_ms"])
        self.assertEqual(s["grace_ms"], 2000)
        self.assertEqual(s["turn_id"], f"{s['game_id']}:0")
        me = self.me(ids[0])
        self.assertEqual((me["can_pause"], me["can_resume"], me["can_pick"]), (False, True, False))
        self.assertFalse(self.me("999")["can_resume"])
        await self.clock.advance(100)
        self.assertEqual((self.state()["current_index"], self.state()["auto_assigned"]), (0, []))
        self.assertEqual(await self.resume(ids[5]), ("ok", "재개했습니다."))  # 참가자 누구나
        s = self.state()
        self.assertIsNone(s["paused"])
        self.assertEqual(s["deadline_ms"] - s["server_ms"], 13000)
        self.assertTrue(self.me(ids[0])["can_pause"])
        await self.clock.advance(14.9)
        self.assertEqual(self.state()["current_index"], 0)
        await self.clock.advance(0.1)  # 새 마감 13초 + 유예 2초
        self.assertEqual(self.state()["auto_assigned"], [ids[0]])

    async def test_old_turn_timer_is_invalid_after_resume(self):
        await self.start_picking()
        ids = self.state()["pick_order"]
        await self.clock.advance(5)
        await self.pause(ids[0])
        await self.clock.advance(10)
        await self.resume(ids[0])  # 새 마감은 지금부터 15초
        await self.clock.advance(7)  # 옛 마감+유예(시작 22초)가 지났다
        self.assertEqual(self.state()["auto_assigned"], [])
        await self.clock.advance(10)
        self.assertEqual(self.state()["auto_assigned"], [ids[0]])

    async def test_paused_rejects_pick_before_deadline_check(self):
        await self.start_picking()
        await self.pause(self.picker_id())
        self.assertEqual((await self.pick(received_at=self.clock() + 1000))[0], "paused")
        self.assertEqual(self.state()["selections"], {})

    async def test_pause_rejection_codes_in_order(self):
        self.assertEqual((await self.core.activity_pause("101", None))[0], "wrong_phase")  # none
        await self.start_picking()
        s = self.state()
        gid, player = s["game_id"], s["pick_order"][0]
        self.assertEqual((await self.pause(player, "g-old"))[0], "stale_game")
        self.assertEqual((await self.pause("999"))[0], "not_allowed")
        self.assertFalse(self.me("999")["can_pause"])
        self.assertEqual((await self.resume(player))[0], "not_paused")
        await self.clock.advance(20.5)  # 마감이 지나 유예 중
        self.assertEqual((await self.pause(player))[0], "timeout")
        await self.clock.advance(1.5)  # 자동 배정, 다음 차례
        self.assertEqual((await self.pause(player))[0], "ok")
        self.assertEqual((await self.pause(player))[0], "already_paused")
        self.assertEqual((await self.resume("999"))[0], "not_allowed")
        self.assertEqual((await self.resume(player, "g-old"))[0], "stale_game")
        await self.resume(player)
        for _ in range(5):
            await self.clock.advance(22)
        self.assertEqual(self.state()["phase"], "awaiting_result")
        self.assertEqual((await self.pause(player, gid))[0], "wrong_phase")
        self.assertEqual((await self.resume(player, gid))[0], "wrong_phase")
        self.assertFalse(self.me(player)["can_pause"])

    async def test_pause_freezes_start_countdown(self):
        await self.start()
        ids = self.state()["pick_order"]
        await self.enter_all()
        await self.clock.advance(2)
        await self.pause(ids[0])
        s = self.state()
        self.assertEqual((s["start_at_ms"], s["paused"]["remaining_ms"]), (None, 3000))
        self.assertFalse(self.me(ids[0])["can_start_now"])
        await self.clock.advance(100)
        self.assertEqual(self.state()["phase"], "starting")
        await self.resume(ids[1])
        s = self.state()
        self.assertEqual(s["start_at_ms"] - s["server_ms"], 3000)
        await self.clock.advance(3)
        self.assertEqual(self.state()["phase"], "picking")

    async def test_resume_cancels_countdown_if_someone_left_while_paused(self):
        await self.start()
        ids = self.state()["pick_order"]
        await self.enter_all()
        await self.pause(ids[0])
        await self.core.set_present(ids[1:])  # 정지 중에는 카운트다운을 건드리지 않는다
        self.assertEqual(self.state()["paused"]["remaining_ms"], 5000)
        await self.resume(ids[1])
        self.assertIsNone(self.state()["start_at_ms"])  # 전원이 아니라 입장 대기로
        await self.clock.advance(10)
        self.assertEqual(self.state()["phase"], "starting")

    async def test_pause_while_waiting_blocks_start(self):
        await self.start()
        ids = self.state()["pick_order"]
        await self.pause(ids[0])
        self.assertEqual(self.state()["paused"], {"by": ids[0], "remaining_ms": None})
        self.assertFalse(self.me(ids[0])["can_start_now"])
        self.assertEqual((await self.core.activity_start_now(ids[0], self.state()["game_id"]))[0], "paused")
        await self.enter_all()  # 정지 중에는 전원 입장해도 시작하지 않는다
        self.assertIsNone(self.state()["start_at_ms"])
        await self.resume(ids[2])
        s = self.state()
        self.assertEqual(s["start_at_ms"] - s["server_ms"], 5000)  # 재개하면 새 카운트다운

    async def test_race_pause_first_then_countdown_timer_does_nothing(self):
        await self.start()
        ids = self.state()["pick_order"]
        await self.enter_all()
        await self.core.lock.acquire()
        pause_task = asyncio.create_task(self.pause(ids[0]))
        await settle()
        await self.clock.advance(5)  # 카운트다운 타이머는 일시정지 뒤에 락을 얻는다
        self.core.lock.release()
        self.assertEqual((await pause_task)[0], "ok")
        await settle()
        self.assertEqual(self.state()["phase"], "starting")
        self.assertEqual(self.state()["paused"]["remaining_ms"], 0)
        await self.resume(ids[0])
        await self.clock.advance(0)
        self.assertEqual(self.state()["phase"], "picking")

    async def test_new_game_clears_pause(self):
        await self.start_picking()
        await self.pause(self.picker_id())
        async with self.core.lock:
            self.core.new_game(self.people, "activity")  # /게임시작
        self.assertIsNone(self.state()["paused"])


class ChampionPoolResetTest(RulesBase):
    """/챔피언리셋: 제외 목록을 비우면 다음 판 후보에 이전 챔피언이 다시 나올 수 있다."""

    async def test_reset_applies_from_next_game(self):
        await self.start_picking()
        await self.pick_all()
        first = self.state()["champions"]
        picked = set(self.state()["selections"].values())
        self.assertEqual(len(self.core.excluded), 6)
        async with self.core.lock:
            self.assertEqual(self.core.reset_champion_pool(), 6)
        self.assertEqual(self.core.excluded, set())
        self.assertEqual(self.state()["champions"], first)  # 떠 있는 판의 후보는 그대로다
        self.assertEqual((await self.start(game_id=self.state()["game_id"]))[0], "ok")
        again = {c["id"] for c in self.state()["champions"]}
        self.assertTrue(picked & again)  # 앞에서부터 뽑는 배치라 이전 판 챔피언이 다시 나온다

    async def test_without_reset_previous_picks_are_excluded(self):
        await self.start_picking()
        await self.pick_all()
        picked = set(self.state()["selections"].values())
        await self.start(game_id=self.state()["game_id"])
        self.assertFalse(picked & {c["id"] for c in self.state()["champions"]})


class EmbedModeTest(RulesBase):
    pick_mode = "embed"

    async def test_presence_does_not_touch_embed_game(self):
        async with self.core.lock:
            self.core.new_game(self.people, "embed")
        await self.core.set_present([str(m.id) for m in self.people])
        self.assertIsNone(self.core.start_at)
        self.assertIsNone(self.core._timer)
        self.assertEqual(self.state()["present"], [])

    async def test_embed_mode_is_always_none_and_cannot_start(self):
        code, _ = await self.start()
        self.assertEqual(code, "not_allowed")
        async with self.core.lock:
            self.core.new_game(self.people, "embed")  # /게임시작(embed)
        s = self.state()
        self.assertEqual((s["phase"], s["game_id"], s["players"]), ("none", None, []))
        me = self.me("101")
        self.assertFalse(any(me[k] for k in ("can_start", "can_pick", "can_report", "can_reverse")))
        self.assertEqual((await self.core.activity_pick("101", None, None, "Champ0", 0))[0], "wrong_phase")


class PickTest(RulesBase):

    async def test_rejection_codes_in_order(self):
        await self.start()
        s = self.state()
        self.assertEqual((await self.core.activity_pick("101", "g-old", None, "Champ0", 0))[0], "stale_game")
        self.assertEqual((await self.core.activity_pick("101", s["game_id"], None, "Champ0", 0))[0], "wrong_phase")
        await self.begin()
        s = self.state()
        picker = self.picker_id()
        other = next(p for p in s["pick_order"] if p != picker)
        cand = s["champions"][0]["id"]
        deadline_mono = self.core.deadline
        cases = [
            # (요청, 기대 코드) - 여러 조건에 걸리면 먼저 오는 코드가 나와야 한다
            (dict(game_id="g-old", user_id=other, turn_id="x", champion_id="Nope"), "stale_game"),
            (dict(user_id=other, turn_id="x", champion_id="Nope"), "stale_turn"),
            (dict(user_id=other, champion_id="Nope", received_at=deadline_mono + 10), "not_your_turn"),
            (dict(user_id=picker, champion_id="Nope", received_at=deadline_mono + 10), "timeout"),
            (dict(user_id=picker, champion_id="Nope"), "not_candidate"),
        ]
        for kwargs, expected in cases:
            with self.subTest(expected=expected):
                code, _ = await self.pick(**kwargs)
                self.assertEqual(code, expected)
        self.assertEqual(self.state()["selections"], {})
        code, message = await self.pick(user_id=picker, champion_id=cand)
        self.assertEqual(code, "ok")
        self.assertEqual(message, f"{s['champions'][0]['name']} 선택 완료!")
        after = self.state()
        self.assertEqual(after["selections"], {picker: cand})
        self.assertEqual(after["current_index"], 1)
        self.assertEqual(after["turn_id"], f"{after['game_id']}:1")
        # 다음 사람이 이미 뽑힌 챔피언을 고르면 champion_taken
        self.assertEqual((await self.pick(champion_id=cand))[0], "champion_taken")

    async def test_not_your_turn_message_names_picker(self):
        await self.start_picking()
        s = self.state()
        picker = self.picker_id()
        name = next(p["name"] for p in s["players"] if p["id"] == picker)
        other = next(p for p in s["pick_order"] if p != picker)
        code, message = await self.pick(user_id=other)
        self.assertEqual((code, message), ("not_your_turn", f"지금은 {name} 님의 차례입니다."))

    async def test_new_turn_gets_full_timeout(self):
        await self.start_picking()
        await self.clock.advance(12)
        await self.pick()
        s = self.state()
        self.assertEqual(s["deadline_ms"] - s["server_ms"], 20000)

    async def test_deadline_plus_grace_boundary(self):
        await self.start_picking()
        limit = self.core.deadline + 2
        self.assertEqual((await self.pick(received_at=limit + 0.001))[0], "timeout")
        self.assertEqual((await self.pick(received_at=limit - 0.001))[0], "ok")
        limit = self.core.deadline + 2
        self.assertEqual((await self.pick(received_at=limit))[0], "ok")  # 경계 시각은 인정한다

    async def test_auto_assign_after_deadline_plus_grace(self):
        await self.start_picking()
        s = self.state()
        first = self.picker_id()
        await self.clock.advance(21.9)
        self.assertEqual(self.state()["current_index"], 0)  # 유예 중에는 배정하지 않는다
        await self.clock.advance(0.1)
        after = self.state()
        self.assertEqual(after["current_index"], 1)
        self.assertEqual(after["auto_assigned"], [first])
        self.assertIn(after["selections"][first], [c["id"] for c in s["champions"]])
        self.assertEqual(after["deadline_ms"] - after["server_ms"], 20000)  # 다음 차례는 새 20초
        # 이미 자동 배정으로 끝난 차례에 늦게 온 픽은 되돌리지 않는다
        code, _ = await self.pick(user_id=first, turn_id=s["turn_id"], received_at=self.core.deadline - 30)
        self.assertEqual(code, "stale_turn")
        self.assertEqual(self.state()["selections"][first], after["selections"][first])
        self.assertIn(("board_changed",), self.effects.calls)

    async def test_race_timer_first_then_late_pick_confirms_once(self):
        await self.start_picking()
        s = self.state()
        first = self.picker_id()
        received = self.core.deadline + 1.9  # 유예 안에 도착했지만 락을 기다린다
        await self.core.lock.acquire()
        await self.clock.advance(22)  # 타이머가 먼저 락을 기다린다
        pick_task = asyncio.create_task(self.pick(user_id=first, turn_id=s["turn_id"], received_at=received))
        await settle()
        self.core.lock.release()
        code, _ = await pick_task
        self.assertEqual(code, "stale_turn")
        after = self.state()
        self.assertEqual(after["current_index"], 1)
        self.assertEqual(after["auto_assigned"], [first])
        self.assertEqual(len(after["selections"]), 1)

    async def test_race_pick_first_then_timer_does_nothing(self):
        await self.start_picking()
        s = self.state()
        first = self.picker_id()
        champ = s["champions"][3]["id"]
        await self.core.lock.acquire()
        pick_task = asyncio.create_task(
            self.pick(user_id=first, turn_id=s["turn_id"], champion_id=champ, received_at=self.core.deadline + 1.9)
        )
        await settle()
        await self.clock.advance(22)  # 타이머는 픽 뒤에 락을 얻는다
        self.core.lock.release()
        self.assertEqual((await pick_task)[0], "ok")
        await settle()
        after = self.state()
        self.assertEqual(after["selections"], {first: champ})
        self.assertEqual(after["auto_assigned"], [])
        self.assertEqual(after["current_index"], 1)

    async def test_all_picked_moves_to_awaiting_result(self):
        await self.start_picking()
        await self.pick_all()
        s = self.state()
        self.assertEqual(len(s["selections"]), 6)
        for key in ("deadline_ms", "grace_ms", "turn_id", "current_index", "start_at_ms"):
            self.assertIsNone(s[key], key)
        await self.clock.advance(100)
        self.assertEqual(self.state()["auto_assigned"], [])  # 남은 타이머가 없다

    async def test_full_auto_assign_game(self):
        await self.start_picking()
        for _ in range(6):
            await self.clock.advance(22)
        s = self.state()
        self.assertEqual(s["phase"], "awaiting_result")
        self.assertEqual(sorted(s["auto_assigned"]), sorted(s["pick_order"]))
        self.assertEqual(len(set(s["selections"].values())), 6)


class ResultTest(RulesBase):

    async def asyncSetUp(self):
        await super().asyncSetUp()
        await self.start_picking()
        self.gid = self.state()["game_id"]
        self.player = self.state()["players"][0]["id"]

    async def test_rejections_before_awaiting_result(self):
        self.assertEqual((await self.core.activity_result(self.player, "g-old", "team1"))[0], "stale_game")
        self.assertEqual((await self.core.activity_result(self.player, self.gid, "team1"))[0], "wrong_phase")

    async def test_record_flow(self):
        await self.pick_all()
        spectator = "999"
        self.assertEqual((await self.core.activity_result(spectator, self.gid, "team1"))[0], "not_allowed")
        self.assertEqual((await self.core.activity_result(self.player, self.gid, "team3"))[0], "bad_request")
        code, message = await self.core.activity_result(self.player, self.gid, "team2")
        self.assertEqual((code, message), ("ok", "TEAM 2 승리를 기록했습니다."))
        s = self.state()
        self.assertEqual(s["phase"], "completed")
        self.assertEqual(s["result"], {"winner": "team2", "recorded_ms": s["server_ms"], "corrected": None})
        self.assertEqual(s["round"], 87)
        for p in s["players"]:
            self.assertEqual(p["wins"], 1 if p["team"] == "team2" else 0)
        self.assertEqual(len(s["players"]), 6)  # 기록 뒤에도 팀 구성이 남는다
        self.assertEqual((await self.core.activity_result(self.player, self.gid, "team1"))[0], "already_recorded")
        self.assertEqual(self.core.round_counter, 88)
        await settle()
        self.assertIn(("result_recorded", 87, "team2"), self.effects.calls)
        # 판 기록에는 한국어 이름을 저장한다
        names = {c["name"] for c in CHAMPIONS}
        self.assertTrue(all(p["champ"] in names for p in self.store.games[0]["team1"]))

    async def test_save_failure_stays_awaiting_result(self):
        await self.pick_all()
        self.store.fail_save = True
        code, _ = await self.core.activity_result(self.player, self.gid, "team1")
        self.assertEqual(code, "record_failed")
        s = self.state()
        self.assertEqual(s["phase"], "awaiting_result")
        self.assertIsNone(s["result"])
        self.store.fail_save = False
        self.assertEqual((await self.core.activity_result(self.player, self.gid, "team1"))[0], "ok")


class ReverseTest(RulesBase):

    async def asyncSetUp(self):
        await super().asyncSetUp()
        await self.start_picking()
        await self.pick_all()
        self.gid = self.state()["game_id"]
        self.player = self.state()["players"][0]["id"]

    async def test_wrong_phase_before_result(self):
        code, _ = await self.core.activity_reverse(self.player, self.gid, "team1")
        self.assertEqual(code, "wrong_phase")

    async def test_reverse_flow_and_conflict(self):
        await self.core.activity_result(self.player, self.gid, "team1")
        self.assertEqual((await self.core.activity_reverse("999", self.gid, "team1"))[0], "not_allowed")
        self.assertEqual((await self.core.activity_reverse(self.player, "g-old", "team1"))[0], "stale_game")
        code, message = await self.core.activity_reverse(self.player, self.gid, "team1")
        self.assertEqual((code, message), ("ok", "ROUND 87 결과를 TEAM 2 승리로 바꿨습니다."))
        s = self.state()
        self.assertEqual(s["result"]["winner"], "team2")
        self.assertEqual(s["result"]["corrected"], {"from": "team1", "at_ms": s["server_ms"]})
        for p in s["players"]:
            self.assertEqual(p["wins"], 1 if p["team"] == "team2" else 0)
        self.assertEqual(self.store.games[0]["winner"], "team2")
        # 같은 화면을 보던 다른 사람이 늦게 누르면 conflict
        self.assertEqual((await self.core.activity_reverse(self.player, self.gid, "team1"))[0], "conflict")
        await settle()
        self.assertIn(("result_reversed", 87, "team1"), self.effects.calls)

    async def test_save_failure_restores_wins_and_history(self):
        await self.core.activity_result(self.player, self.gid, "team1")
        wins_before = dict(self.core.wins_data)
        self.store.fail_save = True
        code, _ = await self.core.activity_reverse(self.player, self.gid, "team1")
        self.assertEqual(code, "record_failed")
        self.assertEqual(self.core.wins_data, wins_before)
        self.assertEqual(self.store.games[0]["winner"], "team1")
        self.assertEqual(self.state()["result"]["winner"], "team1")

    async def test_game_without_history_cannot_reverse(self):
        from game_recorder import SeasonMismatchError

        self.store.record_error = SeasonMismatchError("라운드 회귀")
        await self.core.activity_result(self.player, self.gid, "team1")
        code, _ = await self.core.activity_reverse(self.player, self.gid, "team1")
        self.assertEqual(code, "record_failed")

    async def test_discord_reverse_updates_displayed_result(self):
        await self.core.activity_result(self.player, self.gid, "team1")
        record = self.store.find_game(87, False)
        async with self.core.lock:
            self.core.reverse_locked(record)  # 디스코드 /번복
        self.assertEqual(self.state()["result"]["winner"], "team2")


class PermissionTest(RulesBase):

    async def test_me_for_player_and_spectator(self):
        me = self.me("101")
        self.assertEqual(me, {
            "id": "101", "role": "spectator", "team": None, "can_start": True, "can_start_now": False,
            "can_pause": False, "can_resume": False,
            "can_pick": False, "can_advantage": False, "can_report": False, "can_reverse": False,
        })
        await self.start_picking()
        s = self.state()
        picker = self.picker_id()
        other = next(p for p in s["pick_order"] if p != picker)
        outsider = next(str(m.id) for m in self.people if str(m.id) not in s["pick_order"])
        picker_team = next(p["team"] for p in s["players"] if p["id"] == picker)
        self.assertEqual(self.me(picker), {
            "id": picker, "role": "player", "team": picker_team, "can_start": False, "can_start_now": False,
            "can_pause": True, "can_resume": False,
            "can_pick": True, "can_advantage": False, "can_report": False, "can_reverse": False,
        })
        self.assertFalse(self.me(other)["can_pick"])
        self.assertEqual(self.me(outsider)["role"], "spectator")
        self.assertFalse(self.me(outsider)["can_start"])  # picking 중에는 아무도 시작 못 한다
        await self.pick_all()
        self.assertTrue(self.me(other)["can_report"])
        self.assertTrue(self.me(other)["can_start"])  # 결과 없이 새 판
        self.assertFalse(self.me(outsider)["can_report"])
        await self.core.activity_result(other, s["game_id"], "team1")
        self.assertTrue(self.me(other)["can_reverse"])
        self.assertFalse(self.me(outsider)["can_reverse"])
        self.assertTrue(self.me(outsider)["can_start"])


class DevModeTest(RulesBase):
    dev_mode = True

    async def asyncSetUp(self):
        await super().asyncSetUp()
        # DEV_MODE는 wins_dev.json의 6명을 쓴다(길드 온라인 상태와 무관)
        self.dev_people = [Member(900 + i, f"가상{i}") for i in range(6)]
        self.effects.guild_members = {"guild-1": self.dev_people}

    async def test_fixed_auto_start_without_presence(self):
        await self.start(user_id="555")
        s = self.state()
        self.assertEqual(s["start_at_ms"] - s["server_ms"], 15000)  # 입장과 무관하게 고정 자동 시작
        self.assertEqual(s["present"], [])
        await self.core.set_present([])
        await self.clock.advance(15)
        self.assertEqual(self.state()["phase"], "picking")

    async def test_anyone_can_act_for_virtual_players(self):
        tester = "555"  # 이 판의 6명이 아닌 접속자
        code, _ = await self.start(user_id=tester)
        self.assertEqual(code, "ok")
        self.assertEqual({p["id"] for p in self.state()["players"]}, {str(m.id) for m in self.dev_people})
        await self.clock.advance(15)
        me = self.me(tester)
        self.assertEqual((me["role"], me["can_pick"], me["can_pause"]), ("spectator", True, True))
        gid = self.state()["game_id"]
        self.assertEqual((await self.core.activity_pause(tester, gid))[0], "ok")
        self.assertTrue(self.me(tester)["can_resume"])
        self.assertEqual((await self.core.activity_resume(tester, gid))[0], "ok")
        for _ in range(6):
            self.assertEqual((await self.pick(user_id=tester))[0], "ok")
        gid = self.state()["game_id"]
        self.assertTrue(self.me(tester)["can_report"])
        self.assertEqual((await self.core.activity_result(tester, gid, "team1"))[0], "ok")
        self.assertTrue(self.me(tester)["can_reverse"])
        self.assertEqual((await self.core.activity_reverse(tester, gid, "team1"))[0], "ok")


if __name__ == "__main__":
    unittest.main()
