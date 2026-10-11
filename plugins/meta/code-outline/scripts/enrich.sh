#!/usr/bin/env bash
# Background job: one Haiku call per file fills the `desc:` lines of the outline.
# Usage: enrich.sh <abs_source> <kb_file> <sha256>
set -uo pipefail
src="$1" kb="$2" sha="$3"
max_bytes="${CODE_OUTLINE_MAX_BYTES:-200000}"

command -v claude &>/dev/null && command -v jq &>/dev/null || exit 0
(( $(wc -c <"$src") <= max_bytes )) || exit 0

sha256() {
  if command -v sha256sum &>/dev/null; then sha256sum "$1" | cut -d' ' -f1
  elif command -v shasum &>/dev/null; then shasum -a 256 "$1" | cut -d' ' -f1
  fi
}
if command -v timeout &>/dev/null; then limit=(timeout 120)
elif command -v gtimeout &>/dev/null; then limit=(gtimeout 120)
else limit=()
fi

# Portable lock (mkdir is atomic). A second job for the same file waits for the
# first instead of exiting, so an edit made mid-enrichment still gets enriched.
lock="$kb.lock.d"
waited=0
until mkdir "$lock" 2>/dev/null; do
  sleep 2; waited=$((waited + 2))
  if (( waited >= 130 )); then
    # stale lock from a killed job: take it over
    rm -rf "$lock"; mkdir "$lock" 2>/dev/null || exit 0; break
  fi
done
tmp="$kb.enrich.$$"
trap 'rm -rf "$lock" "$tmp"' EXIT

# The source or outline may have changed while we waited: work on what is current.
[[ "$(sha256 "$src")" == "$sha" ]] || exit 0
snapshot="$(cat "$kb")" || exit 0
grep -qx "source_sha256: $sha" <<<"$snapshot" || exit 0
grep -qx "status: skeleton" <<<"$snapshot" || exit 0

prompt="Below is a code outline skeleton followed by the source file. For every section header of the outline (the 'L<start>-<end>' ranges, including 'preamble' and 'epilogue' if present), write ONE short sentence (max 20 words) saying what the section does and when a reader would need it. Reply with ONLY a JSON object mapping the exact range string (e.g. \"L31-58\") to the sentence.

=== OUTLINE ===
$snapshot

=== SOURCE ===
$(cat "$src")"

result="$(printf '%s' "$prompt" | CODE_OUTLINE_INNER=1 ${limit[@]+"${limit[@]}"} env -u CLAUDECODE claude -p --model haiku --tools "" --strict-mcp-config --no-session-persistence --output-format json 2>/dev/null | jq -r '.result // empty')" || exit 0
[[ -n "$result" ]] || exit 0
# strip optional ``` fences
map="$(sed -e '/^```/d' <<<"$result" | jq -c 'if type=="object" and length > 0 then . else empty end' 2>/dev/null)" || exit 0
[[ -n "$map" ]] || exit 0

# Apply to the snapshot (not the live file) so descriptions can't land on a newer outline.
jq -r 'to_entries[] | "\(.key)\t\(.value)"' <<<"$map" | awk -F'\t' '
  NR==FNR { d[$1]=$2; next }
  /^#+ L[0-9]+-[0-9]+/ { split($0, a, " "); cur=a[2] }
  /^- desc: / && (cur in d) { print "- desc: " d[cur]; next }
  /^status: skeleton$/ { print "status: enriched"; next }
  { print }
' - <(printf '%s\n' "$snapshot") >"$tmp" || exit 0
[[ -s "$tmp" ]] || exit 0

# Final check right before the swap: the live outline must still be for this source.
[[ "$(sha256 "$src")" == "$sha" ]] || exit 0
grep -qx "source_sha256: $sha" "$kb" || exit 0
mv "$tmp" "$kb"
