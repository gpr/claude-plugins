#!/usr/bin/env bash
# Caches `bin/rails routes --expanded` and emits diffs when config/routes.rb changes.
# Runs for the lifetime of the session. Each stdout line becomes a notification
# to Claude, so we emit one-line event summaries only.

set -euo pipefail

CACHE_DIR="${CLAUDE_PLUGIN_DATA:-${TMPDIR:-/tmp}}"
mkdir -p "${CACHE_DIR}"
CURRENT="${CACHE_DIR}/routes.current"
PREVIOUS="${CACHE_DIR}/routes.previous"
ROUTES_FILE="config/routes.rb"

has_rails() { [ -x bin/rails ] || command -v rails >/dev/null 2>&1; }

dump_routes() {
  if [ -x bin/rails ]; then
    bin/rails routes --expanded 2>/dev/null || return 1
  else
    rails routes --expanded 2>/dev/null || return 1
  fi
}

# Wait until the project looks like a Rails app.
WAIT=0
while [ ! -f "${ROUTES_FILE}" ] || ! has_rails; do
  sleep 2
  WAIT=$((WAIT + 2))
  if [ "${WAIT}" -gt 120 ]; then
    echo "[rails-routes-watcher] gave up waiting for a Rails app in $(pwd)"
    exit 0
  fi
done

if dump_routes > "${CURRENT}.tmp"; then
  mv "${CURRENT}.tmp" "${CURRENT}"
  cp "${CURRENT}" "${PREVIOUS}"
  LINES=$(wc -l < "${CURRENT}" | tr -d ' ')
  echo "[rails-routes-watcher] cached ${LINES} routes"
else
  echo "[rails-routes-watcher] initial routes dump failed; will retry on change"
fi

watch_routes() {
  if command -v fswatch >/dev/null 2>&1; then
    fswatch -0 "${ROUTES_FILE}" | while IFS= read -r -d '' _; do echo changed; done
  else
    # Poll fallback: check mtime every 3s.
    LAST=0
    while :; do
      MT=$(stat -f '%m' "${ROUTES_FILE}" 2>/dev/null || stat -c '%Y' "${ROUTES_FILE}" 2>/dev/null || echo 0)
      if [ "${MT}" != "${LAST}" ] && [ "${LAST}" != 0 ]; then
        echo changed
      fi
      LAST="${MT}"
      sleep 3
    done
  fi
}

watch_routes | while IFS= read -r _; do
  if dump_routes > "${CURRENT}.tmp"; then
    mv "${CURRENT}.tmp" "${CURRENT}"
    if [ -f "${PREVIOUS}" ] && ! diff -q "${PREVIOUS}" "${CURRENT}" >/dev/null; then
      ADDED=$(comm -13 <(sort "${PREVIOUS}") <(sort "${CURRENT}") | wc -l | tr -d ' ')
      REMOVED=$(comm -23 <(sort "${PREVIOUS}") <(sort "${CURRENT}") | wc -l | tr -d ' ')
      echo "[rails-routes-watcher] routes changed: +${ADDED} -${REMOVED}"
      cp "${CURRENT}" "${PREVIOUS}"
    fi
  fi
done
