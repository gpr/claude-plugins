#!/usr/bin/env bash
# Bundle-watch monitor: rebuild on src/** change; emit a line only when a chunk
# grows >10 KB gzipped vs the previous build, or a forbidden Clerk module
# (backend/nextjs/clerk-js) appears in the rollup graph.
# Lazy-armed via on-skill-invoke:tanstack-query.
set -euo pipefail

d="$PWD"
while [ "$d" != "/" ]; do
  if [ -f "$d/pnpm-lock.yaml" ]; then
    break
  fi
  d="$(dirname "$d")"
done
if [ "$d" = "/" ]; then
  exit 0
fi
cd "$d" || exit 0

cache_dir=".cache"
mkdir -p "$cache_dir"
sizes_file="$cache_dir/bundle-sizes.json"
forbidden='@clerk/backend|@clerk/nextjs|@clerk/clerk-js'

# Pick a watcher: prefer fswatch, fall back to entr. If neither exists, exit
# quietly — the monitor is opt-in and we don't want to spam the agent.
if command -v fswatch >/dev/null 2>&1; then
  watch_cmd=(fswatch -o -e '\.cache' -e 'node_modules' src)
elif command -v entr >/dev/null 2>&1; then
  watch_cmd=(bash -c 'find src -type f | entr -d -p echo CHANGE')
else
  echo "bundle-watch: neither fswatch nor entr installed; monitor inactive" >&2
  exit 0
fi

run_build() {
  local out
  if ! out="$(pnpm exec vite build --mode analyze 2>&1)"; then
    printf 'bundle-watch: build failed\n%s\n' "$out" >&2
    return 0
  fi

  if printf '%s' "$out" | grep -E "$forbidden" >/dev/null 2>&1; then
    printf '%s\n' "$out" | grep -E "$forbidden" | head -5 \
      | sed 's/^/bundle-watch: forbidden import — /'
  fi

  if [ -d dist ]; then
    local current
    current="$(find dist -type f -name '*.js' -exec wc -c {} \; \
      | awk '{print $2 ":" $1}' | sort)"
    if [ -f "$sizes_file" ]; then
      local prev
      prev="$(cat "$sizes_file")"
      diff <(echo "$prev") <(echo "$current") \
        | awk -F: '/^>/ {name=$1; size=$2; sub(/> /, "", name); print name, size}' \
        | while read -r name size; do
            local prev_size
            prev_size="$(echo "$prev" | awk -F: -v n="$name" '$1==n{print $2}')"
            if [ -n "$prev_size" ] && [ "$((size - prev_size))" -gt 10240 ]; then
              printf 'bundle-watch: %s grew by %d bytes (>10KB)\n' \
                "$name" "$((size - prev_size))"
            fi
          done
    fi
    printf '%s' "$current" > "$sizes_file"
  fi
}

run_build
"${watch_cmd[@]}" | while read -r _; do
  run_build
done
