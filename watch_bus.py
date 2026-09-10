# KOBUS 고속버스 취소표를 주기적으로 감시해 디스코드 채널로 알리는 독립 스크립트
"""
롤 봇(got_champe.py)과 완전히 분리된 standalone 스크립트다.

디스코드 게이트웨이를 쓰지 않고 REST API만 사용한다. 덕분에 MESSAGE CONTENT 특권
인텐트가 필요 없고, 같은 토큰을 쓰면서도 롤 봇과 충돌할 여지가 없다.

좌석 임시선점(setPcpy.ajax)은 만들지 않는다. 잔여석이 시간표 목록 응답에 그대로
들어 있어 순수 조회만으로 감시가 가능하기 때문이다.

사용법은 --help 참조.
"""

import argparse
import html
import http.cookiejar
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

import requests
from dotenv import load_dotenv

KOBUS_BASE = "https://www.kobus.co.kr"
KOBUS_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
BOOKING_URL = "https://www.kobus.co.kr/mrs/rotinf.do"

DISCORD_API = "https://discord.com/api/v10"
GUILD_ID = "391527401475014658"

## @brief 시간표 행(<p ... role="row">) 시작 지점
ROW_RE = re.compile(r'<p\b[^>]*\brole="row"[^>]*>')
TAG_RE = re.compile(r"<[^>]+>")
WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]

CMD_OFF = "알람끄기"
CMD_ON = "알람켜기"
CMD_STATUS = "상태"

## @brief 명령어 확인 주기(초). KOBUS 조회 주기와 분리해 명령 반응을 빠르게 유지한다
COMMAND_TICK = 5


def log(tag, msg):
    """
    ## @brief 타임스탬프를 붙여 콘솔에 운영 로그를 출력한다
    @param tag 로그 구분 태그
    @param msg 출력할 메시지
    """
    print(
        "%s [%s] %s" % (datetime.now().strftime("%m-%d %H:%M:%S"), tag, msg),
        flush=True,
    )


def strip_tags(fragment):
    """
    ## @brief HTML 조각에서 태그를 걷어내고 공백을 정규화한다
    @param fragment HTML 문자열
    @return 텍스트만 남은 문자열
    """
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", fragment))).strip()


# ---------------------------------------------------------------- KOBUS 조회


def make_opener():
    """
    ## @brief KOBUS 접속용 urllib opener 를 만든다
    @return 쿠키 자와 SSLContext 가 붙은 OpenerDirector

    @note kobus.co.kr 은 기본 cipher 설정으로는 핸드셰이크가 실패한다
          (SSLV3_ALERT_HANDSHAKE_FAILURE). SECLEVEL 을 낮춰야 접속되며,
          인증서 검증은 켠 채로 통과한다.
    """
    ctx = ssl.create_default_context()
    try:
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
    except ssl.SSLError:
        pass
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
        urllib.request.HTTPSHandler(context=ctx),
    )


def _kobus_request(opener, url, data=None, referer=None, timeout=20):
    """
    ## @brief KOBUS 에 GET/POST 요청을 보내고 본문을 문자열로 반환한다
    @param opener make_opener() 로 만든 opener
    @param url 요청 URL
    @param data POST 폼 데이터 dict (None 이면 GET)
    @param referer Referer 헤더 값
    @param timeout 타임아웃(초)
    @return 응답 본문 문자열
    """
    headers = {"User-Agent": KOBUS_UA}
    if referer:
        headers["Referer"] = referer
    if data is None:
        req = urllib.request.Request(url, headers=headers, method="GET")
    else:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(
            url,
            data=urllib.parse.urlencode(data).encode(),
            headers=headers,
            method="POST",
        )
    with opener.open(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def start_session(opener):
    """
    ## @brief 세션 쿠키를 받기 위해 메인 페이지를 1회 조회한다
    @param opener make_opener() 로 만든 opener
    """
    _kobus_request(opener, KOBUS_BASE + "/main.do")


def fetch_board(opener, date, depart, arrive):
    """
    ## @brief 지정 노선/날짜의 시간표 페이지 HTML 을 가져온다
    @param opener make_opener() 로 만든 opener
    @param date 출발일 YYYYMMDD
    @param depart 출발 터미널 코드
    @param arrive 도착 터미널 코드
    @return 시간표 페이지 HTML 문자열
    """
    return _kobus_request(
        opener,
        KOBUS_BASE + "/mrs/alcnSrch.do",
        {
            "deprCd": depart,
            "arvlCd": arrive,
            "pathDvs": "sngl",
            "pathStep": "1",
            "deprDtm": date,
            "busClsCd": "0",
            "rtrpChc": "1",
            "timeLinkMin": "00",
            "timeLinkMax": "23",
        },
        KOBUS_BASE + "/main.do",
    )


def parse_board(body):
    """
    ## @brief 시간표 HTML 을 편별 정보 리스트로 파싱한다
    @param body fetch_board() 가 반환한 HTML
    @return [{key, time, grade, remain, fee, bookable}] 리스트
    @exception RuntimeError 파싱된 행이 하나도 없을 때

    @note 행이 0개면 "좌석 없음"이 아니라 차단/HTML 변경으로 간주해야 한다.
          좌석 없음으로 오인하면 알림이 영영 오지 않는다.
    """
    rows = []
    marks = list(ROW_RE.finditer(body))
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        block = body[mark.start() : end]

        time_hit = re.search(r'class="start_time"[^>]*>([^<]*)<', block)
        if not time_hit:
            continue
        depart_time = re.sub(r"\s", "", time_hit.group(1))

        remain_hit = re.search(r'class="remain"[^>]*>(.*?)</span>', block, re.S)
        remain_text = strip_tags(remain_hit.group(1)) if remain_hit else ""
        num_hit = re.search(r"(\d+)", remain_text)
        if not num_hit:
            continue
        remain = int(num_hit.group(1))

        grade_hit = re.search(r'class="grade_mo">([^<]*)<', block)
        fee_hit = re.search(r"\(([\d,]+)원\)", block)
        rows.append(
            {
                "key": depart_time.replace(":", ""),
                "time": depart_time,
                "grade": grade_hit.group(1).strip() if grade_hit else "?",
                "remain": remain,
                "fee": fee_hit.group(1) if fee_hit else "-",
                "bookable": "fnSatsChc(" in block,
            }
        )
    if not rows:
        raise RuntimeError(
            "시간표 행을 하나도 파싱하지 못했습니다 (차단/구조변경 의심)"
        )
    return rows


# -------------------------------------------------------------- 디스코드 REST


def _discord(token, method, path, payload=None, timeout=15):
    """
    ## @brief 디스코드 REST API 를 호출한다
    @param token 봇 토큰
    @param method HTTP 메서드
    @param path /channels/... 형태의 API 경로
    @param payload POST 본문 dict
    @param timeout 타임아웃(초)
    @return 파싱된 JSON (본문이 없으면 None)
    @exception requests.HTTPError 2xx 가 아닐 때
    """
    headers = {
        "Authorization": "Bot " + token,
        "User-Agent": "DiscordBot (watch_bus, 1.0)",
    }
    resp = requests.request(
        method, DISCORD_API + path, headers=headers, json=payload, timeout=timeout
    )
    if resp.status_code == 429:
        wait = float(resp.json().get("retry_after", 1))
        log("RATE", "디스코드 rate limit, %.1f초 대기" % wait)
        time.sleep(wait + 0.5)
        resp = requests.request(
            method, DISCORD_API + path, headers=headers, json=payload, timeout=timeout
        )
    resp.raise_for_status()
    return resp.json() if resp.content else None


def resolve_channel_id(token, name):
    """
    ## @brief 채널 이름으로 채널 ID 를 찾는다
    @param token 봇 토큰
    @param name 채널 이름
    @return 채널 ID 문자열
    @exception RuntimeError 해당 이름의 채널이 없을 때
    """
    for channel in _discord(token, "GET", "/guilds/%s/channels" % GUILD_ID):
        if channel["name"] == name:
            return channel["id"]
    raise RuntimeError("채널을 찾을 수 없습니다: %s" % name)


def send_message(token, channel_id, content):
    """
    ## @brief 채널에 메시지를 보낸다
    @param token 봇 토큰
    @param channel_id 채널 ID
    @param content 메시지 본문
    """
    _discord(token, "POST", "/channels/%s/messages" % channel_id, {"content": content})


def latest_message_id(token, channel_id):
    """
    ## @brief 채널의 최신 메시지 ID 를 가져온다 (명령 수신 기준선)
    @param token 봇 토큰
    @param channel_id 채널 ID
    @return 최신 메시지 ID 문자열, 메시지가 없으면 None
    """
    msgs = _discord(token, "GET", "/channels/%s/messages?limit=1" % channel_id)
    return msgs[0]["id"] if msgs else None


def poll_commands(token, channel_id, after_id):
    """
    ## @brief 기준선 이후의 새 메시지에서 명령어를 뽑아낸다
    @param token 봇 토큰
    @param channel_id 채널 ID
    @param after_id 이 ID 이후의 메시지만 조회 (None 이면 전체 중 최근 50건)
    @return (명령어 문자열 리스트, 갱신된 기준선 ID)

    @note 봇 자신의 메시지는 무시한다. 응답에 다시 반응하는 루프를 막기 위함이다.
    """
    path = "/channels/%s/messages?limit=50" % channel_id
    if after_id:
        path += "&after=%s" % after_id
    msgs = _discord(token, "GET", path)
    if not msgs:
        return [], after_id

    commands = []
    for msg in reversed(msgs):  # 디스코드는 최신순이라 뒤집어 시간순으로 처리
        if msg["author"].get("bot"):
            continue
        text = (msg.get("content") or "").strip()
        if text in (CMD_OFF, CMD_ON, CMD_STATUS):
            commands.append(text)
    return commands, msgs[0]["id"]


# ------------------------------------------------------------------ 메시지 조립


def date_label(date):
    """
    ## @brief YYYYMMDD 를 "2026-09-12(토)" 형태로 바꾼다
    @param date 날짜 문자열 YYYYMMDD
    @return 표시용 날짜 문자열
    """
    dt = datetime.strptime(date, "%Y%m%d")
    return "%s(%s)" % (dt.strftime("%Y-%m-%d"), WEEKDAY_KR[dt.weekday()])


def mention_prefix(spec):
    """
    ## @brief 멘션 지정 문자열을 디스코드 멘션 문구로 바꾼다
    @param spec 쉼표로 구분한 유저 ID 목록. "everyone"/"here" 도 허용, 빈 값이면 멘션 없음
    @return 멘션 문자열 (없으면 빈 문자열)

    @note 멘션이 없으면 서버 기본 알림 설정("@멘션만")에서 푸시가 뜨지 않는다.
    """
    parts = []
    for token in (spec or "").split(","):
        token = token.strip().lstrip("@")
        if not token:
            continue
        parts.append("@" + token if token in ("everyone", "here") else "<@%s>" % token)
    return " ".join(parts)


def format_alert(row, date, route, mention=""):
    """
    ## @brief 취소표 발견 알림 문구를 만든다
    @param row parse_board() 의 행 하나
    @param date 출발일 YYYYMMDD
    @param route "서울경부 → 삼척" 형태의 노선 표시
    @param mention 앞에 붙일 멘션 문자열
    @return 디스코드 메시지 문자열
    """
    lines = [
        ("%s 🚌 **취소표 발견!**" % mention).strip(),
        "%s  %s" % (date_label(date), route),
        "**%s %s · 잔여 %d석 · %s원**"
        % (row["time"], row["grade"], row["remain"], row["fee"]),
        BOOKING_URL,
    ]
    if not row["bookable"]:
        lines.append(
            "(웹 예매 버튼이 닫힌 편입니다 — 고속버스 모바일앱으로 시도하세요)"
        )
    lines.append("알림을 멈추려면 `%s`" % CMD_OFF)
    return "\n".join(lines)


# ---------------------------------------------------------------------- 실행


def run_once(opener, args, route):
    """
    ## @brief 시간표를 한 번만 조회해 콘솔에 표로 출력한다 (디스코드 미사용)
    @param opener make_opener() 로 만든 opener
    @param args 파싱된 CLI 인자
    @param route 노선 표시 문자열
    @return 종료 코드
    """
    start_session(opener)
    rows = parse_board(fetch_board(opener, args.date, args.depart, args.arrive))
    print("=== %s  %s  (%d편) ===" % (date_label(args.date), route, len(rows)))
    for row in rows:
        mark = " <<< 감시대상" if row["key"] in args.times else ""
        print(
            "  %-6s %-7s %3d석 %10s원 %s%s"
            % (
                row["time"],
                row["grade"],
                row["remain"],
                row["fee"],
                "예매가능" if row["bookable"] else "예매불가",
                mark,
            )
        )
    missing = [t for t in args.times if t not in {r["key"] for r in rows}]
    if missing:
        print("[WARN] 시간표에 없는 감시대상: %s" % ", ".join(missing))
    return 0


def watch(opener, args, route, token, channel_id):
    """
    ## @brief 감시 루프를 돈다 (Ctrl+C 로 종료)
    @param opener make_opener() 로 만든 opener
    @param args 파싱된 CLI 인자
    @param route 노선 표시 문자열
    @param token 봇 토큰
    @param channel_id 알림 채널 ID
    @return 종료 코드
    """
    after_id = latest_message_id(token, channel_id)
    mention = mention_prefix(args.mention)
    pending = list(args.times)
    last_remain = {t: 0 for t in pending}
    last_alert = {t: 0.0 for t in pending}
    last_poll = "아직 없음"
    enabled = True
    fails = 0
    warned = False

    send_message(
        token,
        channel_id,
        "👀 감시 시작 — %s %s / %s\n%d초마다 확인합니다. `%s` `%s` `%s` 사용 가능."
        % (
            date_label(args.date),
            route,
            ", ".join(pending),
            args.interval,
            CMD_OFF,
            CMD_ON,
            CMD_STATUS,
        ),
    )
    next_poll = 0.0
    log("START", "%s %s / 감시대상 %s" % (args.date, route, ",".join(pending)))

    while True:
        # 1) 명령 수신 (꺼져 있어도 계속 듣는다)
        try:
            commands, after_id = poll_commands(token, channel_id, after_id)
        except Exception as exc:
            commands = []
            log("WARN", "명령 조회 실패: %s" % exc)

        for cmd in commands:
            if cmd == CMD_OFF:
                enabled = False
                log("CMD", "알람끄기")
                send_message(
                    token,
                    channel_id,
                    "🔕 알람을 껐습니다. KOBUS 조회도 멈춥니다. 다시 켜려면 `%s`"
                    % CMD_ON,
                )
            elif cmd == CMD_ON:
                enabled = True
                last_remain = {t: 0 for t in pending}
                last_alert = {t: 0.0 for t in pending}
                log("CMD", "알람켜기")
                send_message(
                    token, channel_id, "🔔 알람을 켰습니다. 감시를 재개합니다."
                )
            elif cmd == CMD_STATUS:
                log("CMD", "상태")
                send_message(
                    token,
                    channel_id,
                    "📋 %s / %s %s\n감시대상: %s\n마지막 확인: %s\n잔여석: %s"
                    % (
                        "켜짐" if enabled else "꺼짐",
                        date_label(args.date),
                        route,
                        ", ".join(pending) or "없음",
                        last_poll,
                        ", ".join("%s→%d석" % (t, last_remain[t]) for t in pending)
                        or "없음",
                    ),
                )

        if not enabled:
            time.sleep(COMMAND_TICK)
            continue

        # 2) 출발 시각이 지난 편은 감시 목록에서 뺀다
        now = datetime.now()
        alive = []
        for key in pending:
            if datetime.strptime(args.date + key, "%Y%m%d%H%M") > now:
                alive.append(key)
            else:
                log("DROP", "%s 편 출발 시각 경과" % key)
        pending = alive
        if not pending:
            send_message(
                token, channel_id, "🏁 감시 대상 편이 모두 출발했습니다. 종료합니다."
            )
            log("END", "감시 대상 소진")
            return 0

        # 3) 조회 (명령 확인보다 긴 주기로만)
        if time.time() < next_poll:
            time.sleep(COMMAND_TICK)
            continue
        next_poll = time.time() + args.interval
        try:
            rows = parse_board(fetch_board(opener, args.date, args.depart, args.arrive))
            fails = 0
            warned = False
        except Exception as exc:
            fails += 1
            log("FAIL", "조회 실패 %d회: %s" % (fails, exc))
            if fails % 5 == 0:
                log("INFO", "세션을 새로 만듭니다")
                opener = make_opener()
                try:
                    start_session(opener)
                except Exception as sub:
                    log("WARN", "세션 재생성 실패: %s" % sub)
            if fails >= 10 and not warned:
                warned = True
                try:
                    send_message(
                        token,
                        channel_id,
                        (
                            "%s ⚠️ KOBUS 조회가 %d회 연속 실패했습니다. "
                            "스크립트는 계속 재시도합니다." % (mention, fails)
                        ).strip(),
                    )
                except Exception:
                    pass
            time.sleep(COMMAND_TICK)
            continue

        # 4) 감시 대상 판정
        board = {r["key"]: r for r in rows}
        summary = []
        for key in pending:
            row = board.get(key)
            if row is None:
                summary.append("%s→없음" % key)
                continue
            summary.append("%s→%d석" % (key, row["remain"]))
            if row["remain"] <= 0:
                last_remain[key] = 0
                continue
            fresh = last_remain[key] == 0
            due = time.time() - last_alert[key] >= args.repeat
            if fresh or due:
                try:
                    send_message(
                        token,
                        channel_id,
                        format_alert(row, args.date, route, mention),
                    )
                    last_alert[key] = time.time()
                    log("ALERT", "%s %d석 알림 전송" % (key, row["remain"]))
                except Exception as exc:
                    log("WARN", "알림 전송 실패: %s" % exc)
            last_remain[key] = row["remain"]

        last_poll = datetime.now().strftime("%m-%d %H:%M:%S")
        log("POLL", " / ".join(summary))
        time.sleep(COMMAND_TICK)


def main(argv=None):
    """
    ## @brief CLI 진입점
    @param argv 인자 리스트 (None 이면 sys.argv)
    @return 종료 코드
    """
    parser = argparse.ArgumentParser(
        description="KOBUS 고속버스 취소표 감시 → 디스코드 알림"
    )
    parser.add_argument("--date", default="20260912", help="출발일 YYYYMMDD")
    parser.add_argument(
        "--depart", default="010", help="출발 터미널 코드 (010=서울경부)"
    )
    parser.add_argument("--arrive", default="220", help="도착 터미널 코드 (220=삼척)")
    parser.add_argument(
        "--times", default="2100,2230", help="감시할 출발시각 (쉼표 구분)"
    )
    parser.add_argument("--interval", type=int, default=60, help="조회 주기(초)")
    parser.add_argument(
        "--repeat", type=int, default=300, help="좌석 발견 후 재알림 간격(초)"
    )
    parser.add_argument("--channel", default="bus-watchdog", help="알림 채널 이름")
    parser.add_argument(
        "--mention",
        default="everyone",
        help="알림에 붙일 멘션. everyone/here 또는 쉼표 구분 유저 ID, 빈 값이면 멘션 없음",
    )
    parser.add_argument(
        "--route-name", default="서울경부 → 삼척", help="표시용 노선 이름"
    )
    parser.add_argument(
        "--once", action="store_true", help="한 번만 조회해 표 출력 (디스코드 미사용)"
    )
    parser.add_argument(
        "--test-notify", action="store_true", help="샘플 알림 1건 전송 후 종료"
    )
    args = parser.parse_args(argv)
    args.times = [t.strip() for t in args.times.split(",") if t.strip()]
    route = args.route_name

    opener = make_opener()

    if args.once:
        return run_once(opener, args, route)

    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("[ERROR] .env 에 DISCORD_TOKEN 이 없습니다")
        return 1

    channel_id = resolve_channel_id(token, args.channel)
    log("INIT", "채널 #%s (%s)" % (args.channel, channel_id))

    if args.test_notify:
        sample = {
            "time": "21:00",
            "grade": "우등",
            "remain": 2,
            "fee": "29,500",
            "bookable": True,
        }
        send_message(
            token,
            channel_id,
            "🧪 **테스트 메시지입니다 (실제 취소표 아님)**\n"
            + format_alert(sample, args.date, route, mention_prefix(args.mention)),
        )
        log("TEST", "샘플 알림 전송 완료")
        return 0

    try:
        start_session(opener)
    except Exception as exc:
        log("WARN", "세션 초기화 실패, 계속 진행: %s" % exc)

    try:
        return watch(opener, args, route, token, channel_id)
    except KeyboardInterrupt:
        log("END", "사용자 중단")
        return 0


if __name__ == "__main__":
    sys.exit(main())
