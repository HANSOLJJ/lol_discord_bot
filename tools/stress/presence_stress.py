# 실제 로컬 서버의 입장과 타이머를 다중 웹소켓으로 흔들고 불변식을 검사한다.
import argparse
import asyncio
import collections
import json
import logging
import random
import sys
import time
import traceback
import warnings
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]  # 저장소 루트 (tools/stress/ 기준)
OUT = Path(__file__).resolve().parent / "out"  # 실행 결과 폴더 (git 추적 안 함)
sys.path.insert(0, str(ROOT))

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestServer
from activity_server import ActivityServer
from tests.test_activity_server import ActivityTestBase, CLIENT_ID, CLIENT_SECRET, DISCORD_USER, make_game
from tests.test_activity_rules import BAN_TEAM1, FORCE_TEAM2, NO_ADVANTAGE, FakeClock, arrange, settle
from tests.test_game_core import Member


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class NativeBase(ActivityTestBase):
    async def asyncSetUp(self):
        self.discord_requests = []
        self.token_status = self.me_status = 200
        self.me_body = dict(DISCORD_USER)
        fake = web.Application()
        fake.router.add_post("/oauth2/token", self._fake_token)
        fake.router.add_get("/users/@me", self._fake_me)
        self.fake_discord = TestServer(fake)
        await self.fake_discord.start_server()
        self.clock = FakeClock()
        self.people = [Member(900 + i, f"가상{i}") for i in range(6)]
        self.game, self.store = make_game(self.clock, self.dev_mode, self.pick_mode, self.people)
        self.server = ActivityServer(game=self.game, client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
                                     port=0, discord_api_base=str(self.fake_discord.make_url("")),
                                     heartbeat=self.heartbeat, clock=self.clock)
        await self.server.start()
        port = self.server._runner.addresses[0][1]
        self.client = aiohttp.ClientSession(base_url=f"http://127.0.0.1:{port}")

    async def asyncTearDown(self):
        await self.client.close()
        await self.server.close()
        await self.fake_discord.close()
        await self.game.close()


class Peer:
    def __init__(self, harness, uid, ws):
        self.h = harness
        self.uid = uid
        self.ws = ws
        self.ready = False
        self.active = True
        self.state = None
        self.pending = {}
        self.messages = []
        self.reader = asyncio.create_task(self.read())

    async def read(self):
        async for msg in self.ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                self.messages.append(data)
                if data["t"] == "state":
                    if self.state:
                        require(data["state_version"] >= self.state["state_version"], "state version regressed")
                    self.state = data
                elif data.get("id") in self.pending:
                    future = self.pending.pop(data["id"])
                    future.set_result(data)
            elif msg.type == aiohttp.WSMsgType.PING:
                self.h.stats["ignored_heartbeat_ping"] += 1
        self.active = False

    async def request(self, kind, **fields):
        request_id = fields.pop("id", self.h.next_id())
        future = asyncio.get_running_loop().create_future()
        self.pending[request_id] = future
        data = {"t": kind, "id": request_id, **fields}
        if kind not in ("ping", "sync"):
            data.setdefault("game_id", self.h.state()["game_id"])
        self.h.trace.append({"time": self.h.clock(), "user": self.uid, "send": data})
        await self.ws.send_json(data)
        reply = await asyncio.wait_for(future, 3)
        self.h.stats[f"reply_{reply.get('code', reply['t'])}"] += 1
        self.h.trace.append({"reply": reply})
        require(reply.get("code") != "server_error", f"server_error: {reply}")
        return reply

    async def enter(self, duplicate=False):
        self.h.trace.append({"time": self.h.clock(), "user": self.uid, "ready": True})
        await self.ws.send_json({"t": "ready"})
        if duplicate:
            await self.ws.send_json({"t": "ready", "id": "ignored-ready-id"})
        self.ready = True
        await self.request("ping", c=0)
        await settle()

    async def close(self):
        self.h.trace.append({"time": self.h.clock(), "user": self.uid, "close": True})
        self.active = False
        await self.ws.close()
        await self.reader


class Harness:
    def __init__(self, seed=0, dev=False, mode="activity", heartbeat=10, order=NO_ADVANTAGE, testserver=False):
        self.seed = seed
        self.rng = random.Random(seed)
        self.base = ActivityTestBase() if testserver else NativeBase()
        self.base.dev_mode = dev
        self.base.pick_mode = mode
        self.base.heartbeat = heartbeat
        self.order = order
        self.peers = []
        self.sessions = {}
        self.trace = []
        self.stats = collections.Counter()
        self.sequence = 0
        self.transitions = []
        self.last_phase = "none"
        self.prior_selections = {}

    async def setup(self):
        await self.base.asyncSetUp()
        self.game = self.base.game
        self.clock = self.base.clock
        arrange(self.game, self.order)
        self.game.rng.seed(self.seed)
        self.game.add_listener(self.changed)

    def changed(self):
        phase = self.state()["phase"]
        if phase != self.last_phase:
            self.transitions.append((self.last_phase, phase))
            self.last_phase = phase

    def next_id(self):
        self.sequence += 1
        return f"r{self.sequence}"

    def state(self):
        return self.game.snapshot()

    async def connect(self, uid, ready=True, autoping=True):
        uid = str(uid)
        if uid not in self.sessions:
            self.base.me_body["id"] = uid
            self.sessions[uid] = await self.base.get_session()
        ws = await self.base.client.ws_connect(
            "/pick-api/ws", params={"session": self.sessions[uid]}, autoping=autoping
        )
        peer = Peer(self, uid, ws)
        self.peers.append(peer)
        await peer.request("ping", c=0)
        require(peer.state is not None, "missing initial state")
        if ready:
            await peer.enter()
        self.stats["connections"] += 1
        return peer

    async def check(self):
        # sync를 보내 상태 누락을 가리지 않는다. 자연 broadcast만 수렴해야 한다.
        await settle()
        for attempt in range(100):
            if attempt:
                await asyncio.sleep(0.001)
            expected = {p.uid for p in self.peers if p.active and p.ready}
            s = self.state()
            players = {p["id"] for p in s["players"]}
            expected &= players
            active = [p for p in self.peers if p.active]
            version = self.base.server._state_version
            if set(s["present"]) == expected and all(p.state and p.state["state_version"] == version for p in active):
                break
        require(set(s["present"]) == expected, f"presence expected={expected} actual={s['present']}")
        normalized = lambda d: {k: v for k, v in d.items() if k not in ("me", "server_ms")}
        canonical = {"t": "state", "protocol_version": 4, "server_epoch": self.base.server.server_epoch,
                     "state_version": version, **s}
        for p in active:
            require(normalized(p.state) == normalized(canonical), f"divergent state user={p.uid} actual={p.state} expected={canonical}")
            me = p.state["me"]
            allowed = p.uid in players or self.base.dev_mode
            phase_ok = s["phase"] in ("starting", "advantage", "picking")
            require(me["can_pause"] == (allowed and phase_ok and s["paused"] is None), "can_pause mismatch")
            require(me["can_resume"] == (allowed and phase_ok and s["paused"] is not None), "can_resume mismatch")
            require(me["can_start_now"] == (allowed and s["phase"] == "starting" and s["paused"] is None and s["start_at_ms"] is None), "can_start_now mismatch")
        require(len(s["present"]) == len(set(s["present"])), "duplicate presence")
        require(len(s["auto_assigned"]) == len(set(s["auto_assigned"])), "duplicate auto assignment")
        require(set(s["auto_assigned"]) <= set(s["selections"]), "auto assignment missing selection")
        require(len(s["selections"].values()) == len(set(s["selections"].values())), "champion assigned twice")
        require(all(s["selections"].get(k) == v for k, v in self.prior_selections.items()), "confirmed selection changed")
        self.prior_selections = dict(s["selections"])
        if s["phase"] == "picking":
            require(s["current_index"] == len(s["selections"]), "turn index skipped or duplicated")
        if s["paused"]:
            require(s["deadline_ms"] is None and s["start_at_ms"] is None, "paused clock still armed")
        if len(s["selections"]) == 6:
            require(s["phase"] == "awaiting_result", "six selections did not finish")
        require(sum(a == "starting" and b in ("advantage", "picking") for a, b in self.transitions) <= 1, "game began twice")
        require(sum(c[0] == "game_started" for c in self.game.effects.calls) <= 1, "start effect ran twice")
        adv = s["advantage"]
        if adv and adv["status"] == "chosen":
            chosen = adv["champion_id"]
            if adv["kind"] == "ban":
                require(chosen not in s["selections"].values(), "banned champion selected")
            else:
                owners = [k for k, v in s["selections"].items() if v == chosen]
                require(all(next(p["team"] for p in s["players"] if p["id"] == uid) != adv["team"] for uid in owners), "forced champion wrong team")
                if s["phase"] == "awaiting_result":
                    require(len(owners) == 1, "forced champion not selected")
        self.stats["checkpoints"] += 1

    async def advance(self, seconds):
        before = self.state()
        self.trace.append({"advance": seconds, "time": self.clock()})
        await self.clock.advance(seconds)
        await self.check()
        if before["paused"]:
            after = self.state()
            require(after["paused"] == before["paused"], "paused remaining time decreased")
            require(after["phase"] == before["phase"] and after["selections"] == before["selections"], "timer fired while paused")
            self.stats["frozen_clock_checks"] += 1

    async def request(self, peer, kind, expected=None, **fields):
        before = self.state()
        reply = await peer.request(kind, **fields)
        if expected is not None:
            require(reply["code"] == expected, f"{kind}: expected={expected}, actual={reply}")
        await self.check()
        after = self.state()
        if reply["code"] == "ok" and kind == "resume" and before["paused"]["remaining_ms"] is not None:
            deadline = after["start_at_ms"] if after["phase"] == "starting" else after["deadline_ms"]
            if after["phase"] != before["phase"]:
                require(before["phase"] == "starting" and before["paused"]["remaining_ms"] == 0,
                        "resume unexpectedly changed phase")
            elif deadline is not None:
                require(abs(deadline - after["server_ms"] - before["paused"]["remaining_ms"]) <= 1, "resume lost remaining time")
                self.stats["restored_clock_checks"] += 1
        return reply

    def predict_control(self, peer, kind, stale=False):
        s = self.state()
        if stale:
            return "stale_game"
        if s["phase"] not in (("starting",) if kind == "start_now" else ("starting", "advantage", "picking")):
            return "wrong_phase"
        if not self.base.dev_mode and peer.uid not in {p["id"] for p in s["players"]}:
            return "not_allowed"
        if kind == "resume":
            return "ok" if s["paused"] else "not_paused"
        if s["paused"]:
            return "already_paused" if kind == "pause" else "paused"
        if kind == "start_now":
            return "wrong_phase" if s["start_at_ms"] is not None else "ok"
        if s["phase"] != "starting" and self.game.deadline <= self.clock():
            return "timeout"
        return "ok"

    async def bootstrap(self, count=6, ready=True):
        players = [await self.connect(900 + i, ready=ready) for i in range(count)]
        spectators = [await self.connect(990 + i) for i in range(1 + self.seed % 2)]
        await self.request(players[0], "start", "ok", guild_id="guild-1")
        return players, spectators

    async def finish(self, auto=True):
        s = self.state()
        actor = next((p for p in self.peers if p.active and p.uid == "900"), None) or await self.connect(900)
        if s["paused"]:
            await self.request(actor, "resume", "ok")
        if self.state()["phase"] == "starting":
            if self.state()["start_at_ms"] is None:
                await self.request(actor, "start_now", "ok")
            await self.advance(5.01)
        if self.state()["phase"] == "advantage":
            await self.advance(22.01)
        for _ in range(6):
            s = self.state()
            if s["phase"] == "awaiting_result":
                break
            if auto:
                await self.advance(22.01)
            else:
                uid = s["pick_order"][s["current_index"]]
                peer = next((p for p in self.peers if p.active and p.uid == uid), None) or await self.connect(uid)
                free = next(c["id"] for c in s["champions"] if c["id"] not in s["selections"].values())
                await self.request(peer, "pick", "ok", turn_id=s["turn_id"], champion_id=free)
        require(self.state()["phase"] == "awaiting_result", "game failed to finish")
        require(len(self.state()["selections"]) == 6, "not six picks")
        self.stats["completed_games"] += 1
        await self.advance(100)

    async def close(self):
        for p in self.peers:
            if not p.ws.closed:
                await p.close()
        await self.base.asyncTearDown()
        for p in self.peers:
            await p.reader


async def presence_case(h):
    players, spectators = await h.bootstrap(ready=False)
    for p in players[:5]:
        await p.enter(duplicate=True)
        await h.check()
    require(h.state()["start_at_ms"] is None, "spectator counted as sixth player")
    spare = await h.connect(900, ready=False)
    await spare.close()
    await h.check()
    await players[5].enter()
    await h.check()
    for i in range(12):
        await h.advance(h.rng.choice([0, 0.001, 2, 4.999]))
        index = h.rng.randrange(6)
        duplicate = await h.connect(players[index].uid)
        await players[index].close()
        await h.check()
        require(h.state()["start_at_ms"] is not None, "partial close cancelled countdown")
        await duplicate.close()
        await h.check()
        require(h.state()["start_at_ms"] is None, "last close failed to cancel countdown")
        await h.advance(6)
        require(h.state()["phase"] == "starting", "cancelled countdown fired")
        players[index] = await h.connect(duplicate.uid)
        await h.check()
        require(h.state()["start_at_ms"] - h.state()["server_ms"] == 5000, "reentry did not restart full countdown")
    await h.finish(auto=False)


async def pause_case(h):
    players, spectators = await h.bootstrap(2)
    a, b = players
    await h.request(a, "pause", "ok")
    require(h.state()["paused"]["remaining_ms"] is None, "waiting pause should have null remaining")
    await h.advance(90)
    await h.request(a, "start_now", "paused")
    await h.request(b, "pause", "already_paused")
    for kind in ("pause", "resume", "start_now"):
        await h.request(spectators[0], kind, "not_allowed")
        await h.request(a, kind, "stale_game", game_id="g-old")
    for i in range(2, 6):
        players.append(await h.connect(900 + i))
    await h.request(b, "resume", "ok")
    require(h.state()["start_at_ms"] - h.state()["server_ms"] == 5000, "all arrived during pause did not start countdown")
    await h.advance(4.999)
    await h.request(a, "pause", "ok")
    await h.advance(30)
    replies = await asyncio.gather(a.request("resume"), b.request("resume"))
    require(sorted(r["code"] for r in replies) == ["not_paused", "ok"], "simultaneous resume not serialized")
    await h.check()
    await h.advance(0.002)
    for _ in range(15):
        await h.request(a, "pause", "ok")
        await h.advance(h.rng.choice([0.01, 25, 120]))
        s = h.state()
        await h.request(a, "pick", "paused", turn_id=s["turn_id"], champion_id=s["champions"][0]["id"])
        await h.request(b, "resume", "ok")
    await h.advance(19.999)
    await h.request(a, "pause", "ok")
    require(h.state()["paused"]["remaining_ms"] <= 1, "not deadline boundary")
    await h.advance(100)
    await h.request(b, "resume", "ok")
    await h.advance(0.002)
    await h.request(a, "pause", "timeout")
    await h.advance(1.998)
    await h.finish()


async def start_race_case(h):
    players, _ = await h.bootstrap(ready=False)
    for p in players[:5]:
        await p.enter()
    await h.check()
    async def final_ready():
        await asyncio.sleep(h.rng.random() / 1000)
        await players[5].enter()
    async def force():
        await asyncio.sleep(h.rng.random() / 1000)
        return await players[0].request("start_now")
    _, reply = await asyncio.gather(final_ready(), force())
    require(reply["code"] in ("ok", "wrong_phase"), "start race unexpected reply")
    await h.check()
    await players[5].close()
    await h.check()
    require((h.state()["start_at_ms"] is not None) == (reply["code"] == "ok"), "forced/unforced departure wrong")
    if reply["code"] == "wrong_phase":
        await h.request(players[0], "start_now", "ok")
    await players[1].close()
    await h.check()
    require(h.state()["start_at_ms"] is not None, "forced countdown cancelled")
    await h.finish()


async def advantage_case(h):
    players, spectators = await h.bootstrap()
    await h.advance(5)
    require(h.state()["phase"] == "advantage", "no advantage phase")
    adv = h.state()["advantage"]
    actor = next(p for p in players if next(m["team"] for m in h.state()["players"] if m["id"] == p.uid) == adv["team"])
    await h.advance(19.999)
    await h.request(actor, "pause", "ok")
    await h.advance(60)
    champion = h.state()["champions"][0]["id"]
    await h.request(actor, "advantage", "paused", champion_id=champion)
    await h.request(actor, "advantage", "stale_game", game_id="g-old", champion_id=champion)
    await h.request(spectators[0], "resume", "not_allowed")
    await h.request(players[0], "resume", "ok")
    if h.seed % 2:
        await h.advance(0.002)
        await h.request(actor, "pause", "timeout")
        await h.advance(2.01)
        require(h.state()["advantage"]["status"] == "skipped", "advantage timeout failed")
    else:
        await h.request(actor, "advantage", "ok", champion_id=champion)
        await h.request(players[0], "pause", "ok")
        await h.advance(60)
        await h.request(players[1], "resume", "ok")
        require(h.state()["advantage"]["champion_id"] == champion, "advantage lost across pause")
    await h.finish()


async def heartbeat_case(h):
    players, _ = await h.bootstrap(5)
    dead = await h.connect(905, autoping=False)
    survivor = await h.connect(905) if h.seed == 1 else None
    await h.check()
    require(h.state()["start_at_ms"] is not None, "heartbeat case countdown missing")
    started = time.perf_counter()
    await asyncio.wait_for(dead.reader, max(3, h.base.heartbeat * 2 + 1))
    h.stats["heartbeat_disconnect_ms"] = round((time.perf_counter() - started) * 1000)
    await h.check()
    if survivor:
        require("905" in h.state()["present"], "one dead socket removed healthy duplicate")
        require(h.state()["start_at_ms"] is not None, "dead duplicate cancelled countdown")
        await survivor.close()
        await h.check()
    require("905" not in h.state()["present"], "heartbeat did not remove presence")
    require(h.state()["start_at_ms"] is None, "heartbeat did not cancel countdown")
    require(all(p.active for p in players), "healthy heartbeat peer disconnected")
    await h.connect(905)
    await h.check()
    await h.finish()


async def timer_race_case(h):
    players, _ = await h.bootstrap()
    phase = "starting" if h.seed < 2 else "picking"
    if phase == "picking":
        await h.advance(5)
    await h.game.lock.acquire()
    task = None
    try:
        if h.seed % 2 == 0:
            task = asyncio.create_task(players[0].request("pause"))
            await settle()
            await players[0].request("ping", c=0)
            await settle()
        await h.clock.advance(5 if phase == "starting" else 22)
        if task is None:
            task = asyncio.create_task(players[0].request("pause"))
            await settle()
            await players[0].request("ping", c=0)
            await settle()
    finally:
        h.game.lock.release()
    reply = await task
    await h.check()
    s = h.state()
    if phase == "starting":
        require(reply["code"] == "ok", "countdown race pause rejected")
        require(s["phase"] == ("starting" if h.seed % 2 == 0 else "picking"), "countdown lock order wrong")
    elif h.seed % 2 == 0:
        require(reply["code"] == "timeout", "expired old turn pause accepted")
        require(len(s["selections"]) == 1, "expiry race assigned wrong count")
    else:
        require(reply["code"] == "ok" and s["paused"] is not None, "next turn pause failed")
        require(len(s["selections"]) == 1, "expiry race assigned wrong count")
    await h.finish()


async def pending_presence_case(h):
    players, _ = await h.bootstrap(ready=False)
    await h.game.lock.acquire()
    closes = []
    try:
        for p in players:
            await p.ws.send_json({"t": "ready"})
            p.ready = True
            await p.request("ping", c=0)
        await settle()
        for p in players[::2]:
            closes.append(asyncio.create_task(p.close()))
        await asyncio.sleep(0.01)
    finally:
        h.game.lock.release()
    await asyncio.gather(*closes)
    await h.check()
    require(set(h.state()["present"]) == {"901", "903", "905"}, "queued ready/close presence stale")
    require(h.state()["start_at_ms"] is None, "queued departure left countdown armed")
    await h.advance(6)
    await h.finish()


async def mode_case(h):
    if h.base.pick_mode == "embed":
        p = await h.connect(900)
        await h.connect(901)
        await h.connect(990)
        async with h.game.lock:
            require(h.game.new_game(h.base.people, "embed").ok, "embed creation failed")
        await h.check()
        before = (h.game.game_started, h.game.current_pick_index, h.game.start_at, h.game.deadline)
        await h.request(p, "start", "not_allowed", guild_id="guild-1")
        for kind in ("pause", "resume", "start_now"):
            await h.request(p, kind, "wrong_phase")
        await h.advance(30)
        require(before == (h.game.game_started, h.game.current_pick_index, h.game.start_at, h.game.deadline), "activity mutated embed")
        require(h.state()["phase"] == "none", "embed leaked to activity")
    else:
        h.game.config["dev_auto_start_seconds"] = 0 if h.seed == 0 else 15
        tester = await h.connect(990)
        await h.connect(991)
        await h.request(tester, "start", "ok", guild_id="guild-1")
        if h.seed:
            require(h.state()["phase"] == "starting", "dev delay lost")
            await h.request(tester, "pause", "ok")
            await h.advance(50)
            await h.request(tester, "resume", "ok")
            await h.advance(15)
        else:
            await h.advance(0)
        require(h.state()["phase"] == "picking", "dev zero start failed")
        require(h.state()["present"] == [], "virtual presence not empty")
        await h.request(tester, "pause", "ok")
        await h.advance(100)
        await h.request(tester, "resume", "ok")
        for _ in range(6):
            s = h.state()
            free = next(c["id"] for c in s["champions"] if c["id"] not in s["selections"].values())
            await h.request(tester, "pick", "ok", turn_id=s["turn_id"], champion_id=free)
        require(h.state()["phase"] == "awaiting_result", "dev picks did not finish")
        h.stats["completed_games"] += 1


async def random_case(h):
    players, spectators = await h.bootstrap(2 + h.seed % 5, ready=h.seed % 3 != 0)
    for step in range(70):
        active = [p for p in h.peers if p.active]
        operation = h.rng.randrange(8)
        h.stats[f"random_op_{operation}"] += 1
        if operation == 0 and len(active) < 13:
            await h.connect(h.rng.choice(list(range(900, 906)) + [990, 991]), ready=h.rng.choice([True, False]))
        elif operation == 1 and len(active) > 2:
            await h.rng.choice(active).close()
        elif operation == 2:
            await h.rng.choice(active).enter(duplicate=True)
        elif operation in (3, 4, 5):
            kind = ("pause", "resume", "start_now")[operation - 3]
            p = h.rng.choice(active)
            stale = h.rng.random() < 0.15
            expected = h.predict_control(p, kind, stale)
            await h.request(p, kind, expected, **({"game_id": "g-old"} if stale else {}))
        elif operation == 6:
            await h.advance(h.rng.choice([0, 0.001, 0.1, 1.999, 4.999, 5, 19.999, 20, 21.999, 22.001, 40]))
        else:
            s = h.state()
            if s["phase"] == "picking" and not s["paused"]:
                uid = s["pick_order"][s["current_index"]]
                p = next((p for p in active if p.uid == uid), None)
                if p:
                    # 어드밴티지는 random 경로에서 시간 초과로 넘긴다.
                    free = next(c["id"] for c in s["champions"] if c["id"] not in s["selections"].values())
                    await h.request(p, "pick", "ok", turn_id=s["turn_id"], champion_id=free)
        await h.check()
    await h.finish()


async def run_case(name, func, **kwargs):
    h = Harness(**kwargs)
    started = time.perf_counter()
    loop = asyncio.get_running_loop()
    errors = []
    previous = loop.get_exception_handler()
    loop.set_exception_handler(lambda loop, context: errors.append(str(context)))
    result = {"case": name, "seed": h.seed}
    tasks_before = asyncio.all_tasks()
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            await h.setup()
            await func(h)
            result["status"] = "passed"
    except Exception:
        result.update(status="failed", traceback=traceback.format_exc(), state=h.state() if hasattr(h, "game") else None)
    finally:
        try:
            await h.close()
        except Exception:
            result.update(status="failed", cleanup_traceback=traceback.format_exc())
        await settle()
        loop.set_exception_handler(previous)
    leaked = [str(task) for task in asyncio.all_tasks() - tasks_before if not task.done()]
    result.update(seconds=round(time.perf_counter() - started, 4), stats=dict(h.stats), transitions=h.transitions,
                  loop_errors=errors, warnings=[str(w.message) for w in caught], leaked_tasks=leaked)
    if errors or result["warnings"] or leaked:
        result["status"] = "failed"
    if result["status"] != "passed":
        result["trace"] = h.trace
    for task in asyncio.all_tasks() - tasks_before:
        if not task.done():
            task.cancel()
    await asyncio.gather(*(asyncio.all_tasks() - tasks_before), return_exceptions=True)
    return result


async def main(args):
    started = time.perf_counter()
    cases = []
    if not args.random_only:
        cases += [("presence", presence_case, {"seed": s}) for s in range(3)]
        cases += [("pause", pause_case, {"seed": s}) for s in range(3)]
        cases += [("start_race", start_race_case, {"seed": s}) for s in range(20)]
        cases += [(f"advantage_{kind}", advantage_case, {"seed": s, "order": order}) for kind, order in [("ban", BAN_TEAM1), ("force", FORCE_TEAM2)] for s in range(4)]
        cases += [("heartbeat", heartbeat_case, {"seed": s, "heartbeat": 0.1}) for s in range(3)]
        cases += [("heartbeat_default", heartbeat_case, {"heartbeat": 10})]
        cases += [("timer_race", timer_race_case, {"seed": s}) for s in range(4)]
        cases += [("pending_presence", pending_presence_case, {})]
        cases += [("embed", mode_case, {"mode": "embed"}), ("dev_zero", mode_case, {"dev": True}), ("dev_delayed", mode_case, {"dev": True, "seed": 1})]
    cases += [("random", random_case, {"seed": s, "order": [NO_ADVANTAGE, BAN_TEAM1, FORCE_TEAM2][s % 3]}) for s in range(args.start_seed, args.start_seed + args.seeds)]
    if args.case:
        cases = [c for c in cases if c[0] == args.case]
    results = []
    OUT.mkdir(exist_ok=True)
    output = OUT / args.output
    with output.open("w", encoding="utf-8") as out:
        for name, func, kwargs in cases:
            result = await run_case(name, func, testserver=args.testserver, **kwargs)
            results.append(result)
            out.write(json.dumps(result, ensure_ascii=False) + "\n")
            out.flush()
            if result["status"] != "passed" or len(results) % 10 == 0:
                print(f"{len(results)}/{len(cases)} {name} seed={result['seed']} {result['status']}", flush=True)
    summary = {"python": sys.version, "aiohttp": aiohttp.__version__, "server": "TestServer" if args.testserver else "ActivityServer.start",
               "cases": len(results),
               "passed": sum(r["status"] == "passed" for r in results), "seconds": round(time.perf_counter() - started, 3),
               "stats": dict(sum((collections.Counter(r["stats"]) for r in results), collections.Counter()))}
    output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=True), flush=True)
    return summary["passed"] == summary["cases"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=200)
    parser.add_argument("--start-seed", type=int, default=0)
    parser.add_argument("--case")
    parser.add_argument("--random-only", action="store_true")
    parser.add_argument("--testserver", action="store_true")
    parser.add_argument("--output", default="results.jsonl")
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    logging.basicConfig(filename=str(OUT / "server.log"), level=logging.WARNING, encoding="utf-8")
    sys.exit(not asyncio.run(main(args)))
