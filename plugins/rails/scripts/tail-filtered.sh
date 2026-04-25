#!/usr/bin/env bash
# Tails a Rails log and emits only lines matching an error pattern.
# Line-buffered so Claude Code sees each match as a discrete notification
# instead of waiting for stdio flush.

set -euo pipefail

LOG_PATH="${1:-log/development.log}"
PATTERN="${2:-}"

# Default pattern: exceptions, FATAL/ERROR lines, and 5xx completions.
# Kept as extended regex (ERE) so grep -E handles it directly.
DEFAULT_PATTERN='ERROR|FATAL|Completed 5[0-9]{2}|Exception|NoMethodError|ActiveRecord::|ActionController::|ArgumentError|RuntimeError'
if [ -z "${PATTERN}" ]; then
  PATTERN="${DEFAULT_PATTERN}"
fi

# Wait for the log file to appear. `tail -F` retries on its own, but some
# Rails projects don't create log/development.log until the first request,
# and early tail noise on a missing file is ugly in the task panel.
while [ ! -f "${LOG_PATH}" ]; do
  sleep 2
done

# --line-buffered: GNU grep flushes each match; BSD grep accepts it too.
# If you're on a system where grep lacks --line-buffered, swap in `stdbuf -oL grep -E ...`.
exec tail -n 0 -F "${LOG_PATH}" | grep --line-buffered -E "${PATTERN}"
