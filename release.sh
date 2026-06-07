#!/bin/bash
# release.sh - HomeAI production release
# Run from local dev machine. Merges dev -> main, tags, deploys to REDACTED-HOST.
set -e

NODE_IP="10.0.0.104"  # REDACTED-HOST ethernet; use .107 if on WiFi
NODE_USER="kamilo"
TARGET_DIR="/home/kamilo/swarm-api"
INTEGRATION_BRANCH="dev"
KUMA_PUSH_URL=""  # TODO: create Push monitor in REDACTED-HOST:3001, paste URL here

echo "[1/4] Merging $INTEGRATION_BRANCH -> main..."
git checkout main && git pull origin main
git merge "$INTEGRATION_BRANCH" --no-edit
VERSION="v$(date +%Y.%m.%d-%H%M)"
git tag -a "$VERSION" -m "Release $VERSION"
git push origin main --tags
git checkout "$INTEGRATION_BRANCH"
echo "Tagged $VERSION"

echo "[2/4] Connecting to $NODE_USER@$NODE_IP..."
ssh "$NODE_USER@$NODE_IP" bash << ENDSSH
set -e
cd "$TARGET_DIR"

echo "[3/4] Pulling code..."
git fetch --tags && git checkout main && git pull origin main

echo "[4/4] Rebuilding containers..."
docker compose down && docker compose up -d --build
echo "Done."
ENDSSH

if [ -n "$KUMA_PUSH_URL" ]; then
  curl -s "${KUMA_PUSH_URL}?status=up&msg=${VERSION}&ping=" > /dev/null
  echo "Kuma notified."
fi

echo ""
echo "HomeAI $VERSION deployed."
