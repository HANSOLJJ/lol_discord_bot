# 헬스체크(healthcheck.py)의 프로세스·HTTP 검사 및 알림 로직 단위 테스트
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from scripts.healthcheck import check_http, check_pm2, run_healthcheck


class HealthCheckTest(unittest.TestCase):
    """헬스체크 검사 및 알림 동작 검증."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp_dir.name)
        self.state_file = self.root / "logs" / "healthcheck_state.json"
        self.webhook_url = "https://discord.com/api/webhooks/dummy"

    def tearDown(self):
        self.tmp_dir.cleanup()

    def make_pm2_output(self, lol_status="online", lol_web_status="online"):
        procs = []
        if lol_status is not None:
            procs.append({"name": "lol", "pm2_env": {"status": lol_status}})
        if lol_web_status is not None:
            procs.append({"name": "lol-web", "pm2_env": {"status": lol_web_status}})
        return json.dumps(procs)

    def test_check_pm2_success(self):
        """lol과 lol-web이 모두 online이면 에러가 없다."""
        output = self.make_pm2_output("online", "online")
        errors = check_pm2(output)
        self.assertEqual(errors, [])

    def test_check_pm2_missing_or_stopped(self):
        """프로세스가 없거나 online이 아니면 에러를 반환한다."""
        # lol 누락
        output_missing = self.make_pm2_output(lol_status=None, lol_web_status="online")
        errors = check_pm2(output_missing)
        self.assertTrue(any("lol 프로세스를 찾을 수 없습니다" in e for e in errors))

        # lol-web 상태 stopped
        output_stopped = self.make_pm2_output(lol_status="online", lol_web_status="stopped")
        errors = check_pm2(output_stopped)
        self.assertTrue(any("lol-web 상태가 비정상입니다" in e for e in errors))

        # 잘못된 JSON
        errors_bad_json = check_pm2("invalid json")
        self.assertTrue(any("해석 실패" in e for e in errors_bad_json))

    def test_run_healthcheck_normal_flow(self):
        """모두 정상일 때는 알림이 가지 않는다."""
        sent_messages = []

        def fake_sender(url, msg):
            sent_messages.append((url, msg))

        result = run_healthcheck(
            pm2_provider=lambda: self.make_pm2_output("online", "online"),
            http_checker=lambda: [],
            webhook_sender=fake_sender,
            state_file_path=self.state_file,
            webhook_url=self.webhook_url,
            now=1000.0,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(sent_messages), 0)

    def test_run_healthcheck_failure_and_cooldown(self):
        """장애 발생 시 알림을 보내고, 30분 내 동일 장애는 억제하며, 30분 경과 후 재전송한다."""
        sent_messages = []

        def fake_sender(url, msg):
            sent_messages.append((url, msg))

        # 1. t = 1000초: 첫 장애 발생 -> 알림 전송
        pm2_fail = lambda: self.make_pm2_output("errored", "online")
        res1 = run_healthcheck(
            pm2_provider=pm2_fail,
            http_checker=lambda: [],
            webhook_sender=fake_sender,
            state_file_path=self.state_file,
            webhook_url=self.webhook_url,
            now=1000.0,
        )
        self.assertEqual(res1["status"], "failed")
        self.assertEqual(len(sent_messages), 1)
        self.assertIn("장애 발생", sent_messages[-1][1])
        self.assertIn("lol 상태가 비정상입니다", sent_messages[-1][1])

        # 2. t = 1300초 (5분 뒤): 동일 장애 지속 -> 30분 이내이므로 알림 생략
        res2 = run_healthcheck(
            pm2_provider=pm2_fail,
            http_checker=lambda: [],
            webhook_sender=fake_sender,
            state_file_path=self.state_file,
            webhook_url=self.webhook_url,
            now=1300.0,
        )
        self.assertEqual(res2["status"], "failed")
        self.assertEqual(len(sent_messages), 1)  # 새 알림 없음

        # 3. t = 2900초 (31분 40초 뒤): 동일 장애 지속 -> 30분 경과로 재알림
        res3 = run_healthcheck(
            pm2_provider=pm2_fail,
            http_checker=lambda: [],
            webhook_sender=fake_sender,
            state_file_path=self.state_file,
            webhook_url=self.webhook_url,
            now=2900.0,
        )
        self.assertEqual(res3["status"], "failed")
        self.assertEqual(len(sent_messages), 2)
        self.assertIn("장애 지속", sent_messages[-1][1])

    def test_run_healthcheck_different_failure_alerts_immediately(self):
        """30분 이내라도 장애 유형이 바뀌면 즉시 알림을 보낸다."""
        sent_messages = []

        def fake_sender(url, msg):
            sent_messages.append((url, msg))

        # t = 1000: lol 에러
        run_healthcheck(
            pm2_provider=lambda: self.make_pm2_output("errored", "online"),
            http_checker=lambda: [],
            webhook_sender=fake_sender,
            state_file_path=self.state_file,
            webhook_url=self.webhook_url,
            now=1000.0,
        )
        self.assertEqual(len(sent_messages), 1)

        # t = 1100 (100초 뒤): HTTP 에러도 추가 발생 (새로운 에러 내용)
        run_healthcheck(
            pm2_provider=lambda: self.make_pm2_output("errored", "online"),
            http_checker=lambda: ["웹 서버 응답 오류(503)."],
            webhook_sender=fake_sender,
            state_file_path=self.state_file,
            webhook_url=self.webhook_url,
            now=1100.0,
        )
        self.assertEqual(len(sent_messages), 2)
        self.assertIn("웹 서버 응답 오류", sent_messages[-1][1])

    def test_run_healthcheck_recovery(self):
        """장애 후 정상이 되면 '복구됨' 알림을 한 번 보내고 이후에는 보내지 않는다."""
        sent_messages = []

        def fake_sender(url, msg):
            sent_messages.append((url, msg))

        # 1. 장애 발생
        run_healthcheck(
            pm2_provider=lambda: self.make_pm2_output("stopped", "online"),
            http_checker=lambda: [],
            webhook_sender=fake_sender,
            state_file_path=self.state_file,
            webhook_url=self.webhook_url,
            now=1000.0,
        )
        self.assertEqual(len(sent_messages), 1)

        # 2. 정상 복구
        run_healthcheck(
            pm2_provider=lambda: self.make_pm2_output("online", "online"),
            http_checker=lambda: [],
            webhook_sender=fake_sender,
            state_file_path=self.state_file,
            webhook_url=self.webhook_url,
            now=1050.0,
        )
        self.assertEqual(len(sent_messages), 2)
        self.assertIn("복구됨", sent_messages[-1][1])

        # 3. 정상 상태 지속 -> 알림 없음
        run_healthcheck(
            pm2_provider=lambda: self.make_pm2_output("online", "online"),
            http_checker=lambda: [],
            webhook_sender=fake_sender,
            state_file_path=self.state_file,
            webhook_url=self.webhook_url,
            now=1100.0,
        )
        self.assertEqual(len(sent_messages), 2)

    def test_no_webhook_url_graceful_exit(self):
        """webhook_url이 없으면 예외 없이 알림을 보내지 않고 정상 종료한다."""
        sender = MagicMock()
        res = run_healthcheck(
            pm2_provider=lambda: self.make_pm2_output("errored", "online"),
            http_checker=lambda: [],
            webhook_sender=sender,
            state_file_path=self.state_file,
            webhook_url="",
            now=1000.0,
        )
        self.assertEqual(res["status"], "failed")
        sender.assert_not_called()


if __name__ == "__main__":
    unittest.main()
