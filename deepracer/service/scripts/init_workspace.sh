#!/usr/bin/env bash
# Recreate the local dev sandbox: a throwaway git clone of the pinned upstream
# with our patch series replayed as commits. Edit/commit/test here; never edit
# `upstream/` (the submodule) directly. `workspace/` is git-ignored.
set -euo pipefail
SERVICE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(git -C "$SERVICE" rev-parse --show-toplevel)"
WS="$SERVICE/workspace"

# init the submodule only if absent (don't reset a deliberate bump_upstream checkout)
[ -e "$SERVICE/upstream/.git" ] || git -C "$ROOT" submodule update --init "$SERVICE/upstream"
PIN="$(git -C "$SERVICE/upstream" rev-parse HEAD)"          # the pinned commit (not upstream's tip)
rm -rf "$WS"
git clone -q "$SERVICE/upstream" "$WS"
cd "$WS"
git checkout -q "$PIN"                                      # a local clone checks out the tip; pin it
git tag _base                                               # baseline for export_patches.sh
if git am --3way "$SERVICE"/patches/*.patch; then
    echo "workspace ready: $WS"
    echo "  base upstream@$(git rev-parse --short _base) + $(ls "$SERVICE"/patches/*.patch | wc -l) patches"
else
    echo "!! git am hit a conflict (expected after an upstream bump)."
    echo "   resolve in $WS, then: git am --continue  (repeat), then run export_patches.sh"
    exit 1
fi
