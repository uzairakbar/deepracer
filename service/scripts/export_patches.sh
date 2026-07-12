#!/usr/bin/env bash
# Save the workspace's commits back to the tracked patch series. Run after
# committing your changes inside workspace/. Then commit the updated patches/.
set -euo pipefail
SERVICE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS="$SERVICE/workspace"
[ -d "$WS/.git" ] || { echo "no workspace/; run init_workspace.sh first"; exit 1; }
cd "$WS"
rm -f "$SERVICE"/patches/*.patch
git format-patch _base..HEAD -o "$SERVICE/patches" >/dev/null
echo "exported $(ls "$SERVICE"/patches/*.patch | wc -l) patches -> service/patches/"
