# pm2 프로세스 및 웹 서버 상태를 확인하고 장애 시 디스코드 웹훅으로 알리는 스크립트
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REQUIRED_PM2_APPS = ("lol", "lol-web")
DEFAULT_HTTP_URL = "http://127.0.0.1:8791/"
ALERT_COOLDOWN_SECONDS = 1800  # 30분


def get_repo_root() -> Path:
    """스크립트 기준 저장소 루트 경로를 반환한다."""
    return Path(__file__).resolve().parent.parent


def get_alert_webhook_url(root_dir: Path | None = None) -> str:
    """환경변수 또는 .env 파일에서 ALERT_WEBHOOK_URL을 조회한다."""
    url = os.environ.get("ALERT_WEBHOOK_URL", "").strip()
    if url:
        return url

    if root_dir is None:
        root_dir = get_repo_root()
    env_file = root_dir / ".env"
    if env_file.is_file():
        try:
            with open(env_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    if key.strip() == "ALERT_WEBHOOK_URL":
                        return val.strip().strip("'\"")
        except Exception:
            pass
    return ""


def default_pm2_provider() -> str:
    """실제 pm2 jlist 명령을 실행하여 JSON 출력을 가져온다."""
    res = subprocess.run(["pm2", "jlist"], capture_output=True, text=True, check=True)
    return res.stdout


def check_pm2(pm2_json_text: str) -> list[str]:
    """pm2 JSON 결과를 해석하여 lol, lol-web이 online인지 확인한다."""
    errors = []
    try:
        data = json.loads(pm2_json_text)
    except Exception as e:
        return [f"pm2 출력 해석 실패({e})."]

    if not isinstance(data, list):
        return ["pm2 출력이 올바른 프로세스 목록 형식이 아닙니다."]

    status_map = {}
    for proc in data:
        name = proc.get("name")
        pm2_env = proc.get("pm2_env") or {}
        status = pm2_env.get("status")
        if name:
            status_map[name] = status

    for req in REQUIRED_PM2_APPS:
        if req not in status_map:
            errors.append(f"{req} 프로세스를 찾을 수 없습니다.")
        elif status_map[req] != "online":
            errors.append(f"{req} 상태가 비정상입니다(상태: {status_map[req]}).")

    return errors


def check_http(url: str = DEFAULT_HTTP_URL) -> list[str]:
    """HTTP 엔드포인트에 요청을 보내 200 응답인지 확인한다."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LolHealthCheck/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status != 200:
                return [f"웹 서버 응답 코드 오류({resp.status})."]
    except urllib.error.HTTPError as e:
        return [f"웹 서버 HTTP 오류({e.code})."]
    except Exception as e:
        return [f"웹 서버 접속 실패({e})."]
    return []


def default_webhook_sender(webhook_url: str, message: str) -> None:
    """디스코드 웹훅으로 메시지를 전송한다."""
    payload = json.dumps({"content": message}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "LolHealthCheck/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        pass


def run_healthcheck(
    pm2_provider=default_pm2_provider,
    http_checker=check_http,
    webhook_sender=default_webhook_sender,
    state_file_path: Path | None = None,
    webhook_url: str | None = None,
    now: float | None = None,
    root_dir: Path | None = None,
) -> dict:
    """헬스체크를 수행하고 상태 변화에 따라 디스코드 알림을 전송한다."""
    if now is None:
        now = time.time()
    if root_dir is None:
        root_dir = get_repo_root()
    if state_file_path is None:
        state_file_path = root_dir / "logs" / "healthcheck_state.json"
    if webhook_url is None:
        webhook_url = get_alert_webhook_url(root_dir)

    # 1. 상태 검사
    errors = []
    try:
        pm2_output = pm2_provider()
        errors.extend(check_pm2(pm2_output))
    except Exception as e:
        errors.append(f"pm2 확인 실패({e}).")

    try:
        errors.extend(http_checker())
    except Exception as e:
        errors.append(f"HTTP 확인 실패({e}).")

    is_ok = len(errors) == 0
    current_status = "ok" if is_ok else "failed"
    current_error = " / ".join(errors)

    # 2. 기존 상태 읽기
    prev_state = {"last_status": "ok", "last_error": "", "last_alert_time": 0.0}
    if state_file_path.is_file():
        try:
            prev_state = json.loads(state_file_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    last_status = prev_state.get("last_status", "ok")
    last_error = prev_state.get("last_error", "")
    last_alert_time = float(prev_state.get("last_alert_time", 0.0))

    message_to_send = None
    should_update_alert_time = False

    if is_ok:
        if last_status == "failed":
            # 장애에서 복구된 경우 한 번 알림
            message_to_send = "[정상 복구됨] 봇 및 웹 서버 상태가 정상으로 복구되었습니다."
            should_update_alert_time = True
    else:
        # 장애 상태인 경우
        if last_status == "ok" or current_error != last_error:
            # 새로운 장애이거나 장애 내용이 바뀐 경우 즉시 알림
            message_to_send = f"[장애 발생] {current_error}"
            should_update_alert_time = True
        elif now - last_alert_time >= ALERT_COOLDOWN_SECONDS:
            # 동일 장애라도 30분이 경과했으면 다시 알림
            message_to_send = f"[장애 지속] {current_error}"
            should_update_alert_time = True

    # 3. 알림 전송
    if message_to_send and webhook_url:
        try:
            webhook_sender(webhook_url, message_to_send)
        except Exception:
            pass

    # 4. 새 상태 저장
    new_alert_time = now if should_update_alert_time else last_alert_time
    new_state = {
        "last_status": current_status,
        "last_error": current_error,
        "last_alert_time": new_alert_time,
    }
    try:
        state_file_path.parent.mkdir(parents=True, exist_ok=True)
        state_file_path.write_text(json.dumps(new_state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    return {
        "status": current_status,
        "errors": errors,
        "message_sent": message_to_send if webhook_url else None,
    }


def main() -> None:
    run_healthcheck()


if __name__ == "__main__":
    main()
