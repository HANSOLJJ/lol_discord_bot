##
# @file activity_server.py
# @brief 디스코드 액티비티용 HTTP·WebSocket 서버 (토큰 교환, 세션, 상태 스냅샷, 게임 요청).
# @details 봇 프로세스 안에서 aiohttp.web으로 127.0.0.1에만 바인딩한다. 메시지 형식의 기준은
#          docs/ACTIVITY_PROTOCOL.md(protocol_version 4)이다. 봇 전역 상태를 import하지 않고 게임 객체
#          (game_core.GameCore와 같은 메서드를 가진 객체)와 설정을 생성자로 주입받는다. 이 모듈은 세션·연결·
#          형식 검증·요청 멱등성·state 방송을 맡고, 게임 판정은 게임 객체가 한다.
#          OAuth code, access token, client secret, 세션 토큰, WebSocket query는 로그에 남기지 않는다.
import asyncio
import collections
import json
import logging
import math
import secrets
import time
import uuid

import aiohttp
from aiohttp import web
from aiohttp.abc import AbstractAccessLogger

PROTOCOL_VERSION = 4
DEFAULT_PORT = 8790
BIND_HOST = "127.0.0.1"
DISCORD_API_BASE = "https://discord.com/api"
DISCORD_TIMEOUT_SECONDS = 10  # Discord OAuth2 호출 하나의 최대 시간(초)
SESSION_TTL_SECONDS = 3600  # 세션 수명(초). 발급 시점부터 센다
MAX_BODY_BYTES = 4096  # 토큰 요청 본문 최대 크기
MAX_CODE_LENGTH = 512
MAX_MESSAGE_BYTES = 4096  # 이보다 큰 WS 메시지는 규격 위반(reply bad_request)
WS_HARD_LIMIT_BYTES = 64 * 1024  # 이보다 큰 WS 메시지는 aiohttp가 1009로 끊는다
MAX_REQUEST_ID_LENGTH = 64
MAX_VIOLATIONS = 3  # 연속 규격 위반이 이 횟수에 닿으면 4400으로 닫는다
SEND_TIMEOUT_SECONDS = 5  # 메시지 하나를 이 시간 안에 못 보내면 느린 연결로 보고 4408로 닫는다
# WebSocket 프로토콜 ping 간격(초). pong이 간격의 절반 안에 없으면 aiohttp가 연결을 닫아 입장에서 빠진다
HEARTBEAT_SECONDS = 10
TOKEN_RATE_LIMIT = 30  # 토큰 엔드포인트 허용 횟수(서버 전체). 프록시 뒤라 IP 구분이 무의미하다
TOKEN_RATE_WINDOW_SECONDS = 60
MAX_FIELD_LENGTH = 128  # game_id·turn_id·champion_id 등 문자열 필드의 최대 길이
TEAM_KEYS = ("team1", "team2")

CLOSE_NORMAL = 1000
CLOSE_GOING_AWAY = 1001
CLOSE_BAD_REQUEST = 4400
CLOSE_UNAUTHORIZED = 4401
CLOSE_SLOW = 4408

log = logging.getLogger("activity")


##
# @brief 현재 시각을 유닉스 밀리초 정수로 반환한다.
# @return 유닉스 밀리초.
def _now_ms():
    return int(time.time() * 1000)


##
# @brief 실패 응답(`{"error": 코드}`)을 만든다.
# @param status HTTP 상태 코드.
# @param code 규격의 error 코드.
# @return web.Response.
def _error(status, code):
    return web.json_response({"error": code}, status=status)


##
# @brief Discord users/@me 응답에서 규격의 user 객체를 뽑는다.
# @param data users/@me 응답 JSON.
# @return {id, username, global_name, avatar} 또는 형식이 맞지 않으면 None.
def _parse_user(data):
    if not isinstance(data, dict):
        return None
    user_id, username = data.get("id"), data.get("username")
    global_name, avatar = data.get("global_name"), data.get("avatar")
    if not isinstance(user_id, str) or not user_id or not isinstance(username, str):
        return None
    if not isinstance(global_name, (str, type(None))) or not isinstance(avatar, (str, type(None))):
        return None
    return {"id": user_id, "username": username, "global_name": global_name, "avatar": avatar}


##
# @brief 문자열 필드 형식 검사.
# @param value 값.
# @param nullable True면 None도 허용한다.
# @return 형식이 맞으면 True.
def _is_field(value, nullable=False):
    if value is None:
        return nullable
    return isinstance(value, str) and 1 <= len(value) <= MAX_FIELD_LENGTH


# 게임 요청별 필드 형식 규칙: {t: {필드: 검사 함수}}
_REQUEST_FIELDS = {
    "start": {
        "game_id": lambda v: _is_field(v, nullable=True),
        "guild_id": lambda v: _is_field(v, nullable=True),
    },
    "pick": {
        "game_id": lambda v: _is_field(v, nullable=True),
        "turn_id": lambda v: _is_field(v, nullable=True),
        "champion_id": _is_field,
    },
    "advantage": {
        "game_id": lambda v: _is_field(v, nullable=True),
        "champion_id": _is_field,
    },
    "result": {
        "game_id": lambda v: _is_field(v, nullable=True),
        "winner": _is_field,  # team1·team2 여부는 판정 순서 5번에서 확인한다(규격 9절)
    },
    "reverse": {
        "game_id": lambda v: _is_field(v, nullable=True),
        "expected_winner": lambda v: v in TEAM_KEYS,
    },
    "start_now": {"game_id": lambda v: _is_field(v, nullable=True)},
    "pause": {"game_id": lambda v: _is_field(v, nullable=True)},
    "resume": {"game_id": lambda v: _is_field(v, nullable=True)},
}


##
# @brief 게임 요청의 필수 필드가 모두 있고 형식이 맞는지 확인한다. 모르는 필드는 무시한다.
# @param kind 요청 종류.
# @param data 요청 dict.
# @return 형식이 맞으면 True.
def _valid_request(kind, data):
    return all(
        name in data and check(data[name]) for name, check in _REQUEST_FIELDS[kind].items()
    )


##
# @brief Discord 토큰 교환이나 신원 확인이 실패했음을 알리는 예외. 메시지에는 상태 코드만 담는다.
class _OAuthError(Exception):
    pass


##
# @brief access log에 query 없이 경로만 남기는 로거. 세션 토큰이 WS query로 오기 때문이다.
class _PathOnlyAccessLogger(AbstractAccessLogger):

    ##
    # @brief 요청 한 건을 "원격주소 메서드 경로 상태 소요시간" 형식으로 기록한다.
    # @param request 요청.
    # @param response 응답.
    # @param time 처리 시간(초).
    def log(self, request, response, time):
        self.logger.info(
            '%s "%s %s" %s %.3fs', request.remote, request.method, request.path, response.status, time
        )


##
# @brief 발급한 세션 하나. 서버 메모리에만 보관한다.
class _Session:

    ##
    # @param user 규격의 user 객체.
    # @param ttl 수명(초).
    def __init__(self, user, ttl):
        self.user = user
        self.expires_mono = time.monotonic() + ttl  # 만료 판정용 단조 시계
        self.expires_ms = _now_ms() + int(ttl * 1000)  # 클라이언트에 알려주는 유닉스 밀리초


##
# @brief WebSocket 연결 하나와 그 연결 전용 송신 작업.
# @details 보낼 메시지는 순서대로 쌓아 송신 작업 하나가 보낸다. 아직 못 보낸 state가 있으면 새 state가 그
#          자리를 덮어써서 가장 최신 것만 나간다. 메시지 하나를 제한 시간 안에 못 보내면 4408로 닫는다.
#          닫기 요청이 오면 쌓인 메시지를 마저 보낸 뒤 그 코드로 닫는다.
class _Connection:

    ##
    # @param ws prepare가 끝난 WebSocketResponse(또는 같은 메서드를 가진 객체).
    # @param user_id 연결한 Discord 사용자 ID.
    # @param send_timeout 메시지 하나의 송신 제한 시간(초).
    def __init__(self, ws, user_id, send_timeout=SEND_TIMEOUT_SECONDS):
        self.ws = ws
        self.user_id = user_id
        self.violations = 0  # 연속 규격 위반 횟수
        self.ready = False  # ready를 받았는가(화면이 첫 state를 그렸다 = 입장)
        self.requests = set()  # 처리 중인 게임 요청·입장 반영 태스크
        self._send_timeout = send_timeout
        self._items = collections.deque()  # 보낼 순서대로 쌓인 [메시지] 칸
        self._state_item = None  # 아직 못 보낸 state 칸. 새 state는 이 칸을 덮어쓴다
        self._close_code = None
        self._wake = asyncio.Event()
        self.task = asyncio.create_task(self._run())

    ##
    # @brief 메시지를 송신 순서 끝에 쌓는다. 닫기 요청 뒤에는 버린다.
    # @param message 보낼 dict.
    def send(self, message):
        if self._close_code is None:
            self._items.append([message])
            self._wake.set()

    ##
    # @brief state를 쌓는다. 아직 못 보낸 state가 있으면 그 자리를 새 state로 바꾼다.
    # @param state 보낼 state dict.
    def send_state(self, state):
        if self._close_code is not None:
            return
        if self._state_item is not None:
            self._state_item[0] = state
        else:
            self._state_item = [state]
            self._items.append(self._state_item)
        self._wake.set()

    ##
    # @brief 쌓인 메시지를 보낸 뒤 주어진 코드로 닫도록 요청한다. 먼저 온 요청이 이긴다.
    # @param code 종료 코드.
    def request_close(self, code):
        if self._close_code is None:
            self._close_code = code
            self._wake.set()

    ##
    # @brief 송신 작업 본체. 연결이 닫히거나 닫기 요청을 처리하면 끝난다.
    async def _run(self):
        while True:
            if self._items:
                item = self._items.popleft()
                if item is self._state_item:
                    self._state_item = None
                try:
                    await asyncio.wait_for(
                        self.ws.send_str(json.dumps(item[0], ensure_ascii=False)), self._send_timeout
                    )
                except TimeoutError:
                    log.warning("[ACTIVITY] 느린 연결을 닫습니다 (user=%s)", self.user_id)
                    await self._close(CLOSE_SLOW)
                    return
                except Exception:
                    return  # 연결이 이미 끊겼다
            elif self._close_code is not None:
                await self._close(self._close_code)
                return
            else:
                self._wake.clear()
                await self._wake.wait()

    ##
    # @brief 연결을 닫는다. 제한 시간을 넘기면 aiohttp가 전송 계층을 바로 끊는다.
    # @param code 종료 코드.
    async def _close(self, code):
        try:
            await asyncio.wait_for(self.ws.close(code=code), self._send_timeout)
        except Exception:
            pass


##
# @brief 액티비티 서버. 토큰 교환·세션·WebSocket 연결과 상태 전송을 맡는다.
# @details `app`을 aiohttp 테스트 도구에 바로 넘길 수 있고, 실제 실행은 start()/close()로 한다.
#          Discord HTTP 세션은 앱 시작 때 하나 만들어 재사용하고 정리 때 닫는다.
class ActivityServer:

    ##
    # @param game 게임 객체. snapshot(), me(), add_listener(), set_present(),
    #             activity_start/start_now/pause/resume/pick/advantage/result/reverse()를 쓴다.
    # @param client_id Discord 앱 client ID.
    # @param client_secret Discord 앱 client secret. 로그에 남기지 않는다.
    # @param port 바인딩할 포트(주소는 항상 127.0.0.1).
    # @param discord_api_base Discord API 기본 URL. 테스트에서 가짜 서버로 바꾼다.
    # @param session_ttl 세션 수명(초).
    # @param heartbeat WebSocket 프로토콜 ping 간격(초).
    # @param clock 요청 접수 시각을 잡는 단조 시계. 게임 객체의 마감 판정과 같은 시계여야 한다.
    def __init__(
        self,
        *,
        game,
        client_id,
        client_secret,
        port=DEFAULT_PORT,
        discord_api_base=DISCORD_API_BASE,
        session_ttl=SESSION_TTL_SECONDS,
        heartbeat=HEARTBEAT_SECONDS,
        clock=time.monotonic,
    ):
        self._game = game
        self._clock = clock
        self._client_id = client_id
        self._client_secret = client_secret
        self._port = port
        self._api_base = discord_api_base.rstrip("/")
        self._session_ttl = session_ttl
        self._heartbeat = heartbeat
        self.server_epoch = str(uuid.uuid4())  # 프로세스(서버 객체)마다 새로 만든다
        self._sessions = {}  # {세션 토큰: _Session}
        self._connections = set()  # 열린 _Connection
        # {사용자 ID: ready를 보낸 열린 연결 수}. 한 사람의 여러 연결(PC·휴대폰)은 한 명으로 센다
        self._ready_counts = collections.Counter()
        self._token_requests = collections.deque()  # 빈도 제한 창 안의 토큰 요청 시각(단조 시계)
        self._state_version = 0
        # {(사용자, game_id, 요청 id): (요청 내용, reply Future)} - 같은 요청 재전송에 같은 reply를 돌려준다.
        # 다음 판이 시작되면 비운다
        self._replies = {}
        self._last_game_id = None  # 마지막으로 보낸 state의 game_id (판이 바뀌었는지 판단용)
        self._http = None  # Discord 호출용 ClientSession
        self._runner = None
        self.app = web.Application(client_max_size=MAX_BODY_BYTES)
        self.app.router.add_post("/pick-api/token", self._handle_token)
        self.app.router.add_get("/pick-api/ws", self._handle_ws)
        self.app.on_startup.append(self._on_startup)
        self.app.on_shutdown.append(self._on_shutdown)
        self.app.on_cleanup.append(self._on_cleanup)
        game.add_listener(self._on_game_change)

    # === 실행과 정리 ===

    ##
    # @brief 127.0.0.1:port에 서버를 띄운다. 실패하면 만든 자원을 정리하고 예외를 그대로 던진다.
    async def start(self):
        runner = web.AppRunner(self.app, access_log_class=_PathOnlyAccessLogger)
        await runner.setup()
        try:
            await web.TCPSite(runner, BIND_HOST, self._port).start()
        except BaseException:
            await runner.cleanup()
            raise
        self._runner = runner
        log.info("[ACTIVITY] 액티비티 서버 시작: %s:%s", BIND_HOST, self._port)

    ##
    # @brief 서버를 멈춘다. 열린 소켓(1001)·Discord HTTP 세션·runner를 모두 정리한다.
    async def close(self):
        runner, self._runner = self._runner, None
        if runner is not None:
            await runner.cleanup()

    async def _on_startup(self, app):
        self._http = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=DISCORD_TIMEOUT_SECONDS)
        )

    async def _on_shutdown(self, app):
        connections = list(self._connections)
        for conn in connections:
            conn.request_close(CLOSE_GOING_AWAY)
        await asyncio.gather(*(conn.task for conn in connections), return_exceptions=True)

    async def _on_cleanup(self, app):
        if self._http is not None:
            await self._http.close()
            self._http = None

    # === HTTP: 토큰 교환 ===

    ##
    # @brief POST /pick-api/token. OAuth code를 access token과 세션으로 바꾼다.
    # @param request 요청.
    # @return 성공 200, 실패 400/401/429/500.
    async def _handle_token(self, request):
        if not self._take_token_slot():
            return _error(429, "rate_limited")
        try:
            data = json.loads(await request.read())
        except (web.HTTPRequestEntityTooLarge, ValueError):  # 4KB 초과, JSON·UTF-8 오류
            return _error(400, "bad_request")
        code = data.get("code") if isinstance(data, dict) else None
        if not isinstance(code, str) or not 1 <= len(code) <= MAX_CODE_LENGTH:
            return _error(400, "bad_request")
        try:
            access_token, user = await self._exchange_code(code)
        except _OAuthError as e:
            log.warning("[ACTIVITY] OAuth 실패: %s", e)
            return _error(401, "oauth_failed")
        except Exception as e:
            log.error("[ACTIVITY] 토큰 교환 중 서버 오류: %s", type(e).__name__)
            return _error(500, "server_error")
        self._prune_sessions()
        token = secrets.token_urlsafe(32)
        session = _Session(user, self._session_ttl)
        self._sessions[token] = session
        log.info("[ACTIVITY] 세션 발급 (user=%s)", user["id"])
        return web.json_response(
            {
                "access_token": access_token,
                "session": token,
                "session_expires_ms": session.expires_ms,
                "user": user,
            }
        )

    ##
    # @brief 토큰 요청 빈도 제한 창에 자리가 있으면 차지한다(서버 전체 기준).
    # @return 허용이면 True, 초과면 False.
    def _take_token_slot(self):
        now = time.monotonic()
        requests = self._token_requests
        while requests and now - requests[0] >= TOKEN_RATE_WINDOW_SECONDS:
            requests.popleft()
        if len(requests) >= TOKEN_RATE_LIMIT:
            return False
        requests.append(now)
        return True

    ##
    # @brief Discord에 code를 access token으로 바꾸고 users/@me로 신원을 확인한다.
    # @param code OAuth code.
    # @return (access_token, user).
    # @throws _OAuthError Discord 응답 오류, 형식 오류, 네트워크 오류·타임아웃.
    async def _exchange_code(self, code):
        form = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "grant_type": "authorization_code",
            "code": code,
        }
        try:
            async with self._http.post(f"{self._api_base}/oauth2/token", data=form) as resp:
                if resp.status != 200:
                    raise _OAuthError(f"oauth2/token {resp.status}")
                token_data = await resp.json(content_type=None)
            access_token = token_data.get("access_token") if isinstance(token_data, dict) else None
            if not isinstance(access_token, str) or not access_token:
                raise _OAuthError("oauth2/token 응답에 access_token 없음")
            headers = {"Authorization": f"Bearer {access_token}"}
            async with self._http.get(f"{self._api_base}/users/@me", headers=headers) as resp:
                if resp.status != 200:
                    raise _OAuthError(f"users/@me {resp.status}")
                me = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as e:
            raise _OAuthError(type(e).__name__) from None
        user = _parse_user(me)
        if user is None:
            raise _OAuthError("users/@me 응답 형식 오류")
        return access_token, user

    ##
    # @brief 만료된 세션을 지운다.
    def _prune_sessions(self):
        now = time.monotonic()
        for token in [t for t, s in self._sessions.items() if s.expires_mono <= now]:
            del self._sessions[token]

    ##
    # @brief 세션 토큰으로 유효한 세션을 찾는다. 만료됐으면 지우고 None을 반환한다.
    # @param token 세션 토큰(없으면 None).
    # @return _Session 또는 None.
    def _find_session(self, token):
        session = self._sessions.get(token) if token else None
        if session is None:
            return None
        if session.expires_mono <= time.monotonic():
            del self._sessions[token]
            return None
        return session

    # === WebSocket ===

    ##
    # @brief GET /pick-api/ws?session=... 세션이 없거나 만료됐으면 업그레이드 직후 4401로 닫는다.
    # @param request 요청.
    # @return WebSocketResponse.
    async def _handle_ws(self, request):
        ws = web.WebSocketResponse(
            max_msg_size=WS_HARD_LIMIT_BYTES, timeout=SEND_TIMEOUT_SECONDS, heartbeat=self._heartbeat
        )
        await ws.prepare(request)
        session = self._find_session(request.query.get("session"))
        if session is None:
            await ws.close(code=CLOSE_UNAUTHORIZED)
            return ws
        conn = _Connection(ws, session.user["id"])
        # 아래 세 줄 사이에 await가 없어 다른 상태 변경이 끼어들지 않는다
        self._connections.add(conn)
        conn.send(self._hello(session.user))
        conn.send_state(self._state_for(self._snapshot(), conn))
        log.info("[ACTIVITY] WS 연결 (user=%s, 연결 %d개)", conn.user_id, len(self._connections))
        try:
            await self._receive_loop(conn, session)
        finally:
            self._connections.discard(conn)
            await asyncio.gather(*conn.requests, return_exceptions=True)
            if conn.ready:
                await self._leave(conn)
            conn.request_close(CLOSE_NORMAL)
            await conn.task
            log.info("[ACTIVITY] WS 종료 (user=%s, code=%s)", conn.user_id, ws.close_code)
        return ws

    ##
    # @brief 클라이언트 메시지를 받아 처리한다. 세션 만료·연속 위반·연결 종료 시 끝난다.
    # @param conn 연결.
    # @param session 연결에 쓴 세션.
    async def _receive_loop(self, conn, session):
        while True:
            remaining = session.expires_mono - time.monotonic()
            if remaining <= 0:
                conn.request_close(CLOSE_UNAUTHORIZED)
                return
            try:
                msg = await conn.ws.receive(timeout=remaining)
            except TimeoutError:
                continue  # 다음 바퀴에서 만료를 판정한다
            received_at = self._clock()  # 접수 시각. 락이나 다른 작업을 기다리기 전에 잡는다
            if msg.type == web.WSMsgType.TEXT:
                self._handle_message(conn, msg.data, received_at)
            elif msg.type == web.WSMsgType.BINARY:
                self._reject(conn, None)
            else:
                return  # CLOSE·CLOSING·CLOSED·ERROR
            if conn.violations >= MAX_VIOLATIONS:
                conn.request_close(CLOSE_BAD_REQUEST)
                return

    ##
    # @brief 텍스트 메시지 하나를 검증하고 처리한다. 게임 요청은 태스크로 넘겨 다음 메시지 수신을 막지 않는다.
    # @param conn 연결.
    # @param text 받은 문자열.
    # @param received_at 접수 단조 시각.
    def _handle_message(self, conn, text, received_at):
        if len(text.encode("utf-8")) > MAX_MESSAGE_BYTES:
            self._reject(conn, None)
            return
        try:
            data = json.loads(text)
        except ValueError:
            self._reject(conn, None)
            return
        if isinstance(data, dict) and data.get("t") == "ready":  # id가 없고 응답하지 않는다
            conn.violations = 0
            self._enter(conn)
            return
        request_id = data.get("id") if isinstance(data, dict) else None
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= MAX_REQUEST_ID_LENGTH:
            self._reject(conn, None)
            return
        kind = data.get("t")
        if kind == "ping":
            c = data.get("c")
            if isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(c):
                self._reject(conn, request_id)
                return
            conn.violations = 0
            conn.send({"t": "pong", "id": request_id, "c": c, "s": _now_ms()})
        elif kind == "sync":
            conn.violations = 0
            conn.send_state(self._state_for(self._snapshot(), conn))
        elif kind in _REQUEST_FIELDS:
            if not _valid_request(kind, data):
                self._reject(conn, request_id)
                return
            conn.violations = 0
            task = asyncio.create_task(self._process_request(conn, kind, data, received_at))
            conn.requests.add(task)
            task.add_done_callback(conn.requests.discard)
        else:
            self._reject(conn, request_id)

    ##
    # @brief 게임 요청 하나를 처리하고 reply를 보낸다. 같은 사용자·판·요청 ID의 재전송에는 처음 reply를 돌려준다.
    # @details 상태가 바뀌면 게임 객체의 변경 알림으로 모든 소켓에 state가 먼저 쌓이고, reply는 그 뒤에 쌓인다.
    # @param conn 연결.
    # @param kind _REQUEST_FIELDS의 요청 종류.
    # @param data 형식 검증을 통과한 요청.
    # @param received_at 접수 단조 시각.
    async def _process_request(self, conn, kind, data, received_at):
        request_id = data["id"]
        key = (conn.user_id, data["game_id"], request_id)
        content = json.dumps(data, sort_keys=True, ensure_ascii=False)
        cached = self._replies.get(key)
        if cached is not None:
            if cached[0] != content:
                message = "같은 요청 ID로 다른 내용을 보냈습니다."
                conn.send(self._reply(request_id, False, "bad_request", message, self._state_version))
                return
            conn.send(await asyncio.shield(cached[1]))
            return
        future = asyncio.get_running_loop().create_future()
        self._replies[key] = (content, future)
        try:
            code, message = await self._dispatch(conn.user_id, kind, data, received_at)
        except Exception:
            log.exception("[ACTIVITY] %s 요청 처리 실패 (user=%s)", kind, conn.user_id)
            code, message = "server_error", "서버 오류로 요청을 처리하지 못했습니다."
        reply = self._reply(request_id, code == "ok", code, message, self._state_version)
        future.set_result(reply)
        # 새 판이 시작되면 보관한 reply를 비우는데, 그 판을 시작한 이 요청의 reply는 남긴다
        self._replies.setdefault(key, (content, future))
        log.info("[ACTIVITY] %s → %s (user=%s, id=%s)", kind, code, conn.user_id, request_id)
        conn.send(reply)

    ##
    # @brief 요청 종류에 맞는 게임 객체 메서드를 부른다.
    # @return (code, message).
    async def _dispatch(self, user_id, kind, data, received_at):
        game = self._game
        if kind == "start":
            return await game.activity_start(user_id, data["game_id"], data["guild_id"])
        if kind == "pick":
            return await game.activity_pick(
                user_id, data["game_id"], data["turn_id"], data["champion_id"], received_at
            )
        if kind == "advantage":
            return await game.activity_advantage(
                user_id, data["game_id"], data["champion_id"], received_at
            )
        if kind == "result":
            return await game.activity_result(user_id, data["game_id"], data["winner"])
        if kind == "start_now":
            return await game.activity_start_now(user_id, data["game_id"])
        if kind == "pause":
            return await game.activity_pause(user_id, data["game_id"])
        if kind == "resume":
            return await game.activity_resume(user_id, data["game_id"])
        return await game.activity_reverse(user_id, data["game_id"], data["expected_winner"])

    # === 입장 ===

    ##
    # @brief ready를 받은 연결을 입장시킨다. 연결마다 한 번만 센다. 그 사용자의 첫 입장이면 게임에 알린다.
    # @details 게임 반영은 락을 기다리므로 태스크로 넘기고, 연결이 닫힐 때 _leave보다 먼저 끝나도록 요청 태스크와
    #          함께 모은다. 목록을 복사하지 않고 _ready_counts를 넘겨, 반영 순서가 뒤바뀌어도 게임이 락을 얻은
    #          시점의 최신 입장 사용자를 읽는다.
    # @param conn 연결.
    def _enter(self, conn):
        if conn.ready:
            return
        conn.ready = True
        self._ready_counts[conn.user_id] += 1
        if self._ready_counts[conn.user_id] == 1:
            log.info("[ACTIVITY] 입장 (user=%s)", conn.user_id)
            task = asyncio.create_task(self._game.set_present(self._ready_counts))
            conn.requests.add(task)
            task.add_done_callback(conn.requests.discard)

    ##
    # @brief 닫힌 연결을 입장에서 뺀다. 그 사용자의 ready 연결이 모두 끊겼으면 게임에 알린다.
    # @param conn ready를 보낸 연결.
    async def _leave(self, conn):
        self._ready_counts[conn.user_id] -= 1
        if self._ready_counts[conn.user_id] > 0:
            return
        del self._ready_counts[conn.user_id]
        log.info("[ACTIVITY] 퇴장 (user=%s)", conn.user_id)
        await self._game.set_present(self._ready_counts)

    ##
    # @brief 규격 위반 메시지에 reply bad_request를 보내고 연속 위반 횟수를 올린다.
    # @param conn 연결.
    # @param request_id 돌려줄 요청 ID(알 수 없으면 None).
    def _reject(self, conn, request_id):
        conn.violations += 1
        message = "요청 형식이 올바르지 않습니다."
        conn.send(self._reply(request_id, False, "bad_request", message, self._state_version))

    # === 상태 ===

    ##
    # @brief 게임 상태가 바뀌었을 때 게임 객체가 부른다(게임 락 안). 버전을 올리고 모든 연결에 state를 쌓는다.
    # @details 판이 바뀌었으면 이전 판의 요청 기록(reply 보관)을 비운다.
    def _on_game_change(self):
        self._state_version += 1
        snapshot = self._snapshot()
        if snapshot["game_id"] != self._last_game_id:
            self._last_game_id = snapshot["game_id"]
            self._replies.clear()
        self._broadcast(snapshot)

    ##
    # @brief 모든 연결에 state를 쌓는다. 실제 전송은 각 연결의 송신 작업이 한다.
    # @param snapshot _snapshot()의 결과.
    def _broadcast(self, snapshot):
        for conn in self._connections:
            conn.send_state(self._state_for(snapshot, conn))

    ##
    # @brief 연결과 무관한 state 본문을 만든다(규격 8절, `me` 제외).
    # @return state dict(`me` 제외).
    def _snapshot(self):
        return {
            "t": "state",
            "protocol_version": PROTOCOL_VERSION,
            "server_epoch": self.server_epoch,
            "state_version": self._state_version,
            **self._game.snapshot(),
        }

    ##
    # @brief state 본문에 받는 사람의 `me`를 붙인다.
    # @param snapshot _snapshot()의 결과.
    # @param conn 받을 연결.
    # @return 보낼 state dict.
    def _state_for(self, snapshot, conn):
        return {**snapshot, "me": self._game.me(snapshot, conn.user_id)}

    ##
    # @brief 연결 직후 보내는 hello 메시지를 만든다.
    # @param user 세션의 user 객체.
    # @return hello dict.
    def _hello(self, user):
        return {
            "t": "hello",
            "protocol_version": PROTOCOL_VERSION,
            "server_epoch": self.server_epoch,
            "server_ms": _now_ms(),
            "user": user,
        }

    ##
    # @brief reply 메시지를 만든다.
    # @return reply dict.
    def _reply(self, request_id, ok, code, message, state_version):
        return {
            "t": "reply",
            "id": request_id,
            "ok": ok,
            "code": code,
            "message": message,
            "state_version": state_version,
        }
