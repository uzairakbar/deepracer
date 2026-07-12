#!/usr/bin/env bash
# Move the upstream pin to a new ref, re-apply patches (3-way), and re-export.
# Usage: bump_upstream.sh <upstream-tag-or-sha>
set -euo pipefail
REF="${1:?usage: bump_upstream.sh <upstream-tag-or-sha>}"
SERVICE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

git -C "$SERVICE/upstream" fetch --tags origin
git -C "$SERVICE/upstream" checkout "$REF"
echo "pin moved to ${REF}. re-applying patches..."
"$SERVICE/scripts/init_workspace.sh" || true   # may conflict; resolve in workspace/
cat <<EOF

next:
  1. resolve any conflicts in $SERVICE/workspace  (git am --continue)
  2. build + validate the image on a docker host / CI
  3. $SERVICE/scripts/export_patches.sh
  4. git add service/upstream service/patches && \\
     git commit -m "chore(service): bump upstream to ${REF}"
EOF
