#!/usr/bin/env bash
# Assemble (pinned upstream + patches) into a throwaway tree and build the image.
# Offline: reads the vendored submodule, no network. Requires DOCKER (not on PACE;
# use a docker host or the monorepo CI). Env passthrough to build-zmqsim.sh:
#   ARCH=amd64|arm64   OUT_IMAGE=uzairakbar/deepracer-test:v0[-<arch>]   PUSH=0|1
set -euo pipefail
SERVICE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(git -C "$SERVICE" rev-parse --show-toplevel)"
[ -e "$SERVICE/upstream/.git" ] || git -C "$ROOT" submodule update --init "$SERVICE/upstream"

BUILD="$(mktemp -d)"; trap 'rm -rf "$BUILD"' EXIT
git -C "$SERVICE/upstream" archive HEAD | tar -x -C "$BUILD"
git -C "$BUILD" init -q
git -C "$BUILD" add -A
git -C "$BUILD" -c user.email=ci@local -c user.name=ci commit -qm base
git -C "$BUILD" -c user.email=ci@local -c user.name=ci am --3way "$SERVICE"/patches/*.patch >/dev/null

echo "==> building in $BUILD (ARCH=${ARCH:-native} OUT_IMAGE=${OUT_IMAGE:-default} PUSH=${PUSH:-0})"
( cd "$BUILD" && ./build-zmqsim.sh )
