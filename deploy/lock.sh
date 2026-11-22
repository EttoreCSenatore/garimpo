#!/usr/bin/env bash
# Regenerate (or with --check, verify) the hashed dependency locks.
# Runs pip-compile inside the same Python the image and CI use (3.12), so the locks do not
# depend on whatever Python happens to be on your machine.
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE="python:3.12-slim"
MODE="${1:-}"

run() {
  # Run as the calling user so the files stay yours; pip-tools is installed from its own lock.
  docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD":/src -w /src \
    -e PIP_DISABLE_PIP_VERSION_CHECK=1 "$IMAGE" sh -c "
    python -m pip install -q --user --no-warn-script-location --require-hashes -r deploy/pip-tools.txt &&
    python -m piptools compile -q --generate-hashes --allow-unsafe --strip-extras --no-header \
      --output-file=\"$1\" \"$2\""
}

if [ "$MODE" = "--check" ]; then
  tmp="$(mktemp -d)"
  trap 'cp "$tmp/requirements.txt" "$tmp/requirements-dev.txt" . ; rm -rf "$tmp"' EXIT
  cp requirements.txt requirements-dev.txt "$tmp"/
  run requirements.txt requirements.in
  run requirements-dev.txt requirements-dev.in
  if ! diff -q requirements.txt "$tmp/requirements.txt" >/dev/null \
     || ! diff -q requirements-dev.txt "$tmp/requirements-dev.txt" >/dev/null; then
    echo "Locks are stale: run deploy/lock.sh and commit the result." >&2
    exit 1
  fi
  echo "Locks are up to date."
else
  run requirements.txt requirements.in
  run requirements-dev.txt requirements-dev.in
  echo "Locks regenerated."
fi
