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

# pm2 프로세스 재시작
if [[ "$DEV_RESTART" == "true" ]]; then
  echo "[배포 4/4] pm2 운영 및 개발 프로세스 재시작 (lol, lol-web, lol-dev, lol-dev-web)..."
  pm2 restart lol lol-web lol-dev lol-dev-web
else
  echo "[배포 4/4] pm2 운영 프로세스 재시작 (lol, lol-web)..."
  pm2 restart lol lol-web
fi

echo "[배포 완료] 모든 배포 단계가 정상적으로 완료되었습니다."
