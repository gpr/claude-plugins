#!/usr/bin/env bash
# Background job: one Haiku call per file fills the `desc:` lines of the outline.
# Usage: enrich.sh <abs_source> <kb_file> <sha256>
set -uo pipefail
src="$1" kb="$2" sha="$3"
max_bytes="${CODE_OUTLINE_MAX_BYTES:-200000}"

command -v claude &>/dev/null && command -v jq &>/dev/null || exit 0
(( $(wc -c <"$src") <= max_bytes )) || exit 0

exec 9>"$kb.lock"
flock -n 9 || exit 0
trap 'rm -f "$kb.lock" "$kb.enrich.$$"' EXIT

prompt="Below is a code outline skeleton followed by the source file. For every section header of the outline (the 'L<start>-<end>' ranges, including 'preamble' if present), write ONE short sentence (max 20 words) saying what the section does and when a reader would need it. Reply with ONLY a JSON object mapping the exact range string (e.g. \"L31-58\") to the sentence.

=== OUTLINE ===
$(cat "$kb")

=== SOURCE ===
$(cat "$src")"

result="$(printf '%s' "$prompt" | CODE_OUTLINE_INNER=1 timeout 120 claude -p --model haiku --tools "" --strict-mcp-config --no-session-persistence --output-format json 2>/dev/null | jq -r '.result // empty')" || exit 0
[[ -n "$result" ]] || exit 0
# strip optional ``` fences
map="$(sed -e '/^```/d' <<<"$result" | jq -c 'if type=="object" then . else empty end' 2>/dev/null)" || exit 0
[[ -n "$map" ]] || exit 0

# source may have changed while Haiku was working
[[ "$(sha256sum "$src" | cut -d' ' -f1)" == "$sha" ]] || exit 0
grep -q "^source_sha256: $sha\$" "$kb" || exit 0

tmp="$kb.enrich.$$"
jq -r 'to_entries[] | "\(.key)\t\(.value)"' <<<"$map" | awk -F'\t' '
  NR==FNR { d[$1]=$2; next }
  /^#+ L[0-9]+-[0-9]+/ { split($0, a, " "); cur=a[2] }
  /^- desc: / && (cur in d) { print "- desc: " d[cur]; next }
  /^status: skeleton$/ { print "status: enriched"; next }
  { print }
' - "$kb" >"$tmp" && mv "$tmp" "$kb"
