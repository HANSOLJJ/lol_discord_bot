# 정적 웹 서버(web_server.py)의 경로 라우팅·보안·캐시 헤더 단위 테스트
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from aiohttp.test_utils import AioHTTPTestCase, TestClient, TestServer

from web_server import DIST_MISSING_MSG, PathOnlyAccessLogger, create_app


class WebServerTest(AioHTTPTestCase):
    """정적 웹 서버 경로 및 동작 테스트."""

    async def get_application(self):
        # 임시 디렉터리에 가상 저장소 구조를 만든다.
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp_dir.name)

        self.dist_dir = self.root / "web" / "activity" / "dist"
        self.dist_assets = self.dist_dir / "assets"
        self.dist_fonts = self.dist_dir / "fonts"
        self.web_dir = self.root / "web"
        self.data_dir = self.root / "data"

        self.dist_assets.mkdir(parents=True, exist_ok=True)
        self.dist_fonts.mkdir(parents=True, exist_ok=True)
        self.web_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 테스트용 파일 생성
        (self.dist_dir / "dashboard.html").write_text("<h1>대시보드</h1>", encoding="utf-8")
        (self.dist_dir / "index.html").write_text("<h1>액티비티</h1>", encoding="utf-8")
        (self.dist_assets / "app-12345.js").write_text("console.log('app');", encoding="utf-8")
        (self.dist_fonts / "pretendard.woff2").write_bytes(b"dummy font")
        (self.data_dir / "history_data.json").write_text('{"games": []}', encoding="utf-8")
        (self.web_dir / "terms.html").write_text("<p>이용약관</p>", encoding="utf-8")
        (self.web_dir / "privacy.html").write_text("<p>개인정보처리방침</p>", encoding="utf-8")
        (self.web_dir / "index.html").write_text("<h1>옛 대시보드</h1>", encoding="utf-8")

        # 루트 바깥 비밀 파일
        (self.root / "secret.txt").write_text("비밀데이터", encoding="utf-8")

        return create_app(root_dir=self.root)

    async def tearDownAsync(self):
        await super().tearDownAsync()
        self.tmp_dir.cleanup()

    async def test_root_route_by_frame_id(self):
        """디스코드가 붙이는 frame_id가 있으면 액티비티, 없으면 대시보드를 내준다."""
        cases = [
            ({"Host": "lol.hansoljj.com"}, "/?frame_id=abc&instance_id=i-1", "액티비티"),
            ({"Host": "LOL.hansoljj.com:443"}, "/?frame_id=abc", "액티비티"),
            ({"Host": "lol.hansoljj.com"}, "/", "대시보드"),
            ({}, "/", "대시보드"),
            ({"Host": "lol.hansoljj.com"}, "/?instance_id=i-1", "대시보드"),
        ]
        for headers, path, expected in cases:
            resp = await self.client.get(path, headers=headers)
            self.assertEqual(resp.status, 200, path)
            self.assertEqual(resp.headers.get("Cache-Control"), "no-cache")
            self.assertIn(expected, await resp.text(), path)

    async def test_legacy_host_redirects_to_canonical(self):
        """arena.hansoljj.com으로 온 요청은 경로와 query를 유지한 채 lol.hansoljj.com으로 301 된다."""
        cases = [
            ("/", "https://lol.hansoljj.com/"),
            ("/terms", "https://lol.hansoljj.com/terms"),
            ("/?a=1&b=2", "https://lol.hansoljj.com/?a=1&b=2"),
            ("/없는경로", "https://lol.hansoljj.com/%EC%97%86%EB%8A%94%EA%B2%BD%EB%A1%9C"),
        ]
        for path, location in cases:
            for host in ("arena.hansoljj.com", "ARENA.hansoljj.com:443"):
                resp = await self.client.get(path, headers={"Host": host}, allow_redirects=False)
                self.assertEqual(resp.status, 301, (host, path))
                self.assertEqual(resp.headers.get("Location"), location, (host, path))

    async def test_dashboard_route(self):
        """/dashboard.html은 항상 dashboard.html을 반환한다."""
        resp = await self.client.get("/dashboard.html", headers={"Host": "lol.hansoljj.com"})
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.headers.get("Cache-Control"), "no-cache")
        text = await resp.text()
        self.assertIn("대시보드", text)

    async def test_pick_routes(self):
        """/pick/ 및 /pick/<나머지> 경로가 정상 동작한다."""
        # /pick/ -> dist/index.html
        resp = await self.client.get("/pick/")
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.headers.get("Cache-Control"), "no-cache")
        text = await resp.text()
        self.assertIn("액티비티", text)

        # /pick/assets/app-12345.js -> dist/assets/app-12345.js (캐시 불변)
        resp = await self.client.get("/pick/assets/app-12345.js")
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.headers.get("Cache-Control"), "public, max-age=31536000, immutable")
        text = await resp.text()
        self.assertIn("console.log", text)

    async def test_assets_and_fonts(self):
        """/assets/* 및 /fonts/* 경로가 올바른 헤더와 함께 서빙된다."""
        # /assets/app-12345.js
        resp = await self.client.get("/assets/app-12345.js")
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.headers.get("Cache-Control"), "public, max-age=31536000, immutable")

        # /fonts/pretendard.woff2
        resp = await self.client.get("/fonts/pretendard.woff2")
        self.assertEqual(resp.status, 200)
        body = await resp.read()
        self.assertEqual(body, b"dummy font")

    async def test_history_data_cache_header(self):
        """/history_data.json은 no-cache 헤더를 돌려준다."""
        resp = await self.client.get("/history_data.json")
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.headers.get("Cache-Control"), "no-cache")
        data = await resp.json()
        self.assertEqual(data, {"games": []})

    async def test_terms_privacy_legacy(self):
        """/terms, /terms.html, /privacy, /privacy.html, /legacy.html 경로가 정상 서빙된다."""
        for path, keyword in [
            ("/terms", "이용약관"),
            ("/terms.html", "이용약관"),
            ("/privacy", "개인정보처리방침"),
            ("/privacy.html", "개인정보처리방침"),
            ("/legacy.html", "옛 대시보드"),
        ]:
            resp = await self.client.get(path)
            self.assertEqual(resp.status, 200, f"Failed on path {path}")
            self.assertEqual(resp.headers.get("Cache-Control"), "no-cache")
            text = await resp.text()
            self.assertIn(keyword, text)

    async def test_404_routes(self):
        """정의되지 않은 경로는 404를 반환한다."""
        for path in ["/unknown", "/api/data", "/pick", "/terms/extra", "/assets/nonexistent.js"]:
            resp = await self.client.get(path)
            self.assertEqual(resp.status, 404, f"Path {path} did not return 404")

    async def test_path_traversal_protection(self):
        """.. 및 심볼릭 링크를 이용한 정해진 폴더 밖 파일 접근을 차단한다."""
        # 1. .. 를 통한 상위 디렉터리 접근 시도
        resp = await self.client.get("/assets/../../secret.txt")
        self.assertEqual(resp.status, 404)

        resp = await self.client.get("/pick/../secret.txt")
        self.assertEqual(resp.status, 404)

        # 2. 심볼릭 링크가 외부 파일을 가리킬 때 차단
        symlink_target = self.dist_assets / "escaped_link.txt"
        try:
            symlink_target.symlink_to(self.root / "secret.txt")
            resp = await self.client.get("/assets/escaped_link.txt")
            self.assertEqual(resp.status, 404)
        except (OSError, NotImplementedError):
            # Windows 권한 등으로 심볼릭 링크 생성이 제한될 경우 건너뜀
            pass


class DistMissingTest(unittest.IsolatedAsyncioTestCase):
    """dist 폴더가 없을 때 503 웹 빌드 오류 테스트."""

    async def test_dist_missing_503(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            web_dir = root / "web"
            data_dir = root / "data"
            web_dir.mkdir(parents=True, exist_ok=True)
            data_dir.mkdir(parents=True, exist_ok=True)
            (web_dir / "terms.html").write_text("<p>약관</p>", encoding="utf-8")
            (data_dir / "history_data.json").write_text("{}", encoding="utf-8")

            # dist/ 디렉터리를 만들지 않은 상태로 app 생성
            app = create_app(root_dir=root)
            server = TestServer(app)
            client = TestClient(server)
            await client.start_server()

            try:
                # dist에 의존하는 경로들은 503 반환
                for path in ["/", "/dashboard.html", "/pick/", "/pick/anything.js", "/assets/app.js", "/fonts/f.woff2"]:
                    resp = await client.get(path)
                    self.assertEqual(resp.status, 503, f"Path {path} did not return 503")
                    text = await resp.text()
                    self.assertEqual(text, DIST_MISSING_MSG)

                # dist와 무관한 경로들은 정상 작동
                resp_terms = await client.get("/terms")
                self.assertEqual(resp_terms.status, 200)

                resp_data = await client.get("/history_data.json")
                self.assertEqual(resp_data.status, 200)
            finally:
                await client.close()


class AccessLoggerTest(unittest.TestCase):
    """접근 로거가 쿼리 문자열을 제외하고 경로만 포맷팅하는지 테스트."""

    def test_format_r_strips_query(self):
        req = MagicMock()
        req.method = "GET"
        req.path = "/pick/"
        req.path_qs = "/pick/?token=secret123&user=noble"
        req.version.major = 1
        req.version.minor = 1

        resp = MagicMock()
        formatted = PathOnlyAccessLogger._format_r(req, resp, 0.01)
        self.assertEqual(formatted, "GET /pick/ HTTP/1.1")
        self.assertNotIn("secret123", formatted)
        self.assertNotIn("token", formatted)


if __name__ == "__main__":
    unittest.main()
