#!/usr/bin/env bash
# 맥미니에서 봇과 웹 서비스를 빌드하고 pm2로 재시작하는 배포 스크립트
set -euo pipefail

DEV_RESTART=false
for arg in "$@"; do
  if [[ "$arg" == "--dev" ]]; then
    DEV_RESTART=true
  fi
done

# 저장소 루트로 이동
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
echo "[배포] 저장소 루트로 이동: $REPO_ROOT"

# 최신 코드 동기화
echo "[배포 1/4] Git 원격 코드 가져오기 (git pull --ff-only)..."
git pull --ff-only

# 파이썬 의존성 동기화
echo "[배포 2/4] Python 의존성 동기화 (uv sync)..."
uv sync

# 프론트엔드 빌드
echo "[배포 3/4] 웹 액티비티 의존성 설치 및 빌드 (npm ci, npm run build)..."
(
  cd web/activity
  npm ci
  npm run build
)

# 실행 중인 앱만 재시작한다. 봇은 필요할 때만 켜 두므로, 꺼져 있으면 배포가 켜지 않는다
restart_if_online() {
  local app="$1"
  if pm2 jlist | python3 -c "import sys, json; sys.exit(0 if any(p['name'] == '$app' and p['pm2_env']['status'] == 'online' for p in json.load(sys.stdin)) else 1)"; then
    pm2 restart "$app"
  else
    echo "[배포] $app 은(는) 꺼져 있어 재시작하지 않습니다."
  fi
}

# pm2 프로세스 재시작
echo "[배포 4/4] pm2 재시작 (lol-web은 항상, lol-bot은 켜져 있을 때만)..."
pm2 restart lol-web
restart_if_online lol-bot
if [[ "$DEV_RESTART" == "true" ]]; then
  restart_if_online lol-bot-dev
  restart_if_online lol-web-dev
fi

echo "[배포 완료] 모든 배포 단계가 정상적으로 완료되었습니다."
