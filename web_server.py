# 정적 자산 및 대시보드·액티비티를 서빙하는 aiohttp 기반 웹 서버
import os
from pathlib import Path

import aiohttp.web_log
from aiohttp import web

DIST_MISSING_MSG = "웹 빌드가 없습니다"
CACHE_NO_CACHE = "no-cache"
CACHE_IMMUTABLE = "public, max-age=31536000, immutable"


class PathOnlyAccessLogger(aiohttp.web_log.AccessLogger):
    """접근 로그에 쿼리 문자열을 제외하고 경로만 기록하는 로거."""

    @staticmethod
    def _format_r(request: web.BaseRequest, response: web.StreamResponse, time: float) -> str:
        if request is None:
            return "-"
        return f"{request.method} {request.path} HTTP/{request.version.major}.{request.version.minor}"


def safe_resolve_child(base_dir: Path, subpath: str) -> Path | None:
    """정해진 폴더 밖으로 벗어나는 경로 탐색(상대경로, 절대경로, 심볼릭 링크)을 차단하고 파일 경로를 반환한다."""
    clean = subpath.lstrip("/\\")
    if Path(clean).is_absolute() or (len(clean) >= 2 and clean[1] == ":"):
        return None
    try:
        base_resolved = base_dir.resolve()
        candidate = (base_dir / clean).resolve()
        if not candidate.is_relative_to(base_resolved):
            return None
        if not candidate.is_file():
            return None
        return candidate
    except Exception:
        return None


def create_app(root_dir: Path | str | None = None) -> web.Application:
    """웹 서버 aiohttp 애플리케이션을 생성하고 라우트를 등록한다."""
    if root_dir is None:
        root_path = Path(__file__).resolve().parent
    else:
        root_path = Path(root_dir).resolve()

    dist_dir = (root_path / "web" / "activity" / "dist").resolve()
    web_dir = (root_path / "web").resolve()
    data_file = (root_path / "data" / "history_data.json").resolve()

    app = web.Application()

    def check_dist() -> web.Response | None:
        if not dist_dir.is_dir():
            return web.Response(
                status=503,
                text=DIST_MISSING_MSG,
                content_type="text/plain",
                charset="utf-8",
            )
        return None

    def make_file_response(file_path: Path, cache_control: str | None = None) -> web.FileResponse:
        headers = {}
        if cache_control:
            headers["Cache-Control"] = cache_control
        elif file_path.suffix.lower() == ".html":
            headers["Cache-Control"] = CACHE_NO_CACHE
        return web.FileResponse(file_path, headers=headers)

    # 1. 루트 경로 (Host 헤더에 따라 액티비티 또는 대시보드 분기)
    async def handle_root(request: web.Request) -> web.StreamResponse:
        err = check_dist()
        if err is not None:
            return err

        host_header = request.headers.get("Host") or ""
        host_name = host_header.split(":")[0].strip().lower()
        raw_hosts = os.environ.get("ACTIVITY_ROOT_HOSTS", "lol.hansoljj.com")
        activity_hosts = {h.strip().lower() for h in raw_hosts.split(",") if h.strip()}

        if host_name in activity_hosts:
            target = dist_dir / "index.html"
        else:
            target = dist_dir / "dashboard.html"

        if not target.is_file():
            return web.Response(status=404, text="Not Found")
        return make_file_response(target, cache_control=CACHE_NO_CACHE)

    # 2. 대시보드 명시 경로
    async def handle_dashboard(request: web.Request) -> web.StreamResponse:
        err = check_dist()
        if err is not None:
            return err
        target = dist_dir / "dashboard.html"
        if not target.is_file():
            return web.Response(status=404, text="Not Found")
        return make_file_response(target, cache_control=CACHE_NO_CACHE)

    # 3. 픽 루트 (/pick/)
    async def handle_pick_root(request: web.Request) -> web.StreamResponse:
        err = check_dist()
        if err is not None:
            return err
        target = dist_dir / "index.html"
        if not target.is_file():
            return web.Response(status=404, text="Not Found")
        return make_file_response(target, cache_control=CACHE_NO_CACHE)

    # 4. 픽 하위 자산 (/pick/<나머지>)
    async def handle_pick_tail(request: web.Request) -> web.StreamResponse:
        err = check_dist()
        if err is not None:
            return err
        tail = request.match_info["tail"]
        if not tail:
            target = dist_dir / "index.html"
            if not target.is_file():
                return web.Response(status=404, text="Not Found")
            return make_file_response(target, cache_control=CACHE_NO_CACHE)

        target = safe_resolve_child(dist_dir, tail)
        if target is None:
            return web.Response(status=404, text="Not Found")

        cache_control = None
        if tail.startswith("assets/"):
            cache_control = CACHE_IMMUTABLE
        elif target.suffix.lower() == ".html":
            cache_control = CACHE_NO_CACHE
        return make_file_response(target, cache_control=cache_control)

    # 5. /assets/*
    async def handle_assets(request: web.Request) -> web.StreamResponse:
        err = check_dist()
        if err is not None:
            return err
        tail = request.match_info["tail"]
        target = safe_resolve_child(dist_dir / "assets", tail)
        if target is None:
            return web.Response(status=404, text="Not Found")
        return make_file_response(target, cache_control=CACHE_IMMUTABLE)

    # 6. /fonts/*
    async def handle_fonts(request: web.Request) -> web.StreamResponse:
        err = check_dist()
        if err is not None:
            return err
        tail = request.match_info["tail"]
        target = safe_resolve_child(dist_dir / "fonts", tail)
        if target is None:
            return web.Response(status=404, text="Not Found")
        return make_file_response(target)

    # 7. /history_data.json
    async def handle_history_data(request: web.Request) -> web.StreamResponse:
        if not data_file.is_file():
            return web.Response(status=404, text="Not Found")
        return make_file_response(data_file, cache_control=CACHE_NO_CACHE)

    # 8. /terms, /terms.html
    async def handle_terms(request: web.Request) -> web.StreamResponse:
        target = (web_dir / "terms.html").resolve()
        if not target.is_file():
            return web.Response(status=404, text="Not Found")
        return make_file_response(target, cache_control=CACHE_NO_CACHE)

    # 9. /privacy, /privacy.html
    async def handle_privacy(request: web.Request) -> web.StreamResponse:
        target = (web_dir / "privacy.html").resolve()
        if not target.is_file():
            return web.Response(status=404, text="Not Found")
        return make_file_response(target, cache_control=CACHE_NO_CACHE)

    # 10. /legacy.html
    async def handle_legacy(request: web.Request) -> web.StreamResponse:
        target = (web_dir / "index.html").resolve()
        if not target.is_file():
            return web.Response(status=404, text="Not Found")
        return make_file_response(target, cache_control=CACHE_NO_CACHE)

    app.router.add_get("/", handle_root)
    app.router.add_get("/dashboard.html", handle_dashboard)
    app.router.add_get("/pick/", handle_pick_root)
    app.router.add_get("/pick/{tail:.*}", handle_pick_tail)
    app.router.add_get("/assets/{tail:.*}", handle_assets)
    app.router.add_get("/fonts/{tail:.*}", handle_fonts)
    app.router.add_get("/history_data.json", handle_history_data)
    app.router.add_get("/terms", handle_terms)
    app.router.add_get("/terms.html", handle_terms)
    app.router.add_get("/privacy", handle_privacy)
    app.router.add_get("/privacy.html", handle_privacy)
    app.router.add_get("/legacy.html", handle_legacy)

    return app


def main() -> None:
    """웹 서버 진입점."""
    port = int(os.environ.get("WEB_PORT", "8791"))
    app = create_app()
    web.run_app(app, host="127.0.0.1", port=port, access_log_class=PathOnlyAccessLogger)


if __name__ == "__main__":
    main()
