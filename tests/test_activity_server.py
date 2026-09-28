##
# @file test_activity_server.py
# @brief activity_server의 토큰 교환·세션·WebSocket 규격(docs/ACTIVITY_PROTOCOL.md 1단계) 테스트.
# @details 가짜 Discord API를 aiohttp 테스트 서버로 띄워 discord_api_base로 주입한다. 실제 Discord나
#          봇(got_champe)은 쓰지 않는다. 실행: uv run python -m unittest discover -s tests -t . -v
import asyncio
import json
import time
import unittest

import aiohttp
from aiohttp import WSMsgType, web
from aiohttp.test_utils import TestClient, TestServer

import activity_server
from activity_server import ActivityServer, _Connection

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
# @brief 가짜 Discord API와 액티비티 서버를 띄우는 공통 테스트 기반.
class ActivityTestBase(unittest.IsolatedAsyncioTestCase):
    dev_mode = True
    session_ttl = activity_server.SESSION_TTL_SECONDS

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

        self.server = ActivityServer(
            dev_mode=self.dev_mode,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            discord_api_base=str(self.fake_discord.make_url("")),
            session_ttl=self.session_ttl,
        )
        self.client = TestClient(TestServer(self.server.app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        await self.fake_discord.close()

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
        self.assertEqual(hello["protocol_version"], 1)
        self.assertEqual(hello["server_epoch"], self.server.server_epoch)
        self.assertIsInstance(hello["server_ms"], int)
        self.assertAlmostEqual(hello["server_ms"], before, delta=5000)
        self.assertEqual(hello["user"]["id"], DISCORD_USER["id"])
        self.assertEqual(hello["user"]["username"], "hansol")

        self.assertEqual(state["t"], "state")
        self.assertEqual(state["protocol_version"], 1)
        self.assertEqual(state["server_epoch"], self.server.server_epoch)
        self.assertEqual(state["state_version"], 0)
        self.assertEqual(state["phase"], "none")
        self.assertIsInstance(state["server_ms"], int)
        for key in ("game_id", "round", "season", "start_at_ms", "deadline_ms", "grace_ms",
                    "turn_id", "current_index"):
            self.assertIn(key, state)
            self.assertIsNone(state[key], key)
        for key in ("players", "pick_order", "champions", "auto_assigned"):
            self.assertEqual(state[key], [], key)
        self.assertEqual(state["selections"], {})
        self.assertEqual(state["me"], {"id": DISCORD_USER["id"], "role": "spectator"})

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
            {"t": "demo_countdown", "id": "d", "seconds": 0},
            {"t": "demo_countdown", "id": "d", "seconds": 61},
            {"t": "demo_countdown", "id": "d", "seconds": 2.5},
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


class DemoCountdownDevTest(ActivityTestBase):
    dev_mode = True

    async def test_demo_countdown_picking_then_none(self):
        ws = await self.connect_ready()
        other = await self.connect_ready()  # 다른 연결도 같은 state를 받는다

        await ws.send_str(json.dumps({"t": "demo_countdown", "id": "d-1", "seconds": 1}))
        picking = await self.recv(ws)
        reply = await self.recv(ws)

        self.assertEqual(picking["t"], "state")
        self.assertEqual(picking["phase"], "picking")
        self.assertEqual(picking["game_id"], "demo")
        self.assertEqual(picking["turn_id"], "demo-1")
        self.assertEqual(picking["grace_ms"], 2000)
        self.assertEqual(picking["deadline_ms"] - picking["server_ms"], 1000)
        self.assertEqual(picking["state_version"], 1)
        self.assertEqual(picking["players"], [])

        self.assertEqual(reply["t"], "reply")
        self.assertEqual(reply["id"], "d-1")
        self.assertIs(reply["ok"], True)
        self.assertEqual(reply["code"], "ok")
        self.assertEqual(reply["state_version"], 1)

        other_picking = await self.recv(other)
        self.assertEqual(other_picking["turn_id"], "demo-1")

        started = time.monotonic()
        done = await self.recv(ws)  # 마감 1초 + 유예 2초 뒤
        waited = time.monotonic() - started
        self.assertEqual(done["t"], "state")
        self.assertEqual(done["phase"], "none")
        self.assertIsNone(done["game_id"])
        self.assertIsNone(done["deadline_ms"])
        self.assertEqual(done["state_version"], 2)
        self.assertGreaterEqual(waited, 2.5)
        self.assertEqual((await self.recv(other))["phase"], "none")

        await ws.send_str(json.dumps({"t": "sync", "id": "s-2"}))
        self.assertEqual((await self.recv(ws))["state_version"], 2)

    async def test_sync_during_demo_keeps_same_deadline(self):
        ws = await self.connect_ready()
        await ws.send_str(json.dumps({"t": "demo_countdown", "id": "d-1", "seconds": 20}))
        picking = await self.recv(ws)
        await self.recv(ws)  # reply
        await asyncio.sleep(0.2)
        await ws.send_str(json.dumps({"t": "sync", "id": "s-1"}))
        synced = await self.recv(ws)
        self.assertEqual(synced["phase"], "picking")
        self.assertEqual(synced["state_version"], picking["state_version"])
        self.assertAlmostEqual(synced["deadline_ms"], picking["deadline_ms"], delta=50)
        self.assertLess(synced["deadline_ms"] - synced["server_ms"], 20000)

    async def test_new_demo_replaces_running_one(self):
        ws = await self.connect_ready()
        await ws.send_str(json.dumps({"t": "demo_countdown", "id": "d-1", "seconds": 1}))
        await self.recv(ws)
        await self.recv(ws)
        await ws.send_str(json.dumps({"t": "demo_countdown", "id": "d-2", "seconds": 20}))
        second = await self.recv(ws)
        await self.recv(ws)
        self.assertEqual(second["turn_id"], "demo-2")
        self.assertEqual(second["state_version"], 2)
        await asyncio.sleep(3.3)  # 첫 데모의 종료 시점이 지나도
        await ws.send_str(json.dumps({"t": "sync", "id": "s-1"}))
        synced = await self.recv(ws)
        self.assertEqual((synced["phase"], synced["turn_id"]), ("picking", "demo-2"))


class DemoCountdownProdTest(ActivityTestBase):
    dev_mode = False

    async def test_demo_countdown_not_allowed(self):
        ws = await self.connect_ready()
        await ws.send_str(json.dumps({"t": "demo_countdown", "id": "d-1", "seconds": 20}))
        reply = await self.recv(ws)
        self.assertEqual(reply["t"], "reply")
        self.assertEqual(reply["id"], "d-1")
        self.assertIs(reply["ok"], False)
        self.assertEqual(reply["code"], "not_allowed")
        self.assertEqual(reply["state_version"], 0)


class ShutdownTest(ActivityTestBase):

    async def test_shutdown_closes_sockets_with_1001(self):
        ws = await self.connect_ready()
        await ws.send_str(json.dumps({"t": "demo_countdown", "id": "d-1", "seconds": 20}))
        await self.recv(ws)
        await self.recv(ws)
        await self.client.server.close()
        self.assertEqual(await self.recv_close_code(ws), 1001)
        self.assertEqual(self.server._connections, set())
        self.assertTrue(self.server._demo_task.done())
        self.assertIsNone(self.server._http)


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
        server = ActivityServer(
            dev_mode=True,
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
