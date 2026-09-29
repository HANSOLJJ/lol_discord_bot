##
# @file test_activity_server.py
# @brief activity_server의 토큰 교환·세션·WebSocket 규격(docs/ACTIVITY_PROTOCOL.md, protocol_version 4) 테스트.
# @details 가짜 Discord API를 aiohttp 테스트 서버로 띄워 discord_api_base로 주입한다. 게임은 game_core.GameCore에
#          가짜 저장소·가짜 시계를 넣어 쓴다. 실제 Discord나 봇(got_champe)은 쓰지 않는다.
#          실행: uv run python -m unittest discover -s tests -t . -v
import asyncio
import json
import time
import unittest

import aiohttp
from aiohttp import WSMsgType, web
from aiohttp.test_utils import TestClient, TestServer

import activity_server
from activity_server import ActivityServer, _Connection
from game_core import GameCore
from tests.test_activity_rules import BAN_TEAM1, FakeClock, FakeEffects, arrange
from tests.test_game_core import CHAMPIONS, FakeStore, Member

CLIENT_ID = "test-client-id"
CLIENT_SECRET = "test-client-secret-value"
GOOD_CODE = "good-oauth-code"
ACCESS_TOKEN = "discord-access-token-value"
DISCORD_USER = {
    "id": "365414320332472332",
    "username": "hansol",
    "global_name": "정한솔",
    "avatar": "a1b2c3",
    "discriminator": "0",  # 규격에 없는 필드는 응답에 넣지 않는다
}
RECEIVE_TIMEOUT = 5  # 메시지 하나를 기다리는 최대 시간(초)


##
# @brief 테스트용 GameCore를 만든다(가짜 저장소·시계, 길드 "guild-1"에 가상 6명).
# @param clock FakeClock.
# @param dev_mode DEV_MODE 여부.
# @param pick_mode 이 프로세스의 픽 방식.
# @param people 길드 온라인 멤버.
# @return (GameCore, FakeStore).
def make_game(clock, dev_mode, pick_mode, people):
    store = FakeStore()
    game = GameCore(
        dev_mode=dev_mode,
        save_wins=store.save_wins,
        record_game=store.record_game,
        find_game=store.find_game,
        set_game_winner=store.set_game_winner,
        get_season=store.get_season,
        clock=clock,
        wall_ms=clock.wall_ms,
        sleep=clock.sleep,
    )
    game.config = {
        "pick_timeout": 20,
        "auto_start_seconds": 15,
        "pick_grace_seconds": 2,
        "champion_count": 8,
        ("dev_pick_mode" if dev_mode else "pick_mode"): pick_mode,
    }
    game.champion_list = list(CHAMPIONS)
    game.ddragon_version = "15.19.1"
    game.wins_data = {"total_rounds": 86}
    game.round_counter = 87
    game.effects = FakeEffects({"guild-1": people})
    arrange(game)  # 이점이 없는 배치. 어드밴티지 왕복 테스트는 다시 arrange한다
    return game, store


##
# @brief 가짜 Discord API와 액티비티 서버를 띄우는 공통 테스트 기반.
class ActivityTestBase(unittest.IsolatedAsyncioTestCase):
    dev_mode = True
    pick_mode = "activity"
    session_ttl = activity_server.SESSION_TTL_SECONDS
    heartbeat = activity_server.HEARTBEAT_SECONDS

    async def asyncSetUp(self):
        self.discord_requests = []  # 가짜 Discord가 받은 (경로, 본문 또는 헤더)
        self.token_status = 200
        self.me_status = 200
        self.me_body = dict(DISCORD_USER)

        fake = web.Application()
        fake.router.add_post("/oauth2/token", self._fake_token)
        fake.router.add_get("/users/@me", self._fake_me)
        self.fake_discord = TestServer(fake)
        await self.fake_discord.start_server()

        self.clock = FakeClock()
        self.people = [Member(900 + i, f"가상{i}") for i in range(6)]
        self.game, self.store = make_game(self.clock, self.dev_mode, self.pick_mode, self.people)
        self.server = ActivityServer(
            game=self.game,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            discord_api_base=str(self.fake_discord.make_url("")),
            session_ttl=self.session_ttl,
            heartbeat=self.heartbeat,
            clock=self.clock,
        )
        self.client = TestClient(TestServer(self.server.app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        await self.fake_discord.close()
        await self.game.close()

    async def _fake_token(self, request):
        form = dict(await request.post())
        self.discord_requests.append(("token", form))
        if self.token_status != 200:
            return web.json_response({"error": "invalid_grant"}, status=self.token_status)
        if form.get("code") != GOOD_CODE:
            return web.json_response({"error": "invalid_grant"}, status=400)
        return web.json_response({"access_token": ACCESS_TOKEN, "token_type": "Bearer"})

    async def _fake_me(self, request):
        self.discord_requests.append(("me", request.headers.get("Authorization")))
        if self.me_status != 200:
            return web.json_response({"message": "401: Unauthorized"}, status=self.me_status)
        return web.json_response(self.me_body)

    async def get_session(self):
        resp = await self.client.post("/pick-api/token", json={"code": GOOD_CODE})
        self.assertEqual(resp.status, 200)
        return (await resp.json())["session"]

    async def connect(self, session=None):
        if session is None:
            session = await self.get_session()
        return await self.client.ws_connect("/pick-api/ws", params={"session": session})

    async def connect_ready(self):
        """연결하고 hello·state를 받은 뒤 소켓을 돌려준다."""
        ws = await self.connect()
        await self.recv(ws)
        await self.recv(ws)
        return ws

    async def recv(self, ws):
        msg = await asyncio.wait_for(ws.receive(), RECEIVE_TIMEOUT)
        self.assertEqual(msg.type, WSMsgType.TEXT, f"텍스트 메시지 대신 {msg.type} {msg.data}")
        return json.loads(msg.data)

    async def recv_close_code(self, ws):
        """다음 메시지가 종료 프레임이라고 보고 종료 코드를 돌려준다."""
        msg = await asyncio.wait_for(ws.receive(), RECEIVE_TIMEOUT)
        self.assertEqual(msg.type, WSMsgType.CLOSE, f"종료 대신 {msg.type} {msg.data}")
        return msg.data


class TokenEndpointTest(ActivityTestBase):

    async def test_success(self):
        before = time.time() * 1000
        resp = await self.client.post("/pick-api/token", json={"code": GOOD_CODE})
        self.assertEqual(resp.status, 200)
        body = await resp.json()
        self.assertEqual(body["access_token"], ACCESS_TOKEN)
        self.assertGreaterEqual(len(body["session"]), 43)  # 32바이트 URL-safe
        self.assertAlmostEqual(body["session_expires_ms"], before + 3600 * 1000, delta=5000)
        self.assertEqual(
            body["user"],
            {"id": "365414320332472332", "username": "hansol", "global_name": "정한솔", "avatar": "a1b2c3"},
        )
        token_form = self.discord_requests[0][1]
        self.assertEqual(
            token_form,
            {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": GOOD_CODE,
            },
        )
        self.assertEqual(self.discord_requests[1], ("me", f"Bearer {ACCESS_TOKEN}"))

    async def test_null_global_name_and_avatar(self):
        self.me_body.update(global_name=None, avatar=None)
        resp = await self.client.post("/pick-api/token", json={"code": GOOD_CODE})
        user = (await resp.json())["user"]
        self.assertIsNone(user["global_name"])
        self.assertIsNone(user["avatar"])

    async def test_discord_token_failure_is_401(self):
        self.token_status = 400
        resp = await self.client.post("/pick-api/token", json={"code": GOOD_CODE})
        self.assertEqual(resp.status, 401)
        self.assertEqual(await resp.json(), {"error": "oauth_failed"})

    async def test_discord_me_failure_is_401(self):
        self.me_status = 401
        resp = await self.client.post("/pick-api/token", json={"code": GOOD_CODE})
        self.assertEqual(resp.status, 401)
        self.assertEqual(await resp.json(), {"error": "oauth_failed"})

    async def test_discord_unreachable_is_401(self):
        await self.fake_discord.close()
        resp = await self.client.post("/pick-api/token", json={"code": GOOD_CODE})
        self.assertEqual(resp.status, 401)
        self.assertEqual(await resp.json(), {"error": "oauth_failed"})

    async def test_bad_bodies_are_400(self):
        bad_bodies = [
            b"not json",
            b"[]",
            b"{}",
            json.dumps({"code": 123}).encode(),
            json.dumps({"code": ""}).encode(),
            json.dumps({"code": "x" * 513}).encode(),
            json.dumps({"code": GOOD_CODE, "pad": "x" * 5000}).encode(),  # 4KB 초과
        ]
        for body in bad_bodies:
            with self.subTest(body=body[:30]):
                resp = await self.client.post(
                    "/pick-api/token", data=body, headers={"Content-Type": "application/json"}
                )
                self.assertEqual(resp.status, 400)
                self.assertEqual(await resp.json(), {"error": "bad_request"})
        self.assertEqual(self.discord_requests, [])  # Discord까지 가지 않는다

    async def test_code_of_512_chars_is_accepted_format(self):
        resp = await self.client.post("/pick-api/token", json={"code": "x" * 512})
        self.assertEqual(resp.status, 401)  # 형식은 통과하고 가짜 Discord가 거절한다

    async def test_rate_limited_is_429(self):
        for _ in range(activity_server.TOKEN_RATE_LIMIT):
            resp = await self.client.post("/pick-api/token", data=b"x")
            self.assertEqual(resp.status, 400)
        resp = await self.client.post("/pick-api/token", json={"code": GOOD_CODE})
        self.assertEqual(resp.status, 429)
        self.assertEqual(await resp.json(), {"error": "rate_limited"})


class WebSocketAuthTest(ActivityTestBase):

    async def test_missing_session_closes_4401(self):
        ws = await self.client.ws_connect("/pick-api/ws")
        self.assertEqual(await self.recv_close_code(ws), 4401)

    async def test_wrong_session_closes_4401(self):
        await self.get_session()
        ws = await self.connect("not-a-real-session")
        self.assertEqual(await self.recv_close_code(ws), 4401)


class ExpiredSessionTest(ActivityTestBase):
    session_ttl = 0.3

    async def test_expired_session_closes_4401(self):
        session = await self.get_session()
        await asyncio.sleep(0.4)
        ws = await self.connect(session)
        self.assertEqual(await self.recv_close_code(ws), 4401)

    async def test_session_expiring_while_connected_closes_4401(self):
        ws = await self.connect()
        self.assertEqual((await self.recv(ws))["t"], "hello")
        self.assertEqual((await self.recv(ws))["t"], "state")
        self.assertEqual(await self.recv_close_code(ws), 4401)


class WebSocketMessageTest(ActivityTestBase):

    async def test_hello_then_state(self):
        before = time.time() * 1000
        ws = await self.connect()
        hello = await self.recv(ws)
        state = await self.recv(ws)

        self.assertEqual(hello["t"], "hello")
        self.assertEqual(hello["protocol_version"], 4)
        self.assertEqual(hello["server_epoch"], self.server.server_epoch)
        self.assertIsInstance(hello["server_ms"], int)
        self.assertAlmostEqual(hello["server_ms"], before, delta=5000)
        self.assertEqual(hello["user"]["id"], DISCORD_USER["id"])
        self.assertEqual(hello["user"]["username"], "hansol")

        self.assertEqual(state["t"], "state")
        self.assertEqual(state["protocol_version"], 4)
        self.assertEqual(state["server_epoch"], self.server.server_epoch)
        self.assertEqual(state["state_version"], 0)
        self.assertEqual(state["phase"], "none")
        self.assertIsInstance(state["server_ms"], int)
        for key in ("game_id", "round", "season", "start_at_ms", "deadline_ms", "grace_ms",
                    "turn_id", "current_index", "ddragon_version", "result", "advantage", "paused"):
            self.assertIn(key, state)
            self.assertIsNone(state[key], key)
        for key in ("players", "pick_order", "champions", "auto_assigned", "present"):
            self.assertEqual(state[key], [], key)
        self.assertEqual(state["selections"], {})
        self.assertEqual(
            state["me"],
            {
                "id": DISCORD_USER["id"],
                "role": "spectator",
                "team": None,
                "can_start": True,
                "can_start_now": False,
                "can_pause": False,
                "can_resume": False,
                "can_pick": False,
                "can_advantage": False,
                "can_report": False,
                "can_reverse": False,
            },
        )

    async def test_ping_pong(self):
        ws = await self.connect_ready()
        await ws.send_str(json.dumps({"t": "ping", "id": "p-3", "c": 12345.67}))
        pong = await self.recv(ws)
        self.assertEqual(pong["t"], "pong")
        self.assertEqual(pong["id"], "p-3")
        self.assertEqual(pong["c"], 12345.67)
        self.assertIsInstance(pong["s"], int)
        self.assertAlmostEqual(pong["s"], time.time() * 1000, delta=5000)

    async def test_sync_returns_state(self):
        ws = await self.connect_ready()
        await ws.send_str(json.dumps({"t": "sync", "id": "s-1"}))
        state = await self.recv(ws)
        self.assertEqual(state["t"], "state")
        self.assertEqual(state["phase"], "none")
        self.assertEqual(state["state_version"], 0)

    async def test_bad_messages_get_bad_request_reply(self):
        ws = await self.connect_ready()
        cases = [
            ('{"t": "dance", "id": "x-1"}', "x-1"),  # 모르는 t
            ('{"t": "demo_countdown", "id": "d-1", "seconds": 5}', "d-1"),  # v2에서 없어진 t
            ("{broken json", None),  # 깨진 JSON
        ]
        for text, expected_id in cases:
            with self.subTest(text=text):
                await ws.send_str(text)
                reply = await self.recv(ws)
                self.assertEqual(reply["t"], "reply")
                self.assertEqual(reply["id"], expected_id)
                self.assertIs(reply["ok"], False)
                self.assertEqual(reply["code"], "bad_request")
                self.assertIsInstance(reply["message"], str)
                self.assertEqual(reply["state_version"], 0)
                # 위반 횟수를 초기화해 다음 사례가 4400에 걸리지 않게 한다
                await ws.send_str(json.dumps({"t": "sync", "id": "reset"}))
                await self.recv(ws)

    async def test_field_violations_get_bad_request(self):
        ws = await self.connect_ready()
        cases = [
            {"t": "ping", "c": 1},  # id 없음
            {"t": "ping", "id": "", "c": 1},
            {"t": "ping", "id": "x" * 65, "c": 1},
            {"t": "ping", "id": "p", "c": "1"},
            {"t": "ping", "id": "p", "c": True},
            {"t": "start", "id": "g"},  # game_id·guild_id 없음
            {"t": "start", "id": "g", "game_id": None, "guild_id": 5},
            {"t": "pick", "id": "k", "game_id": "g-1", "turn_id": "g-1:0"},  # champion_id 없음
            {"t": "pick", "id": "k", "game_id": "g-1", "turn_id": "g-1:0", "champion_id": ""},
            {"t": "pick", "id": "k", "game_id": 1, "turn_id": "g-1:0", "champion_id": "Ahri"},
            {"t": "result", "id": "r", "game_id": "g-1", "winner": 1},
            {"t": "reverse", "id": "v", "game_id": "g-1", "expected_winner": "team3"},
            {"t": "start_now", "id": "n"},  # game_id 없음
            {"t": "pause", "id": "p", "game_id": 5},
            {"t": "resume", "id": "r", "game_id": ""},
        ]
        for message in cases:
            with self.subTest(message=message):
                await ws.send_str(json.dumps(message))
                reply = await self.recv(ws)
                self.assertEqual((reply["t"], reply["code"]), ("reply", "bad_request"))
                await ws.send_str(json.dumps({"t": "sync", "id": "reset"}))
                await self.recv(ws)

    async def test_message_over_4kb_gets_bad_request(self):
        ws = await self.connect_ready()
        await ws.send_str(json.dumps({"t": "ping", "id": "p", "c": 1, "pad": "x" * 4100}))
        reply = await self.recv(ws)
        self.assertEqual((reply["t"], reply["code"]), ("reply", "bad_request"))

    async def test_three_consecutive_violations_close_4400(self):
        ws = await self.connect_ready()
        for _ in range(3):  # 세 번째 위반도 reply를 받은 뒤 닫힌다
            await ws.send_str("{broken")
            self.assertEqual((await self.recv(ws))["code"], "bad_request")
        self.assertEqual(await self.recv_close_code(ws), 4400)

    async def test_valid_message_resets_violations(self):
        ws = await self.connect_ready()
        for text in ["{broken", "{broken", '{"t": "ping", "id": "p", "c": 1}', "{broken", "{broken"]:
            await ws.send_str(text)
            await self.recv(ws)
        await ws.send_str(json.dumps({"t": "ping", "id": "p-alive", "c": 2}))
        self.assertEqual((await self.recv(ws))["id"], "p-alive")  # 아직 연결돼 있다


class ShutdownTest(ActivityTestBase):

    async def test_shutdown_closes_sockets_with_1001(self):
        ws = await self.connect_ready()
        await self.client.server.close()
        self.assertEqual(await self.recv_close_code(ws), 1001)
        self.assertEqual(self.server._connections, set())
        self.assertIsNone(self.server._http)


##
# @brief 게임 요청(start·pick·result·reverse)을 실제 WebSocket으로 주고받는 테스트 기반.
class GameSocketBase(ActivityTestBase):

    async def send(self, ws, message):
        await ws.send_str(json.dumps(message))

    async def recv_type(self, ws, kind):
        msg = await self.recv(ws)
        self.assertEqual(msg["t"], kind, msg)
        return msg

    async def until(self, predicate):
        """서버 태스크가 입장 등을 반영할 때까지 최대 2초 기다린다."""
        for _ in range(200):
            if predicate():
                return
            await asyncio.sleep(0.01)
        self.fail("조건이 끝내 참이 되지 않았습니다")


class GameRoundTripTest(GameSocketBase):
    """DEV_MODE activity: 연결 → hello/state → start → state 변화 → pick → reply."""

    async def test_start_pick_result_round_trip(self):
        ws = await self.connect()
        hello = await self.recv_type(ws, "hello")
        first = await self.recv_type(ws, "state")
        self.assertEqual((hello["protocol_version"], first["phase"]), (4, "none"))
        other = await self.connect_ready()  # 다른 연결도 같은 state를 받는다

        await self.send(ws, {"t": "start", "id": "g-1", "game_id": None, "guild_id": "guild-1"})
        starting = await self.recv_type(ws, "state")  # state가 reply보다 먼저 온다
        reply = await self.recv_type(ws, "reply")
        self.assertEqual(starting["phase"], "starting")
        self.assertEqual(starting["state_version"], first["state_version"] + 1)
        self.assertEqual(starting["start_at_ms"] - starting["server_ms"], 15000)
        self.assertEqual(len(starting["players"]), 6)
        self.assertEqual(starting["ddragon_version"], "15.19.1")
        self.assertEqual(
            reply,
            {
                "t": "reply",
                "id": "g-1",
                "ok": True,
                "code": "ok",
                "message": "ROUND 87 게임을 시작했습니다.",
                "state_version": starting["state_version"],
            },
        )
        self.assertEqual((await self.recv_type(other, "state"))["game_id"], starting["game_id"])

        await self.clock.advance(15)  # 서버 타이머가 picking으로 바꾼다
        picking = await self.recv_type(ws, "state")
        self.assertEqual(picking["phase"], "picking")
        self.assertEqual(picking["deadline_ms"] - picking["server_ms"], 20000)
        self.assertTrue(picking["me"]["can_pick"])  # DEV_MODE: 누구나 대신 고른다
        self.assertEqual((await self.recv_type(other, "state"))["phase"], "picking")

        champ = picking["champions"][0]["id"]
        await self.send(ws, {
            "t": "pick", "id": "k-1", "game_id": picking["game_id"],
            "turn_id": picking["turn_id"], "champion_id": champ,
        })
        picked = await self.recv_type(ws, "state")
        reply = await self.recv_type(ws, "reply")
        self.assertEqual(picked["selections"], {picking["pick_order"][0]: champ})
        self.assertEqual(picked["current_index"], 1)
        self.assertEqual((reply["id"], reply["code"], reply["ok"]), ("k-1", "ok", True))
        self.assertEqual(reply["state_version"], picked["state_version"])

        # 같은 차례 ID로 다시 고르면 stale_turn (상태가 바뀌지 않아 state 없이 reply만 온다)
        await self.send(ws, {
            "t": "pick", "id": "k-2", "game_id": picking["game_id"],
            "turn_id": picking["turn_id"], "champion_id": picking["champions"][1]["id"],
        })
        reply = await self.recv_type(ws, "reply")
        self.assertEqual((reply["code"], reply["ok"]), ("stale_turn", False))
        self.assertEqual(reply["state_version"], picked["state_version"])

        for _ in range(5):  # 나머지 5명은 시간 초과로 자동 배정
            await self.clock.advance(22)
        state = picked
        while state["phase"] != "awaiting_result":
            state = await self.recv_type(ws, "state")
        self.assertEqual(len(state["auto_assigned"]), 5)
        self.assertTrue(state["me"]["can_report"])

        await self.send(ws, {"t": "result", "id": "r-1", "game_id": state["game_id"], "winner": "team2"})
        done = await self.recv_type(ws, "state")
        reply = await self.recv_type(ws, "reply")
        self.assertEqual(done["phase"], "completed")
        self.assertEqual(done["result"]["winner"], "team2")
        self.assertEqual(reply["code"], "ok")

        await self.send(ws, {
            "t": "reverse", "id": "v-1", "game_id": done["game_id"], "expected_winner": "team2",
        })
        reversed_state = await self.recv_type(ws, "state")
        reply = await self.recv_type(ws, "reply")
        self.assertEqual(reversed_state["result"]["winner"], "team1")
        self.assertEqual(reversed_state["result"]["corrected"]["from"], "team2")
        self.assertEqual(reply["code"], "ok")

    async def test_sync_returns_same_deadline(self):
        ws = await self.connect_ready()
        await self.send(ws, {"t": "start", "id": "g-1", "game_id": None, "guild_id": "guild-1"})
        await self.recv_type(ws, "state")
        await self.recv_type(ws, "reply")
        await self.clock.advance(15)
        picking = await self.recv_type(ws, "state")
        await self.clock.advance(5)
        await self.send(ws, {"t": "sync", "id": "s-1"})
        synced = await self.recv_type(ws, "state")
        self.assertEqual(synced["state_version"], picking["state_version"])
        self.assertEqual(synced["deadline_ms"], picking["deadline_ms"])
        self.assertEqual(synced["deadline_ms"] - synced["server_ms"], 15000)


class AdvantageRoundTripTest(GameSocketBase):
    """DEV_MODE activity 어드밴티지 판: start → advantage phase → advantage(밴) → picking → pick."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        arrange(self.game, BAN_TEAM1)

    async def test_start_advantage_pick_round_trip(self):
        ws = await self.connect_ready()
        await self.send(ws, {"t": "start", "id": "g-1", "game_id": None, "guild_id": "guild-1"})
        starting = await self.recv_type(ws, "state")
        await self.recv_type(ws, "reply")
        self.assertEqual(starting["advantage"]["status"], "pending")

        await self.clock.advance(15)
        adv = await self.recv_type(ws, "state")
        self.assertEqual(adv["phase"], "advantage")
        self.assertEqual(
            adv["advantage"], {"kind": "ban", "team": "team1", "status": "pending", "champion_id": None}
        )
        self.assertEqual(adv["deadline_ms"] - adv["server_ms"], 20000)
        self.assertTrue(adv["me"]["can_advantage"])
        self.assertFalse(adv["me"]["can_pick"])

        banned = adv["champions"][0]["id"]
        request = {"t": "advantage", "id": "a-1", "game_id": adv["game_id"], "champion_id": banned}
        await self.send(ws, request)
        picking = await self.recv_type(ws, "state")  # state가 reply보다 먼저 온다
        reply = await self.recv_type(ws, "reply")
        self.assertEqual(picking["phase"], "picking")
        self.assertEqual(picking["advantage"]["champion_id"], banned)
        self.assertFalse(picking["me"]["can_advantage"])
        self.assertEqual((reply["id"], reply["code"]), ("a-1", "ok"))
        self.assertEqual(reply["state_version"], picking["state_version"])
        await self.send(ws, request)  # 재전송에는 처음 reply를 그대로 돌려준다
        self.assertEqual(await self.recv_type(ws, "reply"), reply)

        pick = {
            "t": "pick", "id": "k-1", "game_id": picking["game_id"],
            "turn_id": picking["turn_id"], "champion_id": banned,
        }
        await self.send(ws, pick)
        reply = await self.recv_type(ws, "reply")
        self.assertEqual((reply["code"], reply["ok"]), ("champion_banned", False))
        await self.send(ws, dict(pick, id="k-2", champion_id=picking["champions"][1]["id"]))
        picked = await self.recv_type(ws, "state")
        reply = await self.recv_type(ws, "reply")
        self.assertEqual(reply["code"], "ok")
        self.assertEqual(picked["current_index"], 1)

    async def test_advantage_field_violations_get_bad_request(self):
        ws = await self.connect_ready()
        for bad in (
            {"t": "advantage", "id": "a-1", "game_id": None},
            {"t": "advantage", "id": "a-2", "game_id": None, "champion_id": 3},
            {"t": "advantage", "id": "a-3", "champion_id": "Zed"},
        ):
            await self.send(ws, bad)
            reply = await self.recv_type(ws, "reply")
            self.assertEqual((reply["id"], reply["code"]), (bad["id"], "bad_request"))
            await self.send(ws, {"t": "ping", "id": "p", "c": 1})  # 연속 위반 횟수를 비운다
            await self.recv_type(ws, "pong")


class IdempotencyTest(GameSocketBase):

    async def start_picking(self, ws):
        await self.send(ws, {"t": "start", "id": "g-1", "game_id": None, "guild_id": "guild-1"})
        await self.recv_type(ws, "state")
        await self.recv_type(ws, "reply")
        await self.clock.advance(15)
        return await self.recv_type(ws, "state")

    async def test_resend_same_request_returns_first_reply(self):
        ws = await self.connect_ready()
        picking = await self.start_picking(ws)
        pick = {
            "t": "pick", "id": "k-1", "game_id": picking["game_id"],
            "turn_id": picking["turn_id"], "champion_id": picking["champions"][0]["id"],
        }
        await self.send(ws, pick)
        await self.recv_type(ws, "state")
        first = await self.recv_type(ws, "reply")
        await self.send(ws, pick)  # 응답을 못 받았다고 보고 다시 보냄
        again = await self.recv_type(ws, "reply")  # 다시 처리하지 않아 state가 오지 않는다
        self.assertEqual(again, first)
        self.assertEqual(len(self.game.selected_users), 1)

        changed = dict(pick, champion_id=picking["champions"][1]["id"])
        await self.send(ws, changed)
        reply = await self.recv_type(ws, "reply")
        self.assertEqual((reply["id"], reply["code"]), ("k-1", "bad_request"))
        await self.send(ws, {"t": "ping", "id": "p", "c": 1})
        self.assertEqual((await self.recv_type(ws, "pong"))["id"], "p")

    async def test_duplicates_sent_back_to_back_are_processed_once(self):
        ws = await self.connect_ready()
        start = {"t": "start", "id": "g-1", "game_id": None, "guild_id": "guild-1"}
        await self.send(ws, start)
        await self.send(ws, start)
        messages = [await self.recv(ws) for _ in range(3)]
        self.assertEqual([m["t"] for m in messages], ["state", "reply", "reply"])
        self.assertEqual(messages[1], messages[2])
        self.assertEqual(self.game.current_game_id, 1)

    async def test_start_reply_is_kept_after_its_new_game(self):
        ws = await self.connect_ready()
        start = {"t": "start", "id": "g-1", "game_id": None, "guild_id": "guild-1"}
        await self.send(ws, start)
        await self.recv_type(ws, "state")
        first = await self.recv_type(ws, "reply")
        await self.send(ws, start)
        self.assertEqual(await self.recv_type(ws, "reply"), first)  # stale_game이 아니라 처음 reply

    async def test_replies_are_cleared_when_next_game_starts(self):
        ws = await self.connect_ready()
        await self.send(ws, {"t": "start", "id": "g-1", "game_id": None, "guild_id": "guild-1"})
        await self.recv_type(ws, "state")
        await self.recv_type(ws, "reply")
        self.assertEqual(len(self.server._replies), 1)
        async with self.game.lock:
            self.game.new_game(self.people, "activity")  # /게임시작
        await self.recv_type(ws, "state")
        self.assertEqual(self.server._replies, {})


class ProdPermissionTest(GameSocketBase):
    dev_mode = False

    async def asyncSetUp(self):
        await super().asyncSetUp()
        # 연결한 사용자(DISCORD_USER)를 온라인 6명 중 한 명으로 둔다
        self.people[0] = Member(int(DISCORD_USER["id"]), "정한솔")

    async def test_me_is_built_per_user(self):
        ws = await self.connect_ready()
        await self.send(ws, {"t": "start", "id": "g-1", "game_id": None, "guild_id": "guild-1"})
        state = await self.recv_type(ws, "state")
        await self.recv_type(ws, "reply")
        me = state["me"]
        self.assertEqual(me["role"], "player")
        self.assertIn(me["team"], ("team1", "team2"))
        await self.game.set_present(state["pick_order"])  # 참가자 전원 입장 → 5초 카운트다운
        await self.recv_type(ws, "state")
        await self.clock.advance(5)
        picking = await self.recv_type(ws, "state")
        mine = picking["pick_order"][0] == DISCORD_USER["id"]
        self.assertEqual(picking["me"]["can_pick"], mine)


class PresenceSocketTest(GameSocketBase):
    """운영 activity: ready로 입장 → 참가자 전원 입장 시 카운트다운 → 이탈 시 취소, start_now·pause·resume 왕복."""
    dev_mode = False

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.people[0] = Member(int(DISCORD_USER["id"]), "정한솔")

    async def connect_as(self, user_id):
        """user_id로 세션을 받아 연결하고 hello·state를 받은 소켓을 돌려준다."""
        self.me_body["id"] = user_id
        return await self.connect_ready()

    async def recv_reply(self, ws):
        """state를 건너뛰고 다음 reply를 돌려준다."""
        while (msg := await self.recv(ws))["t"] != "reply":
            self.assertEqual(msg["t"], "state", msg)
        return msg

    async def test_ready_once_per_connection_and_same_user_counts_once(self):
        me = DISCORD_USER["id"]
        ws1 = await self.connect_ready()
        await self.send(ws1, {"t": "ready"})
        await self.send(ws1, {"t": "ready", "id": "x"})  # 두 번째 ready는 무시하고 id가 있어도 받는다
        await self.until(lambda: me in self.game.present)
        await self.send(ws1, {"t": "ping", "id": "p", "c": 1})
        while (msg := await self.recv(ws1))["t"] != "pong":
            self.assertEqual(msg["t"], "state")  # ready에는 reply가 없다
        self.assertEqual(self.server._ready_counts[me], 1)
        ws2 = await self.connect_ready()  # 같은 사람의 두 번째 연결(휴대폰 등)
        await self.send(ws2, {"t": "ready"})
        await self.until(lambda: self.server._ready_counts[me] == 2)
        await ws1.close()
        await self.until(lambda: self.server._ready_counts[me] == 1)
        self.assertIn(me, self.game.present)  # 다른 연결이 남아 있어 입장 유지
        await ws2.close()
        await self.until(lambda: me not in self.game.present)
        self.assertNotIn(me, self.server._ready_counts)

    async def test_connection_without_ready_is_not_present(self):
        ws = await self.connect_ready()
        await ws.close()
        await asyncio.sleep(0.05)
        self.assertEqual((self.game.present, dict(self.server._ready_counts)), (set(), {}))

    async def test_all_ready_counts_down_and_leaving_cancels(self):
        ws = await self.connect_ready()
        await self.send(ws, {"t": "start", "id": "g-1", "game_id": None, "guild_id": "guild-1"})
        self.assertEqual((await self.recv_reply(ws))["code"], "ok")
        ids = self.game.snapshot()["pick_order"]
        sockets = {}
        for uid in ids + ["777"]:  # 777은 관전자
            sockets[uid] = await self.connect_as(uid)
            await self.send(sockets[uid], {"t": "ready"})
        await self.until(lambda: self.game.start_at is not None)
        s = self.game.snapshot()
        self.assertEqual(s["present"], [p["id"] for p in s["players"]])  # 관전자는 빠진다
        self.assertEqual(s["start_at_ms"] - s["server_ms"], 5000)

        await sockets[ids[2]].close()
        await self.until(lambda: self.game.start_at is None)
        self.assertEqual(len(self.game.snapshot()["present"]), 5)
        self.assertEqual(self.game.visible_phase(), "starting")

        gid = s["game_id"]
        ws_a = sockets[ids[0]]
        await self.send(ws_a, {"t": "start_now", "id": "n-1", "game_id": gid})
        reply = await self.recv_reply(ws_a)
        self.assertEqual((reply["code"], reply["ok"]), ("ok", True))
        await self.send(ws_a, {"t": "pause", "id": "p-1", "game_id": gid})
        self.assertEqual((await self.recv_reply(ws_a))["code"], "ok")
        await self.send(ws_a, {"t": "pause", "id": "p-2", "game_id": gid})
        self.assertEqual((await self.recv_reply(ws_a))["code"], "already_paused")
        await self.send(ws_a, {"t": "resume", "id": "r-1", "game_id": gid})
        self.assertEqual((await self.recv_reply(ws_a))["code"], "ok")
        await self.send(ws_a, {"t": "resume", "id": "r-2", "game_id": gid})
        self.assertEqual((await self.recv_reply(ws_a))["code"], "not_paused")
        await self.clock.advance(5)
        self.assertEqual(self.game.visible_phase(), "picking")


class HeartbeatTest(GameSocketBase):
    """WebSocket 프로토콜 ping에 pong이 없으면 서버가 연결을 닫고 입장에서 뺀다."""
    heartbeat = 0.2

    async def test_missing_pong_drops_presence(self):
        me = DISCORD_USER["id"]
        alive = await self.connect_ready()
        await self.send(alive, {"t": "ready"})
        reader = asyncio.create_task(self.drain(alive))  # 받는 동안 ping에 자동으로 pong을 돌려준다
        self.me_body["id"] = "888"
        session = await self.get_session()
        silent = await self.client.ws_connect("/pick-api/ws", params={"session": session}, autoping=False)
        await self.send(silent, {"t": "ready"})
        await self.until(lambda: self.game.present == {me, "888"})
        await self.until(lambda: self.game.present == {me})  # pong이 없으면 약 0.3초 뒤 닫힌다
        await asyncio.sleep(0.6)  # ping을 몇 번 더 주고받아도
        self.assertEqual(self.game.present, {me})  # pong을 돌려준 연결은 그대로다
        reader.cancel()

    async def drain(self, ws):
        async for _ in ws:
            pass


class EmbedModeSocketTest(GameSocketBase):
    pick_mode = "embed"

    async def test_start_not_allowed_and_state_none(self):
        ws = await self.connect()
        await self.recv_type(ws, "hello")
        state = await self.recv_type(ws, "state")
        self.assertFalse(state["me"]["can_start"])
        await self.send(ws, {"t": "start", "id": "g-1", "game_id": None, "guild_id": "guild-1"})
        reply = await self.recv_type(ws, "reply")
        self.assertEqual((reply["ok"], reply["code"]), (False, "not_allowed"))
        async with self.game.lock:
            self.game.new_game(self.people, "embed")  # 디스코드 /게임시작(embed)
        state = await self.recv_type(ws, "state")
        self.assertEqual((state["phase"], state["game_id"]), ("none", None))


##
# @brief 송신 작업 단위 테스트용 가짜 WebSocket. send_str은 gate가 열릴 때까지 멈춘다.
class FakeWebSocket:

    def __init__(self):
        self.sent = []
        self.close_code = None
        self.gate = asyncio.Event()
        self.gate.set()

    async def send_str(self, data):
        await self.gate.wait()
        self.sent.append(json.loads(data))

    async def close(self, *, code):
        self.close_code = code


class ConnectionSenderTest(unittest.IsolatedAsyncioTestCase):

    async def test_pending_state_is_replaced_by_latest(self):
        ws = FakeWebSocket()
        ws.gate.clear()
        conn = _Connection(ws, "u", send_timeout=5)
        conn.send({"t": "hello"})
        await asyncio.sleep(0)  # hello 전송에서 멈춘다
        conn.send_state({"t": "state", "state_version": 1})
        conn.send({"t": "pong", "id": "p"})
        conn.send_state({"t": "state", "state_version": 2})
        conn.send_state({"t": "state", "state_version": 3})
        ws.gate.set()
        conn.request_close(1000)
        await asyncio.wait_for(conn.task, 1)
        self.assertEqual(
            ws.sent,
            [{"t": "hello"}, {"t": "state", "state_version": 3}, {"t": "pong", "id": "p"}],
        )
        self.assertEqual(ws.close_code, 1000)

    async def test_slow_send_closes_4408(self):
        ws = FakeWebSocket()
        ws.gate.clear()  # 영영 보내지 못한다
        conn = _Connection(ws, "u", send_timeout=0.2)
        conn.send({"t": "hello"})
        await asyncio.wait_for(conn.task, 2)
        self.assertEqual(ws.close_code, 4408)
        self.assertEqual(ws.sent, [])


class RealServerLoggingTest(unittest.IsolatedAsyncioTestCase):
    """start()/close()로 실제 포트에 띄워 로그에 비밀 값이 남지 않는지 확인한다."""

    async def asyncSetUp(self):
        fake = web.Application()

        async def token(request):
            return web.json_response({"access_token": ACCESS_TOKEN})

        async def me(request):
            return web.json_response(DISCORD_USER)

        fake.router.add_post("/oauth2/token", token)
        fake.router.add_get("/users/@me", me)
        self.fake_discord = TestServer(fake)
        await self.fake_discord.start_server()

    async def asyncTearDown(self):
        await self.fake_discord.close()

    async def test_logs_have_no_secrets_or_query(self):
        game, _ = make_game(FakeClock(), True, "activity", [])
        server = ActivityServer(
            game=game,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            port=0,  # 테스트용 임시 포트
            discord_api_base=str(self.fake_discord.make_url("")),
        )
        with self.assertLogs(level="DEBUG") as captured:
            await server.start()
            try:
                host, port = server._runner.addresses[0][:2]
                self.assertEqual(host, "127.0.0.1")
                async with aiohttp.ClientSession() as http:
                    base = f"http://127.0.0.1:{port}"
                    async with http.post(f"{base}/pick-api/token", json={"code": GOOD_CODE}) as resp:
                        session = (await resp.json())["session"]
                    async with http.ws_connect(f"{base}/pick-api/ws?session={session}") as ws:
                        await asyncio.wait_for(ws.receive(), RECEIVE_TIMEOUT)
                        await asyncio.wait_for(ws.receive(), RECEIVE_TIMEOUT)
            finally:
                await server.close()
        output = "\n".join(captured.output)
        self.assertIn("/pick-api/ws", output)  # access log는 남는다
        for secret in (GOOD_CODE, ACCESS_TOKEN, CLIENT_SECRET, session, "session="):
            self.assertNotIn(secret, output)


if __name__ == "__main__":
    unittest.main()
