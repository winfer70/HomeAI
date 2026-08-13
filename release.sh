#!/bin/bash
# release.sh - HomeAI production release
# Run from local dev machine. Merges dev -> main, tags, and deploys to the target node.
set -e

NODE_HOST="${NODE_HOST:-node-c.lan}"
NODE_USER="${NODE_USER:-deploy}"
TARGET_DIR="${TARGET_DIR:-/opt/homeai}"
INTEGRATION_BRANCH="dev"
KUMA_PUSH_URL=""  # Optional: paste a Uptime Kuma push URL here

echo "[1/4] Merging $INTEGRATION_BRANCH -> main..."
git checkout main && git pull origin main
git merge "$INTEGRATION_BRANCH" --no-edit
VERSION="v$(date +%Y.%m.%d-%H%M)"
git tag -a "$VERSION" -m "Release $VERSION"
git push origin main --tags
git checkout "$INTEGRATION_BRANCH"
echo "Tagged $VERSION"

echo "[2/4] Connecting to $NODE_USER@$NODE_HOST..."
ssh "$NODE_USER@$NODE_HOST" bash << ENDSSH
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
